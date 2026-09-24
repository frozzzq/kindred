from unittest.mock import MagicMock, patch

import httpx

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


@patch("src.voice.tts.playsound")
@patch("src.voice.tts.httpx.post")
def test_hablar_reproduce_audio_exitoso(mock_post, mock_playsound, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")

    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    tts.hablar("hola mundo")

    mock_post.assert_called_once()
    mock_playsound.assert_called_once()


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


@patch("src.voice.tts.playsound")
@patch("src.voice.tts.httpx.post")
def test_hablar_usa_voz_del_motor_en_la_url(mock_post, mock_playsound, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_GEMINI", "voz-gemini")

    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    tts.hablar("hola", motor="gemini")

    url_llamada = mock_post.call_args.args[0]
    assert "voz-gemini" in url_llamada
