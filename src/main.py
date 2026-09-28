"""Punto de entrada CLI: recibe texto, decide motor o acción directa, y
responde con la personalidad del agente, su memoria de la conversación y
acceso a la bóveda de Obsidian mediante herramientas.
"""

from dataclasses import dataclass

from dotenv import load_dotenv

from src.actions.busqueda_web import construir_contexto_web
from src.actions.confirmacion import Confirmador, confirmar_por_texto
from src.actions.system_control import abrir_aplicacion, escribir_texto, hacer_click
from src.agente.conversacion import Conversacion
from src.agente.personalidad import construir_prompt_sistema, quitar_muletilla_final
from src.agente.reflexion import aprender_si_quedo_sin_guardar
from src.consola import forzar_utf8
from src.engines.gemini_client import preguntar_gemini
from src.engines.ollama_client import conversar_ollama
from src.obsidian.contexto import evaluar_guardado
from src.obsidian.estructura import asegurar_estructura_boveda
from src.obsidian.herramientas import (
    DEFINICIONES,
    MENSAJE_VERIFICACION,
    afirma_cambio_sin_hacerlo,
    ejecutar_herramienta,
)
from src.obsidian.vault_writer import registrar_interaccion
from src.router.intent_router import (
    MOTOR_ACCION,
    MOTOR_GEMINI,
    MOTOR_GEMINI_FALLO,
    MOTOR_OLLAMA,
    decidir_motor,
    es_busqueda_web,
    es_cierre,
    es_click_riesgoso,
    extraer_nombre_app,
    extraer_texto_a_escribir,
    extraer_texto_click,
    nombre_motor,
)


@dataclass
class Respuesta:
    """Respuesta del asistente junto con el motor que realmente la generó.

    El motor real puede diferir del elegido por el router si hubo fallback
    (ej. el router eligió Gemini pero falló y respondió Ollama). Se necesita
    saber cuál respondió de verdad para, por ejemplo, elegir la voz correcta.

    cerrar=True indica que el usuario pidió cerrar la aplicación (y lo
    confirmó): quien llame a procesar_comando debe terminar el programa (o
    cerrar la ventana) después de mostrar/decir esta respuesta.
    """

    texto: str
    motor: str
    cerrar: bool = False


def _responder(
    texto: str,
    respuesta: str,
    motor: str,
    conversacion: Conversacion,
    herramientas_usadas: list[str] | None = None,
    cerrar: bool = False,
) -> Respuesta:
    respuesta = quitar_muletilla_final(respuesta)
    evaluar_guardado(texto, respuesta, motor)
    if motor != MOTOR_ACCION:
        aprender_si_quedo_sin_guardar(texto, herramientas_usadas or [])
    conversacion.agregar_turno(texto, respuesta)
    return Respuesta(texto=respuesta, motor=motor, cerrar=cerrar)


