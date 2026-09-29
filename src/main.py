"""Punto de entrada CLI: recibe texto, decide motor o acción directa, y
responde con la personalidad del agente, su memoria de la conversación y
herramientas (bóveda de Obsidian y acciones en la PC) con permisos.
"""

from dataclasses import dataclass

from dotenv import load_dotenv

from src.actions.aplicaciones import reconoce_aplicacion
from src.actions.archivos import es_carpeta_conocida
from src.actions.busqueda_web import construir_contexto_web
from src.actions.confirmacion import Confirmador, confirmar_por_texto
from src.actions.navegador import parece_url
from src.agente.conversacion import Conversacion
from src.agente.personalidad import construir_prompt_sistema, quitar_muletilla_final
from src.agente.reflexion import aprender_si_quedo_sin_guardar
from src.consola import forzar_utf8
from src.engines.gemini_client import conversar_gemini, preguntar_gemini
from src.engines.modelos import RespuestaMotor
from src.engines.ollama_client import conversar_ollama
from src.herramientas.catalogo import REGISTRO, seleccionar_grupos
from src.herramientas.registro import ContextoEjecucion
from src.obsidian.contexto import evaluar_guardado
from src.obsidian.estructura import asegurar_estructura_boveda
from src.obsidian.herramientas import (
    MENSAJE_VERIFICACION,
    MENSAJE_VERIFICACION_PENDIENTE,
    MENSAJE_VERIFICACION_SISTEMA,
    afirma_accion_sin_hacerla,
    afirma_cambio_sin_hacerlo,
    niega_accion_hecha,
    resumen_de_acciones,
    usuario_reporta_tarea_hecha,
)
from src.obsidian.vault_writer import registrar_interaccion
from src.router.intent_router import (
    MOTOR_ACCION,
    MOTOR_GEMINI,
    MOTOR_GEMINI_FALLO,
    MOTOR_OLLAMA,
    cambio_de_modo_seguro,
    decidir_motor,
    es_busqueda_web,
    es_cierre,
    extraer_nombre_app,
    extraer_texto_a_escribir,
    extraer_texto_click,
    nombre_motor,
    parece_varias_instrucciones,
)

PREFIJO_CARPETA = "carpeta "


