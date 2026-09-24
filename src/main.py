"""Punto de entrada CLI (Fase 1): recibe texto, decide motor, responde.

Sin voz ni Obsidian todavía (eso llega en Fases 2 y 3).
"""

from dotenv import load_dotenv

from src.engines.gemini_client import preguntar_gemini
from src.engines.ollama_client import preguntar_ollama
from src.router.intent_router import MOTOR_GEMINI, decidir_motor


def procesar_comando(texto: str) -> str:
    """Decide el motor para el texto y devuelve la respuesta, con fallback a Ollama."""
    motor = decidir_motor(texto)

    if motor == MOTOR_GEMINI:
        respuesta = preguntar_gemini(texto)
        if respuesta.exito:
            return respuesta.texto
        print(f"[aviso] Gemini falló ({respuesta.error}), usando Ollama como fallback...")

    respuesta = preguntar_ollama(texto)
    if respuesta.exito:
        return respuesta.texto
    return f"[error] Ollama también falló: {respuesta.error}"


def main() -> None:
    load_dotenv()
    print("Jarvis (CLI de prueba, Fase 1). Escribe 'salir' para terminar.")
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
