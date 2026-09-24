"""Detección de wake word ("hey jarvis") local con openWakeWord.

Fase 3 (mejora sobre push-to-talk): activación por voz sin presionar
Enter. Modelo pre-entrenado, 100% local, sin costo ni API key — y
openWakeWord trae literalmente un modelo llamado "hey_jarvis".
"""

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

TASA_MUESTREO = 16000
TAMANO_BLOQUE = 1280  # openWakeWord espera bloques de 80ms a 16kHz
UMBRAL_DETECCION = 0.3  # ajustado tras pruebas reales: 0.5 nunca se alcanzaba con este micrófono

_modelo: Model | None = None


def _obtener_modelo() -> Model:
    global _modelo
    if _modelo is None:
        _modelo = Model(wakeword_models=["hey_jarvis"])
    return _modelo


def esperar_wake_word() -> None:
    """Bloquea hasta escuchar "hey jarvis" por el micrófono."""
    modelo = _obtener_modelo()
    modelo.reset()
    detectada = False

    def callback(datos_entrada, frames, tiempo, estado):
        nonlocal detectada
        if detectada:
            return
        audio_int16 = (datos_entrada[:, 0] * 32767).astype(np.int16)
        predicciones = modelo.predict(audio_int16)
        if predicciones.get("hey_jarvis", 0.0) >= UMBRAL_DETECCION:
            detectada = True

    with sd.InputStream(
        samplerate=TASA_MUESTREO,
        channels=1,
        dtype="float32",
        blocksize=TAMANO_BLOQUE,
        callback=callback,
    ):
        while not detectada:
            sd.sleep(50)
