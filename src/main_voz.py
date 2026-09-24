"""Punto de entrada de voz (Fase 3 + Fase 4, push-to-talk): escucha,
transcribe, decide motor/acción, responde por texto y por voz.

Reutiliza procesar_comando de src/main.py, así que el router, la
integración con Obsidian y las acciones son exactamente las mismas que en
el CLI de texto. Solo cambia cómo se pide confirmación: aquí, por voz.
"""

from dotenv import load_dotenv

from src.actions.confirmacion import es_afirmativo
from src.consola import forzar_utf8
from src.main import procesar_comando
from src.obsidian.estructura import asegurar_estructura_boveda
from src.router.intent_router import nombre_motor
from src.voice.stt import escuchar_comando
from src.voice.tts import hablar


def confirmar_por_voz(descripcion: str) -> bool:
    """Pide confirmación hablando la pregunta y escuchando la respuesta."""
    hablar(f"{descripcion} Di sí o no.")
    respuesta = escuchar_comando()
    return es_afirmativo(respuesta)


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

    print("Jarvis (voz, Fase 3 + Fase 4 - push-to-talk). Ctrl+C para salir.")
    while True:
        try:
            texto = escuchar_comando()
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
