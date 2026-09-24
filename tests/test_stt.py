from unittest.mock import MagicMock, patch

import numpy as np

from src.voice import stt


def test_transcribir_audio_vacio_devuelve_cadena_vacia():
    assert stt.transcribir(np.zeros(0, dtype="float32")) == ""


@patch("src.voice.stt._obtener_modelo")
def test_transcribir_une_segmentos(mock_obtener_modelo):
    segmento_1 = MagicMock(text=" hola ")
    segmento_2 = MagicMock(text="mundo ")
    modelo_mock = MagicMock()
    modelo_mock.transcribe.return_value = ([segmento_1, segmento_2], None)
    mock_obtener_modelo.return_value = modelo_mock

    resultado = stt.transcribir(np.ones(10, dtype="float32"))

    assert resultado == "hola mundo"
