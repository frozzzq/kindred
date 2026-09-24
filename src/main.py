"""Punto de entrada CLI (Fase 1 + Fase 2 + Fase 4): recibe texto, decide
motor o acción directa, inyecta contexto de la bóveda, responde y evalúa
qué guardar.
"""

from dataclasses import dataclass

from dotenv import load_dotenv

from src.actions.busqueda_web import construir_contexto_web
from src.actions.confirmacion import Confirmador, confirmar_por_texto
from src.actions.system_control import abrir_aplicacion
from src.engines.gemini_client import preguntar_gemini
from src.engines.ollama_client import preguntar_ollama
from src.obsidian.contexto import construir_contexto, evaluar_guardado
from src.obsidian.estructura import asegurar_estructura_boveda
from src.obsidian.vault_writer import registrar_interaccion
from src.router.intent_router import (
    MOTOR_ACCION,
    MOTOR_GEMINI,
    MOTOR_GEMINI_FALLO,
    MOTOR_OLLAMA,
    decidir_motor,
    es_busqueda_web,
    extraer_nombre_app,
    nombre_motor,
)


@dataclass
class Respuesta:
    """Respuesta del asistente junto con el motor que realmente la generó.

    El motor real puede diferir del elegido por el router si hubo fallback
    (ej. el router eligió Gemini pero falló y respondió Ollama). Se necesita
    saber cuál respondió de verdad para, por ejemplo, elegir la voz correcta.
    """

    texto: str
    motor: str


def procesar_comando(
    texto: str,
    confirmador: Confirmador = confirmar_por_texto,
    motor_forzado: str | None = None,
) -> Respuesta:
    """Decide qué hacer con el texto: acción directa, o motor (con contexto de la bóveda).

    motor_forzado (MOTOR_OLLAMA/MOTOR_GEMINI) salta el router, para cuando el
    usuario elige el agente a mano; None deja que el router decida. Las
    acciones (abrir apps) se detectan igual en cualquier caso.
    """
    nombre_app = extraer_nombre_app(texto)
    if nombre_app:
        if confirmador(f"¿Confirmas que abra '{nombre_app}'?"):
            resultado = abrir_aplicacion(nombre_app)
        else:
            resultado_texto = "Cancelado, no abrí nada."
            evaluar_guardado(texto, resultado_texto, MOTOR_ACCION)
            return Respuesta(texto=resultado_texto, motor=MOTOR_ACCION)
        evaluar_guardado(texto, resultado.mensaje, MOTOR_ACCION)
        return Respuesta(texto=resultado.mensaje, motor=MOTOR_ACCION)

    motor = motor_forzado or decidir_motor(texto)
    contexto = construir_contexto(texto)
    prompt = f"{contexto}\n\n{texto}" if contexto else texto

    if motor == MOTOR_GEMINI:
        respuesta = preguntar_gemini(prompt, usar_busqueda_web=es_busqueda_web(texto))
        if respuesta.exito:
            evaluar_guardado(texto, respuesta.texto, MOTOR_GEMINI)
            return Respuesta(texto=respuesta.texto, motor=MOTOR_GEMINI)
        print(f"[aviso] Gemini falló ({respuesta.error}), usando Ollama como fallback...")
        try:
            registrar_interaccion(texto, f"[fallo] {respuesta.error}", MOTOR_GEMINI_FALLO)
        except RuntimeError:
            pass  # sin bóveda configurada: no bloquea el flujo, solo no queda métrica de este fallo

    if es_busqueda_web(texto):
        # Ollama no tiene acceso a internet nativo (a diferencia de Gemini,
        # que usa su propio grounding); le damos resultados reales como
        # contexto auxiliar, típico cuando Gemini falló y cayó aquí.
        contexto_web = construir_contexto_web(texto)
        if contexto_web:
            prompt = f"{prompt}\n\n{contexto_web}"

    respuesta = preguntar_ollama(prompt)
    if respuesta.exito:
        evaluar_guardado(texto, respuesta.texto, MOTOR_OLLAMA)
        return Respuesta(texto=respuesta.texto, motor=MOTOR_OLLAMA)
    return Respuesta(texto=f"[error] Ollama también falló: {respuesta.error}", motor=MOTOR_OLLAMA)


def main() -> None:
    # override=True: OLLAMA_HOST también existe como variable de entorno de
    # Windows para configurar el SERVIDOR de Ollama (0.0.0.0:11434). Sin
    # override, esa variable del sistema tapa la URL completa del .env
    # (pensada para el CLIENTE) y las llamadas a Ollama fallan.
    load_dotenv(override=True)
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    print("Jarvis (CLI de prueba, Fase 1 + Fase 2 + Fase 4). Escribe 'salir' para terminar.")
    while True:
        try:
            texto = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit"}:
            break
        respuesta = procesar_comando(texto)
        print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")


if __name__ == "__main__":
    main()
