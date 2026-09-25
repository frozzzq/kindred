from unittest.mock import patch

import numpy as np

from src.voice import escucha_continua
from src.voice.escucha_continua import (
    BLOQUES_PREVIOS,
    MAX_BLOQUES_POR_FRASE,
    EscuchaContinua,
    SegmentadorDeFrases,
)
from src.voice.stt import BLOQUES_SILENCIO_PARA_PARAR, TAMANO_BLOQUE

VOZ = np.full(TAMANO_BLOQUE, 0.3, dtype="float32")
SILENCIO = np.zeros(TAMANO_BLOQUE, dtype="float32")


def _alimentar(segmentador, bloques):
    return [f for f in (segmentador.agregar(b) for b in bloques) if f is not None]


def test_una_frase_termina_tras_el_silencio():
    segmentador = SegmentadorDeFrases()

    frases = _alimentar(segmentador, [SILENCIO] * 5 + [VOZ] * 10 + [SILENCIO] * BLOQUES_SILENCIO_PARA_PARAR)

    assert len(frases) == 1
    # incluye el audio previo a la voz (para no cortar la primera palabra) y la voz completa
    assert frases[0].size == (BLOQUES_PREVIOS + 10 + BLOQUES_SILENCIO_PARA_PARAR) * TAMANO_BLOQUE


def test_solo_silencio_no_produce_frases():
    assert _alimentar(SegmentadorDeFrases(), [SILENCIO] * 100) == []


def test_un_golpe_corto_no_es_una_frase():
    assert _alimentar(SegmentadorDeFrases(), [VOZ] * 2 + [SILENCIO] * BLOQUES_SILENCIO_PARA_PARAR) == []


def test_una_pausa_corta_no_parte_la_frase():
    bloques = [VOZ] * 5 + [SILENCIO] * (BLOQUES_SILENCIO_PARA_PARAR - 2) + [VOZ] * 5 + [SILENCIO] * BLOQUES_SILENCIO_PARA_PARAR

    assert len(_alimentar(SegmentadorDeFrases(), bloques)) == 1


def test_ruido_constante_se_corta_en_el_maximo():
    frases = _alimentar(SegmentadorDeFrases(), [VOZ] * (MAX_BLOQUES_POR_FRASE + 1))

    assert len(frases) == 1


@patch.object(escucha_continua, "amplificar", side_effect=lambda bloque: bloque)
@patch("src.voice.escucha_continua.threading.Thread")
def test_pausada_no_escucha_nada(mock_hilo, _amplificar):
    """Mientras el agente habla no debe oírse a sí mismo."""
    escucha = EscuchaContinua(al_escuchar=lambda audio: None)
    escucha.pausar()

    for bloque in [VOZ] * 10 + [SILENCIO] * BLOQUES_SILENCIO_PARA_PARAR:
        escucha._callback(bloque.reshape(-1, 1), TAMANO_BLOQUE, None, None)

    mock_hilo.assert_not_called()


@patch.object(escucha_continua, "amplificar", side_effect=lambda bloque: bloque)
@patch("src.voice.escucha_continua.threading.Thread")
def test_entrega_la_frase_al_callback(mock_hilo, _amplificar):
    recibido = []
    escucha = EscuchaContinua(al_escuchar=recibido.append)

    for bloque in [VOZ] * 10 + [SILENCIO] * BLOQUES_SILENCIO_PARA_PARAR:
        escucha._callback(bloque.reshape(-1, 1), TAMANO_BLOQUE, None, None)

    mock_hilo.assert_called_once()
    assert mock_hilo.call_args.kwargs["target"] == recibido.append
