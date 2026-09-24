"""Amplificación digital del audio capturado.

Algunos micrófonos entregan una señal débil incluso al volumen máximo de
Windows (caso real: un USB barato que solo llega al 18% en la prueba de
Windows con el volumen al 100%). En vez de perder precisión en Whisper y
en la detección de wake word, se amplifica la señal en software antes de
usarla. Configurable por si cambias de micrófono.
"""

import os

import numpy as np


def ganancia_microfono() -> float:
    """Factor de amplificación (1.0 = sin cambios). Configurable via GANANCIA_MICROFONO en .env."""
    try:
        return float(os.getenv("GANANCIA_MICROFONO", "3.0"))
    except ValueError:
        return 3.0


def amplificar(bloque: np.ndarray) -> np.ndarray:
    """Amplifica un bloque de audio float32 (-1.0 a 1.0), con protección contra saturación."""
    ganancia = ganancia_microfono()
    if ganancia == 1.0:
        return bloque
    return np.clip(bloque * ganancia, -1.0, 1.0)
