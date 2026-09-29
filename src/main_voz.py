"""Punto de entrada de voz (Fase 3 + Fase 4, push-to-talk): escucha,
transcribe, decide motor/acción, responde por texto y por voz.

Reutiliza procesar_comando de src/main.py, así que el router, la
integración con Obsidian y las acciones son exactamente las mismas que en
el CLI de texto. Solo cambia cómo se pide confirmación: aquí, por voz.
"""

import sys

from src.actions.confirmacion import es_afirmativo
from src.agente.conversacion import Conversacion
from src.arranque import preparar
from src.main import procesar_comando
from src.router.intent_router import nombre_motor
from src.voice.stt import escuchar_comando
from src.voice.tts import hablar


def confirmar_por_voz(descripcion: str) -> bool:
    """Pide confirmación hablando la pregunta y escuchando la respuesta."""
    hablar(f"{descripcion} Di sí o no.")
    respuesta = escuchar_comando()
    return es_afirmativo(respuesta)


def main() -> None:
    preparar(sys.argv[1:])  # .env, bóveda y --pruebas (ver src/arranque.py)

    conversacion = Conversacion()
    print("Crimson y Clover (voz, Fase 3 + Fase 4 - push-to-talk). Ctrl+C para salir.")
    while True:
        try:
            texto = escuchar_comando()
            if not texto:
                print("[aviso] No se entendió nada, intenta de nuevo.")
                continue

            print(f"Tú: {texto}")
            respuesta = procesar_comando(texto, confirmador=confirmar_por_voz, conversacion=conversacion, canal="voz")
            print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")
            hablar(respuesta.texto, motor=respuesta.motor)
            if respuesta.cerrar:
                break
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
