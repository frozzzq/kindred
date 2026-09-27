"""Detección de actividad de voz (VAD) con Silero VAD, embebido en faster-whisper.

Reemplaza el umbral de energía RMS: un ruido de fondo amplificado por
GANANCIA_MICROFONO puede superar cualquier umbral fijo de volumen, pero Silero
reconoce patrones acústicos de voz humana real, no solo el nivel de la señal.
"""

import numpy as np
from faster_whisper.vad import get_vad_model

TAMANO_VENTANA = 512  # tamaño de bloque nativo de Silero VAD (32ms a 16kHz)
UMBRAL_PROBABILIDAD_VOZ = 0.5
_TAMANO_CONTEXTO = 64

_modelo = None


def _obtener_sesion():
    global _modelo
    if _modelo is None:
        _modelo = get_vad_model()
    return _modelo.session


class DetectorDeVoz:
    """Envuelve el modelo ONNX de Silero VAD, manteniendo su estado (LSTM) entre bloques.

    Cada instancia representa una sesión de escucha: llamar a reiniciar() antes
    de empezar a grabar de nuevo evita arrastrar el estado de la frase anterior.
    """

    def __init__(self) -> None:
        self._sesion = _obtener_sesion()
        self.reiniciar()

    def reiniciar(self) -> None:
        self._h = np.zeros((1, 1, 128), dtype="float32")
        self._c = np.zeros((1, 1, 128), dtype="float32")
        self._contexto = np.zeros((1, _TAMANO_CONTEXTO), dtype="float32")

    def es_voz(self, bloque: np.ndarray) -> bool:
        """bloque: TAMANO_VENTANA muestras (float32, mono, 16kHz)."""
        entrada = np.concatenate([self._contexto, bloque[None, :]], axis=1).astype("float32")
        salida, self._h, self._c = self._sesion.run(None, {"input": entrada, "h": self._h, "c": self._c})
        self._contexto = bloque[None, -_TAMANO_CONTEXTO:].astype("float32")
        return float(salida[0]) >= UMBRAL_PROBABILIDAD_VOZ
