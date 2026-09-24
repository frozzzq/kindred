"""Punto de entrada de voz manos libres (Fase 3, mejora sobre push-to-talk):
espera la wake word "hey jarvis", graba automáticamente hasta silencio,
transcribe, decide motor/acción, responde por texto y por voz.

Reutiliza procesar_comando de src/main.py. Si prefieres el modo manual
(presionar Enter), usa src/main_voz.py en su lugar — ambos coexisten.
"""

from dotenv import load_dotenv

from src.actions.confirmacion import es_afirmativo
from src.main import procesar_comando
from src.obsidian.estructura import asegurar_estructura_boveda
from src.router.intent_router import nombre_motor
from src.voice.stt import escuchar_comando_automatico
from src.voice.tts import hablar
from src.voice.wakeword import esperar_wake_word


def confirmar_por_voz(descripcion: str) -> bool:
    """Pide confirmación hablando la pregunta y escuchando la respuesta (sin Enter)."""
    hablar(f"{descripcion} Di sí o no.")
    respuesta = escuchar_comando_automatico()
    return es_afirmativo(respuesta)


def main() -> None:
    # override=True: ver comentario en src/main.py sobre el choque de
    # OLLAMA_HOST con la variable de entorno del servidor de Ollama.
    load_dotenv(override=True)
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    print('Jarvis (voz manos libres, Fase 3). Di "hey jarvis" para activar. Ctrl+C para salir.')
    while True:
        try:
            print("Esperando wake word...")
            esperar_wake_word()
            print("¡Wake word detectada! Escuchando...")

            texto = escuchar_comando_automatico()
            if not texto:
                print("[aviso] No se entendió nada, intenta de nuevo.")
                continue

            print(f"Tú: {texto}")
            respuesta = procesar_comando(texto, confirmador=confirmar_por_voz)
            print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")
            hablar(respuesta.texto, motor=respuesta.motor)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
