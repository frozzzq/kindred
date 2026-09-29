"""Punto de entrada de voz manos libres (Fase 3, mejora sobre push-to-talk):
espera la wake word "hey jarvis", graba automáticamente hasta silencio,
transcribe, decide motor/acción, responde por texto y por voz.

Reutiliza procesar_comando de src/main.py. Si prefieres el modo manual
(presionar Enter), usa src/main_voz.py en su lugar — ambos coexisten.
"""

import sys

from src.actions.confirmacion import es_afirmativo
from src.agente.conversacion import Conversacion
from src.arranque import preparar
from src.main import procesar_comando
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
    preparar(sys.argv[1:])  # .env, bóveda y --pruebas (ver src/arranque.py)

    conversacion = Conversacion()
    # "hey jarvis" es solo la palabra de activación del modelo pre-entrenado de openWakeWord (no
    # hay uno propio para "Crimson"/"Clover"; ver "Fuera de alcance" en CLAUDE.md), no el nombre
    # de ningún agente.
    print('Crimson y Clover (voz manos libres, Fase 3). Di "hey jarvis" para activar. Ctrl+C para salir.')
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
            respuesta = procesar_comando(texto, confirmador=confirmar_por_voz, conversacion=conversacion, canal="voz")
            print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")
            hablar(respuesta.texto, motor=respuesta.motor)
            if respuesta.cerrar:
                break
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
