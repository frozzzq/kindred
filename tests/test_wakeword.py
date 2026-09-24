from unittest.mock import MagicMock, patch

import numpy as np

from src.voice import wakeword


@patch("src.voice.wakeword._obtener_modelo")
@patch("src.voice.wakeword.sd.InputStream")
def test_esperar_wake_word_detecta_y_desbloquea(mock_input_stream, mock_obtener_modelo):
    modelo_mock = MagicMock()
    modelo_mock.predict.return_value = {"hey_jarvis": 0.9}
    mock_obtener_modelo.return_value = modelo_mock

    mock_stream = MagicMock()
    mock_input_stream.return_value.__enter__.return_value = mock_stream

    def simular_callback_al_dormir(*_args, **_kwargs):
        callback = mock_input_stream.call_args.kwargs["callback"]
        audio = np.zeros((wakeword.TAMANO_BLOQUE, 1), dtype="float32")
        callback(audio, wakeword.TAMANO_BLOQUE, None, None)

    with patch("src.voice.wakeword.sd.sleep", side_effect=simular_callback_al_dormir):
        wakeword.esperar_wake_word()

    modelo_mock.reset.assert_called_once()
    modelo_mock.predict.assert_called()
