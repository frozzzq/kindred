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


@patch("src.voice.stt.sd.InputStream")
def test_grabar_hasta_silencio_para_tras_hablar_y_callar(mock_input_stream):
    mock_input_stream.return_value.__enter__.return_value = MagicMock()

    bloque_voz = np.full((stt.TAMANO_BLOQUE, 1), 0.5, dtype="float32")
    bloque_silencio = np.zeros((stt.TAMANO_BLOQUE, 1), dtype="float32")

    def simular_callbacks(*_args, **_kwargs):
        callback = mock_input_stream.call_args.kwargs["callback"]
        callback(bloque_voz, stt.TAMANO_BLOQUE, None, None)
        for _ in range(stt.BLOQUES_SILENCIO_PARA_PARAR):
            callback(bloque_silencio, stt.TAMANO_BLOQUE, None, None)

    with patch("src.voice.stt.sd.sleep", side_effect=simular_callbacks):
        audio = stt.grabar_hasta_silencio()

    assert audio.size > 0


@patch("src.voice.stt.sd.InputStream")
def test_grabadora_inicia_y_detiene_devolviendo_el_audio(mock_input_stream):
    grabadora = stt.Grabadora()
    grabadora.iniciar()
    assert grabadora.grabando is True

    callback = mock_input_stream.call_args.kwargs["callback"]
    callback(np.full((1600, 1), 0.5, dtype="float32"), 1600, None, None)
    callback(np.full((1600, 1), 0.2, dtype="float32"), 1600, None, None)

    audio = grabadora.detener()

    assert grabadora.grabando is False
    assert audio.shape == (3200,)
    mock_input_stream.return_value.stop.assert_called_once()
    mock_input_stream.return_value.close.assert_called_once()


def test_grabadora_detener_sin_iniciar_devuelve_vacio():
    assert stt.Grabadora().detener().size == 0


@patch("src.voice.stt.transcribir", return_value="hola")
@patch("src.voice.stt.grabar_hasta_silencio")
def test_escuchar_comando_automatico_graba_y_transcribe(mock_grabar, mock_transcribir):
    mock_grabar.return_value = np.ones(10, dtype="float32")

    resultado = stt.escuchar_comando_automatico()

    assert resultado == "hola"
    mock_grabar.assert_called_once()
