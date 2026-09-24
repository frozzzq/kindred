"""Punto de entrada de voz (Fase 3, push-to-talk): escucha, transcribe,
decide motor, responde por texto y por voz.

Reutiliza procesar_comando de src/main.py, así que el router y la
integración con Obsidian son exactamente los mismos que en el CLI de texto.
"""

from dotenv import load_dotenv

from src.main import procesar_comando
from src.obsidian.estructura import asegurar_estructura_boveda
from src.voice.stt import escuchar_comando
from src.voice.tts import hablar


def main() -> None:
    load_dotenv()
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    print("Jarvis (voz, Fase 3 - push-to-talk). Ctrl+C para salir.")
    while True:
        try:
            texto = escuchar_comando()
        except KeyboardInterrupt:
            break

        if not texto:
            print("[aviso] No se entendió nada, intenta de nuevo.")
            continue

        print(f"Tú: {texto}")
        respuesta = procesar_comando(texto)
        print(f"Jarvis ({respuesta.motor}): {respuesta.texto}")
        hablar(respuesta.texto, motor=respuesta.motor)


if __name__ == "__main__":
    main()
