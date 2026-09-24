"""Reconocimiento de voz (STT) con Whisper local, modo push-to-talk.

Sin wake word todavía: el usuario presiona Enter para empezar a hablar y
Enter de nuevo para terminar. La activación por voz real queda para una
iteración futura de esta fase.
"""

import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

TASA_MUESTREO = 16000
TAMANO_MODELO = "base"

_modelo: WhisperModel | None = None


def _obtener_modelo() -> WhisperModel:
    global _modelo
    if _modelo is None:
        _modelo = WhisperModel(TAMANO_MODELO, device="cpu", compute_type="int8")
    return _modelo


def grabar_hasta_enter() -> np.ndarray:
    """Graba audio del micrófono hasta que el usuario presione Enter."""
    bloques: list[np.ndarray] = []
    bloqueo = threading.Lock()

    def callback(datos_entrada, frames, tiempo, estado):
        with bloqueo:
            bloques.append(datos_entrada.copy())

    with sd.InputStream(samplerate=TASA_MUESTREO, channels=1, dtype="float32", callback=callback):
        input()

    if not bloques:
        return np.zeros(0, dtype="float32")
    with bloqueo:
        return np.concatenate(bloques, axis=0).flatten()


def transcribir(audio: np.ndarray) -> str:
    """Transcribe un array de audio (mono, 16kHz, float32) a texto en español."""
    if audio.size == 0:
        return ""
    modelo = _obtener_modelo()
    segmentos, _info = modelo.transcribe(audio, language="es")
    return " ".join(segmento.text.strip() for segmento in segmentos).strip()


def escuchar_comando() -> str:
    """Flujo push-to-talk completo: graba hasta Enter y devuelve el texto transcrito."""
    input("Presiona Enter para hablar...")
    print("Grabando... presiona Enter para terminar.")
    audio = grabar_hasta_enter()
    print("Transcribiendo...")
    return transcribir(audio)
