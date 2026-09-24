"""Punto de entrada CLI (Fase 1 + Fase 2): recibe texto, decide motor,
inyecta contexto de la bóveda de Obsidian, responde y evalúa qué guardar.

Sin voz todavía (eso llega en Fase 3).
"""

from dotenv import load_dotenv

from src.engines.gemini_client import preguntar_gemini
from src.engines.ollama_client import preguntar_ollama
from src.obsidian.contexto import construir_contexto, evaluar_guardado
from src.obsidian.estructura import asegurar_estructura_boveda
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA, decidir_motor


def procesar_comando(texto: str) -> str:
    """Decide el motor, agrega contexto de la bóveda, responde y guarda si aplica."""
    motor = decidir_motor(texto)
    contexto = construir_contexto(texto)
    prompt = f"{contexto}\n\n{texto}" if contexto else texto

    if motor == MOTOR_GEMINI:
        respuesta = preguntar_gemini(prompt)
        if respuesta.exito:
            evaluar_guardado(texto, respuesta.texto, MOTOR_GEMINI)
            return respuesta.texto
        print(f"[aviso] Gemini falló ({respuesta.error}), usando Ollama como fallback...")

    respuesta = preguntar_ollama(prompt)
    if respuesta.exito:
        evaluar_guardado(texto, respuesta.texto, MOTOR_OLLAMA)
        return respuesta.texto
    return f"[error] Ollama también falló: {respuesta.error}"


def main() -> None:
    load_dotenv()
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    print("Jarvis (CLI de prueba, Fase 1 + Fase 2). Escribe 'salir' para terminar.")
    while True:
        try:
            texto = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit"}:
            break
        print(procesar_comando(texto))


if __name__ == "__main__":
    main()