def _corregir_respuesta_ollama(
    texto: str, mensajes: list[dict], herramientas: list[dict], ejecutar, respuesta: RespuestaMotor
) -> RespuestaMotor:
    """Corrige dos formas conocidas en las que Crimson no dice la verdad sobre lo que hizo (ver
    src/obsidian/herramientas.py): afirmar un cambio/acción que no hizo, o negar uno que sí hizo.
    """
    if not respuesta.exito:
        return respuesta

    usadas = respuesta.herramientas_usadas or []
    if niega_accion_hecha(respuesta.texto, usadas):
        # Ya se hizo de verdad (herramientas_usadas lo prueba): reintentar con el modelo podría
        # repetir la acción (ej. abrir la misma app otra vez). Mejor corregirlo con lo que la
        # herramienta ya confirmó, sin volver a preguntarle.
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
        return respuesta

    mensaje_verificacion = None
    if afirma_cambio_sin_hacerlo(respuesta.texto, usadas):
        mensaje_verificacion = MENSAJE_VERIFICACION
    elif afirma_accion_sin_hacerla(respuesta.texto, usadas):
        mensaje_verificacion = MENSAJE_VERIFICACION_SISTEMA
    elif usuario_reporta_tarea_hecha(texto) and "completar_pendiente" not in usadas:
        # El usuario contó que ya hizo algo, pero el modelo solo charló sin revisar si era un
        # pendiente (no afirmó ningún cambio, así que afirma_cambio_sin_hacerlo no lo detecta).
        mensaje_verificacion = MENSAJE_VERIFICACION_PENDIENTE
    if not mensaje_verificacion:
        return respuesta

    mensajes = mensajes + [
        {"role": "assistant", "content": respuesta.texto},
        {"role": "user", "content": mensaje_verificacion},
    ]
    respuesta = conversar_ollama(mensajes, herramientas=herramientas, ejecutar=ejecutar)
    if not respuesta.exito:
        return respuesta

    usadas = respuesta.herramientas_usadas or []
    if niega_accion_hecha(respuesta.texto, usadas):
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
    elif afirma_cambio_sin_hacerlo(respuesta.texto, usadas) or afirma_accion_sin_hacerla(respuesta.texto, usadas):
        # Mejor admitirlo que decirle al usuario que algo quedó hecho cuando no.
        respuesta.texto = "No logré hacer eso. ¿Me lo repites, por favor?"
    return respuesta


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
    canal: str = "texto",
) -> Respuesta:
    """Decide qué hacer con el texto: acción directa, o que un agente responda con herramientas.

    motor_forzado (MOTOR_OLLAMA/MOTOR_GEMINI) salta el router, para cuando el
    usuario elige el agente a mano; None deja que el router decida. Los
    atajos (abrir, escribir, click) se detectan igual en cualquier caso.
    conversacion guarda los turnos previos; sin ella, cada mensaje es independiente.
    canal ("texto", "voz", "chat"...) queda en el registro de acciones.
    Toda acción, venga de un atajo o de un agente, pasa por REGISTRO.ejecutar
    (modo seguro, confirmación de lo irreversible y auditoría).
    """
    conversacion = conversacion or Conversacion()
    contexto = ContextoEjecucion(confirmador=confirmador, canal=canal)

    def accion(nombre: str, argumentos: dict) -> Respuesta:
        return _responder(texto, REGISTRO.ejecutar(nombre, argumentos, contexto), MOTOR_ACCION, conversacion)

    modo_seguro = cambio_de_modo_seguro(texto)
    if modo_seguro is not None:
        REGISTRO.modo_seguro = modo_seguro
        mensaje = (
            "Modo seguro activado: solo consultaré, no haré acciones hasta que digas \"sal del modo seguro\"."
            if modo_seguro
            else "Modo seguro desactivado: puedo volver a hacer acciones."
        )
        return _responder(texto, mensaje, MOTOR_ACCION, conversacion)

    if es_cierre(texto):
        if confirmador("¿Confirmas que quieres que cierre la aplicación?"):
            return _responder(texto, "De acuerdo, hasta luego.", MOTOR_ACCION, conversacion, cerrar=True)
        return _responder(texto, "Cancelado, sigo aquí.", MOTOR_ACCION, conversacion)

    # Atajo solo para instrucciones simples ("abre spotify"); "abre spotify y pon mi playlist" o
    # "abre mis pendientes" (no es una app) los resuelve el agente con sus herramientas.
    objetivo = extraer_nombre_app(texto)
    if objetivo and not parece_varias_instrucciones(objetivo):
        if objetivo.startswith(PREFIJO_CARPETA):
            return accion("abrir_carpeta", {"nombre": objetivo[len(PREFIJO_CARPETA):]})
        if parece_url(objetivo):
            return accion("abrir_url", {"url": objetivo})
        # Antes de intentar como app: "mis documentos" o "el escritorio" se confundían con apps de
        # nombre parecido ("Documentación de Referencia", "Conexión a Escritorio remoto").
        if es_carpeta_conocida(objetivo):
            return accion("abrir_carpeta", {"nombre": objetivo})
        if reconoce_aplicacion(objetivo):
            return accion("abrir_aplicacion", {"nombre": objetivo})

    # Guardado igual que arriba: "escribe hola mundo" es dictado literal, pero "escribe un correo
    # para mi jefe pidiendo permiso" es una instrucción compuesta y no algo para teclear tal cual
    # en la ventana activa; eso lo resuelve el agente (que puede seguir usando escribir_texto, pero
    # decidiendo primero qué escribir).
    texto_a_escribir = extraer_texto_a_escribir(texto)
    if texto_a_escribir is not None and not parece_varias_instrucciones(texto_a_escribir):
        return accion("escribir_texto", {"texto": texto_a_escribir})

    texto_click = extraer_texto_click(texto)
    if texto_click is not None:
        return accion("hacer_click", {"texto": texto_click})

    motor = motor_forzado or decidir_motor(texto)

    if motor == MOTOR_GEMINI:
        # Clover recibe su personalidad y perfil en el prompt de sistema, y el historial como texto.
        historial = conversacion.como_transcripcion()
        prompt = f"Conversación reciente:\n{historial}\n\nMensaje actual del usuario: {texto}" if historial else texto
        if es_busqueda_web(texto):
            # El grounding con Google Search va sin herramientas propias.
            respuesta = preguntar_gemini(
                prompt,
                usar_busqueda_web=True,
                instruccion_sistema=construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False),
            )
        else:
            respuesta = conversar_gemini(
                prompt,
                herramientas=REGISTRO.declaraciones_gemini(seleccionar_grupos(texto)),
                ejecutar=REGISTRO.ejecutor(contexto),
                instruccion_sistema=construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=True),
            )
        if respuesta.exito:
            return _responder(texto, respuesta.texto, MOTOR_GEMINI, conversacion, respuesta.herramientas_usadas)
        if respuesta.herramientas_usadas:
            # Ya hizo acciones antes de fallar: pasarle el mensaje a Ollama podría repetirlas.
            return Respuesta(
                texto=f"Hice parte de lo que pediste ({', '.join(respuesta.herramientas_usadas)}), "
                f"pero Gemini falló antes de terminar: {respuesta.error}",
                motor=MOTOR_GEMINI,
            )
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
    herramientas = REGISTRO.esquemas_ollama(seleccionar_grupos(texto, modelo_local=True))
    ejecutar = REGISTRO.ejecutor(contexto)
    respuesta = conversar_ollama(mensajes, herramientas=herramientas, ejecutar=ejecutar)
    respuesta = _corregir_respuesta_ollama(texto, mensajes, herramientas, ejecutar, respuesta)
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
    print("Crimson y Clover (CLI de texto). Escribe 'salir' para terminar.")
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
