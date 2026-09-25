"""Escucha continua del micrófono, partida en frases por volumen.

Cada frase detectada (voz seguida de ~1.2s de silencio) se entrega a un
callback para transcribirla; qué hacer con ella (si llamaron al agente por
su nombre, si la ventana de conversación sigue abierta) lo decide
src/voice/activacion.py.

Se puede pausar: mientras el agente habla por las bocinas hay que dejar de
escuchar, o se oiría a sí mismo y se contestaría en bucle.
"""

import threading
from collections import deque
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from src.voice.audio import amplificar
from src.voice.stt import BLOQUES_SILENCIO_PARA_PARAR, TAMANO_BLOQUE, TASA_MUESTREO, UMBRAL_RMS_VOZ

BLOQUES_PREVIOS = 3  # 300 ms de audio previo, para no cortar el inicio de la primera palabra
MIN_BLOQUES_CON_VOZ = 3  # menos de 300 ms con voz es un golpe o un clic, no una frase
MAX_BLOQUES_POR_FRASE = 150  # 15 s: corta frases eternas (ruido constante)


class SegmentadorDeFrases:
    """Acumula bloques de audio y devuelve una frase completa cuando termina."""

    def __init__(self) -> None:
        self._previos: deque[np.ndarray] = deque(maxlen=BLOQUES_PREVIOS)
        self._frase: list[np.ndarray] = []
        self._con_voz = 0
        self._silencio = 0

    def reiniciar(self) -> None:
        self._previos.clear()
        self._frase = []
        self._con_voz = 0
        self._silencio = 0

    def agregar(self, bloque: np.ndarray) -> np.ndarray | None:
        """Procesa un bloque; devuelve la frase completa si con este bloque terminó."""
        hay_voz = float(np.sqrt(np.mean(bloque**2))) >= UMBRAL_RMS_VOZ
        if not self._frase:
            if not hay_voz:
                self._previos.append(bloque)
                return None
            self._frase = list(self._previos)
            self._previos.clear()

        self._frase.append(bloque)
        if hay_voz:
            self._con_voz += 1
            self._silencio = 0
        else:
            self._silencio += 1

        if self._silencio < BLOQUES_SILENCIO_PARA_PARAR and len(self._frase) < MAX_BLOQUES_POR_FRASE:
            return None
        frase, con_voz = self._frase, self._con_voz
        self.reiniciar()
        if con_voz < MIN_BLOQUES_CON_VOZ:
            return None
        return np.concatenate(frase)


class EscuchaContinua:
    def __init__(self, al_escuchar: Callable[[np.ndarray], None]) -> None:
        self._al_escuchar = al_escuchar
        self._segmentador = SegmentadorDeFrases()
        self._stream: sd.InputStream | None = None
        self._pausada = False

    @property
    def activa(self) -> bool:
        return self._stream is not None

    def iniciar(self) -> None:
        if self._stream is not None:
            return
        self._pausada = False
        self._segmentador.reiniciar()
        self._stream = sd.InputStream(
            samplerate=TASA_MUESTREO,
            channels=1,
            dtype="float32",
            blocksize=TAMANO_BLOQUE,
            callback=self._callback,
        )
        self._stream.start()

    def detener(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def pausar(self) -> None:
        self._pausada = True

    def reanudar(self) -> None:
        self._pausada = False

    def _callback(self, datos_entrada, frames, tiempo, estado) -> None:
        if self._pausada:
            # Se descarta lo que estaba a medias: incluiría la voz del propio agente.
            self._segmentador.reiniciar()
            return
        frase = self._segmentador.agregar(amplificar(datos_entrada[:, 0].copy()))
        if frase is not None:
            threading.Thread(target=self._al_escuchar, args=(frase,), daemon=True).start()
