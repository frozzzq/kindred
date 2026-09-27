from unittest.mock import MagicMock, patch

import httpx
import numpy as np
import sounddevice as sd

from src.voice import tts


def test_limpiar_para_voz_quita_markdown_viñetas_y_emojis():
    texto = "¡Claro! Tienes **3 pendientes**:\n- Comprar pan\n- [ ] Comprar leche\n1. Llamar al doctor 😊📞"

    limpio = tts.limpiar_para_voz(texto)

    assert limpio == "¡Claro! Tienes 3 pendientes: Comprar pan Comprar leche Llamar al doctor"


def test_limpiar_para_voz_conserva_el_texto_de_los_enlaces():
    assert tts.limpiar_para_voz("Mira [el clima](https://x.com) hoy") == "Mira el clima hoy"


@patch("src.voice.tts.httpx.post")
def test_hablar_manda_el_texto_ya_limpio(mock_post, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_post.side_effect = httpx.ConnectError("sin conexion")

    tts.hablar("**Hola** 😊")

    assert mock_post.call_args.kwargs["json"]["text"] == "Hola"


@patch("src.voice.tts._reproducir")
@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
def test_hablar_reproduce_audio_exitoso(mock_post, mock_decodificar, mock_reproducir, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")

    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta
    medidor = tts.MedidorDeVolumen()

    tts.hablar("hola mundo", medidor=medidor)

    mock_post.assert_called_once()
    mock_reproducir.assert_called_once_with(mock_decodificar.return_value, medidor)


class _SalidaDeAudioFalsa:
    """Imita sd.OutputStream: pide bloques al callback hasta que este avisa que terminó."""

    niveles: list[float] = []

    def __init__(self, callback, finished_callback, medidor, **_kwargs):
        self._callback, self._terminar, self._medidor = callback, finished_callback, medidor

    def __enter__(self):
        salida = np.zeros((1000, 1), dtype="float32")
        try:
            while True:
                self._callback(salida, 1000, None, None)
                self.niveles.append(self._medidor.nivel)
        except sd.CallbackStop:
            pass
        self._terminar()
        return self

    def __exit__(self, *_args):
        return False


def test_reproducir_publica_el_volumen_de_lo_que_suena_y_termina_en_cero():
    medidor = tts.MedidorDeVolumen()
    audio = np.concatenate([np.full(2000, 0.2, dtype="float32"), np.full(2000, 0.02, dtype="float32"), np.zeros(500, dtype="float32")])
    _SalidaDeAudioFalsa.niveles = []

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts._reproducir(audio, medidor)

    fuerte, _, suave, _ = _SalidaDeAudioFalsa.niveles
    assert fuerte == 1.0  # voz fuerte: brillo al máximo
    assert 0 < suave < 0.2  # voz suave: brillo bajo, no un simple encendido/apagado
    assert medidor.nivel == 0.0  # al terminar de hablar se apaga


def test_hablar_sin_api_key_no_crashea(monkeypatch, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    tts.hablar("hola")

    salida = capsys.readouterr().out
    assert "ELEVENLABS_API_KEY" in salida


@patch("src.voice.tts.httpx.post")
def test_hablar_error_http_no_crashea(mock_post, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_post.side_effect = httpx.ConnectError("sin conexion")

    tts.hablar("hola")

    salida = capsys.readouterr().out
    assert "hola" in salida


def test_elegir_voz_usa_variable_especifica_de_ollama(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_OLLAMA", "voz-ollama")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_GEMINI", "voz-gemini")

    assert tts._elegir_voz("ollama") == "voz-ollama"
    assert tts._elegir_voz("gemini") == "voz-gemini"


def test_elegir_voz_cae_a_generica_si_falta_la_especifica(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_VOICE_ID_OLLAMA", raising=False)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voz-generica")

    assert tts._elegir_voz("ollama") == "voz-generica"


def test_elegir_voz_cae_a_default_sin_nada_configurado(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_VOICE_ID_OLLAMA", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID_GEMINI", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    assert tts._elegir_voz(None) == tts.VOZ_POR_DEFECTO


@patch("src.voice.tts._reproducir")
@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
def test_hablar_usa_voz_del_motor_en_la_url(mock_post, _mock_decodificar, _mock_reproducir, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_GEMINI", "voz-gemini")

    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    tts.hablar("hola", motor="gemini")

    url_llamada = mock_post.call_args.args[0]
    assert "voz-gemini" in url_llamada