def procesar_comando(
    texto: str,
    confirmador: Confirmador = confirmar_por_texto,
    motor_forzado: str | None = None,
    conversacion: Conversacion | None = None,
) -> Respuesta:
    """Decide qué hacer con el texto: acción directa, o que un agente responda.

    motor_forzado (MOTOR_OLLAMA/MOTOR_GEMINI) salta el router, para cuando el
    usuario elige el agente a mano; None deja que el router decida. Las
    acciones (abrir apps) se detectan igual en cualquier caso.
    conversacion guarda los turnos previos; sin ella, cada mensaje es independiente.
    """
    conversacion = conversacion or Conversacion()

    if es_cierre(texto):
        if confirmador("¿Confirmas que quieres que cierre la aplicación?"):
            return _responder(texto, "De acuerdo, hasta luego.", MOTOR_ACCION, conversacion, cerrar=True)
        return _responder(texto, "Cancelado, sigo aquí.", MOTOR_ACCION, conversacion)

    nombre_app = extraer_nombre_app(texto)
    if nombre_app:
        if confirmador(f"¿Confirmas que abra '{nombre_app}'?"):
            mensaje = abrir_aplicacion(nombre_app).mensaje
        else:
            mensaje = "Cancelado, no abrí nada."
        return _responder(texto, mensaje, MOTOR_ACCION, conversacion)

    texto_a_escribir = extraer_texto_a_escribir(texto)
    if texto_a_escribir is not None:
        return _responder(texto, escribir_texto(texto_a_escribir).mensaje, MOTOR_ACCION, conversacion)

    texto_click = extraer_texto_click(texto)
    if texto_click is not None:
        if es_click_riesgoso(texto_click) and not confirmador(f"¿Confirmas que haga click en '{texto_click}'?"):
            return _responder(texto, "Cancelado, no hice click.", MOTOR_ACCION, conversacion)
        return _responder(texto, hacer_click(texto_click).mensaje, MOTOR_ACCION, conversacion)

    motor = motor_forzado or decidir_motor(texto)

    if motor == MOTOR_GEMINI:
        # Gemini todavía no tiene herramientas: recibe la personalidad de Clover,
        # el perfil y los pendientes en el prompt de sistema, y el historial como texto.
        historial = conversacion.como_transcripcion()
        prompt = f"Conversación reciente:\n{historial}\n\nMensaje actual del usuario: {texto}" if historial else texto
        respuesta = preguntar_gemini(
            prompt,
            usar_busqueda_web=es_busqueda_web(texto),
            instruccion_sistema=construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False),
        )
        if respuesta.exito:
            return _responder(texto, respuesta.texto, MOTOR_GEMINI, conversacion)
        print(f"[aviso] Gemini falló ({respuesta.error}), usando Ollama como fallback...")
        try:
            registrar_interaccion(texto, f"[fallo] {respuesta.error}", MOTOR_GEMINI_FALLO)
        except RuntimeError:
            pass  # sin bóveda configurada: no bloquea el flujo, solo no queda métrica de este fallo

    mensaje_usuario = texto
    if es_busqueda_web(texto):
        # Ollama no tiene acceso a internet nativo (a diferencia de Gemini,
        # que usa su propio grounding); le damos resultados reales como
        # contexto auxiliar, típico cuando Gemini falló y cayó aquí.
        contexto_web = construir_contexto_web(texto)
        if contexto_web:
            mensaje_usuario = f"{texto}\n\n{contexto_web}"

    mensajes = [
        {"role": "system", "content": construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)},
        *conversacion.mensajes(),
        {"role": "user", "content": mensaje_usuario},
    ]
    respuesta = conversar_ollama(mensajes, herramientas=DEFINICIONES, ejecutar=ejecutar_herramienta)
    if respuesta.exito and afirma_cambio_sin_hacerlo(respuesta.texto, respuesta.herramientas_usadas):
        # Dijo que cambió algo sin haberlo hecho: se le da una oportunidad de hacerlo de verdad.
        mensajes += [
            {"role": "assistant", "content": respuesta.texto},
            {"role": "user", "content": MENSAJE_VERIFICACION},
        ]
        respuesta = conversar_ollama(mensajes, herramientas=DEFINICIONES, ejecutar=ejecutar_herramienta)
        if respuesta.exito and afirma_cambio_sin_hacerlo(respuesta.texto, respuesta.herramientas_usadas):
            # Mejor admitirlo que decirle al usuario que algo quedó guardado cuando no.
            respuesta.texto = "No logré hacer ese cambio en tu bóveda. ¿Me lo repites, por favor?"
    if respuesta.exito:
        return _responder(texto, respuesta.texto, MOTOR_OLLAMA, conversacion, respuesta.herramientas_usadas)
    return Respuesta(texto=f"[error] Ollama también falló: {respuesta.error}", motor=MOTOR_OLLAMA)


def main() -> None:
    forzar_utf8()
    # override=True: OLLAMA_HOST también existe como variable de entorno de
    # Windows para configurar el SERVIDOR de Ollama (0.0.0.0:11434). Sin
    # override, esa variable del sistema tapa la URL completa del .env
    # (pensada para el CLIENTE) y las llamadas a Ollama fallan.
    load_dotenv(override=True)
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    conversacion = Conversacion()
    print("Jarvis (CLI de texto). Escribe 'salir' para terminar.")
    while True:
        try:
            texto = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit"}:
            break
        respuesta = procesar_comando(texto, conversacion=conversacion)
        print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")
        if respuesta.cerrar:
            break


if __name__ == "__main__":
    main()
