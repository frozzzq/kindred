"""Reconocimiento de voz (STT) con Whisper local.

Dos formas de grabar:
- grabar_hasta_enter(): push-to-talk manual (Fase 3 original).
- grabar_hasta_silencio(): automática, para usarse después de la wake word
  (Fase 3, mejora) — empieza a contar en cuanto detecta voz y para sola
  tras un silencio, sin necesidad de presionar Enter.
"""

import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

TASA_MUESTREO = 16000
TAMANO_MODELO = "base"

TAMANO_BLOQUE = 1600  # 100 ms a 16kHz
UMBRAL_RMS_VOZ = 0.02
BLOQUES_SILENCIO_PARA_PARAR = 12  # ~1.2s de silencio tras haber hablado
DURACION_MAXIMA_SEGUNDOS = 15

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


class Grabadora:
    """Grabación que se inicia y detiene desde fuera (ej. un botón de UI que se toca dos veces)."""

    def __init__(self) -> None:
        self._bloques: list[np.ndarray] = []
        self._bloqueo = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def grabando(self) -> bool:
        return self._stream is not None

    def iniciar(self) -> None:
        with self._bloqueo:
            self._bloques = []

        def callback(datos_entrada, frames, tiempo, estado):
            with self._bloqueo:
                self._bloques.append(datos_entrada.copy())

        self._stream = sd.InputStream(samplerate=TASA_MUESTREO, channels=1, dtype="float32", callback=callback)
        self._stream.start()

    def detener(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype="float32")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._bloqueo:
            if not self._bloques:
                return np.zeros(0, dtype="float32")
            return np.concatenate(self._bloques, axis=0).flatten()


def grabar_hasta_silencio() -> np.ndarray:
    """Graba automáticamente: empieza a contar al detectar voz, para tras un silencio."""
    bloques: list[np.ndarray] = []
    bloqueo = threading.Lock()
    detener = threading.Event()
    estado = {"hablo": False, "bloques_silencio": 0, "total_bloques": 0}

    def callback(datos_entrada, frames, tiempo, flags):
        with bloqueo:
            bloques.append(datos_entrada.copy())
            rms = float(np.sqrt(np.mean(datos_entrada**2)))
            estado["total_bloques"] += 1

            if rms >= UMBRAL_RMS_VOZ:
                estado["hablo"] = True
                estado["bloques_silencio"] = 0
            elif estado["hablo"]:
                estado["bloques_silencio"] += 1

            duracion_transcurrida = estado["total_bloques"] * TAMANO_BLOQUE / TASA_MUESTREO
            silencio_terminado = estado["hablo"] and estado["bloques_silencio"] >= BLOQUES_SILENCIO_PARA_PARAR
            if silencio_terminado or duracion_transcurrida >= DURACION_MAXIMA_SEGUNDOS:
                detener.set()

    with sd.InputStream(
        samplerate=TASA_MUESTREO,
        channels=1,
        dtype="float32",
        blocksize=TAMANO_BLOQUE,
        callback=callback,
    ):
        while not detener.is_set():
            sd.sleep(50)

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


def escuchar_comando_automatico() -> str:
    """Graba automáticamente (sin Enter) hasta detectar silencio y transcribe."""
    audio = grabar_hasta_silencio()
    return transcribir(audio)
