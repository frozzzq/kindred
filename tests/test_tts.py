from unittest.mock import MagicMock, patch

import edge_tts
import httpx
import numpy as np
import sounddevice as sd

from src.voice import tts


class _ComunicadorFalso:
    """Imita edge_tts.Communicate: entrega los fragmentos dados al iterar stream()."""

    def __init__(self, *_args, fragmentos=(), **_kwargs):
        self._fragmentos = fragmentos

    async def stream(self):
        for fragmento in self._fragmentos:
            yield fragmento


def test_limpiar_para_voz_quita_markdown_viñetas_y_emojis():
    texto = "¡Claro! Tienes **3 pendientes**:\n- Comprar pan\n- [ ] Comprar leche\n1. Llamar al doctor 😊📞"

    limpio = tts.limpiar_para_voz(texto)

    assert limpio == "¡Claro! Tienes 3 pendientes: Comprar pan Comprar leche Llamar al doctor"


def test_limpiar_para_voz_conserva_el_texto_de_los_enlaces():
    assert tts.limpiar_para_voz("Mira [el clima](https://x.com) hoy") == "Mira el clima hoy"


def test_elegir_voz_usa_variable_especifica_del_motor(monkeypatch):
    monkeypatch.setenv("VOZ_OLLAMA", "voz-ollama")

    voz = tts._elegir_voz("ollama", {"ollama": "VOZ_OLLAMA"}, "VOZ_GENERICA", "voz-default")

    assert voz == "voz-ollama"


def test_elegir_voz_cae_a_generica_si_falta_la_especifica(monkeypatch):
    monkeypatch.delenv("VOZ_OLLAMA", raising=False)
    monkeypatch.setenv("VOZ_GENERICA", "voz-generica")

    voz = tts._elegir_voz("ollama", {"ollama": "VOZ_OLLAMA"}, "VOZ_GENERICA", "voz-default")

    assert voz == "voz-generica"


def test_elegir_voz_cae_a_default_sin_nada_configurado(monkeypatch):
    monkeypatch.delenv("VOZ_GENERICA", raising=False)

    voz = tts._elegir_voz(None, {}, "VOZ_GENERICA", "voz-default")

    assert voz == "voz-default"


# --- edge-tts (primera opción) ---


@patch("src.voice.tts._reproducir")
@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
@patch("src.voice.tts.edge_tts.Communicate")
def test_hablar_usa_edge_tts_primero_sin_necesitar_elevenlabs(
    mock_comunicador_cls, mock_post, mock_decodificar, mock_reproducir, monkeypatch
):
    """edge-tts no necesita API key: debe funcionar aunque ElevenLabs no esté configurado."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    mock_comunicador_cls.return_value = _ComunicadorFalso(fragmentos=[{"type": "audio", "data": b"abc"}])
    medidor = tts.MedidorDeVolumen()

    tts.hablar("hola mundo", medidor=medidor)

    mock_post.assert_not_called()
    mock_reproducir.assert_called_once_with(mock_decodificar.return_value, medidor)


@patch("src.voice.tts.edge_tts.Communicate")
def test_hablar_manda_el_texto_ya_limpio_a_edge_tts(mock_comunicador_cls):
    mock_comunicador_cls.return_value = _ComunicadorFalso(fragmentos=[{"type": "audio", "data": b"x"}])

    with patch("src.voice.tts.decode_audio"), patch("src.voice.tts._reproducir"):
        tts.hablar("**Hola** 😊")

    assert mock_comunicador_cls.call_args.args[0] == "Hola"


@patch("src.voice.tts.edge_tts.Communicate")
def test_sintetizar_edge_tts_usa_la_voz_del_motor(mock_comunicador_cls, monkeypatch):
    monkeypatch.setenv("EDGE_TTS_VOICE_GEMINI", "es-ES-VoiceX")
    mock_comunicador_cls.return_value = _ComunicadorFalso(fragmentos=[{"type": "audio", "data": b"x"}])

    with patch("src.voice.tts.decode_audio"):
        tts._sintetizar_edge_tts("hola", "gemini")

    assert mock_comunicador_cls.call_args.args[1] == "es-ES-VoiceX"


@patch("src.voice.tts.edge_tts.Communicate")
def test_sintetizar_edge_tts_sin_audio_devuelve_none(mock_comunicador_cls):
    mock_comunicador_cls.return_value = _ComunicadorFalso(fragmentos=[])

    assert tts._sintetizar_edge_tts("hola", None) is None


@patch("src.voice.tts.edge_tts.Communicate")
def test_sintetizar_edge_tts_error_de_red_devuelve_none(mock_comunicador_cls, capsys):
    mock_comunicador_cls.side_effect = edge_tts.exceptions.WebSocketError("sin conexión")

    resultado = tts._sintetizar_edge_tts("hola", None)

    assert resultado is None
    assert "edge-tts falló" in capsys.readouterr().out


# --- ElevenLabs (respaldo) ---


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
@patch("src.voice.tts._reproducir")
@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
def test_si_edge_tts_falla_cae_a_elevenlabs(mock_post, mock_decodificar, mock_reproducir, _mock_edge, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta
    medidor = tts.MedidorDeVolumen()

    tts.hablar("hola mundo", medidor=medidor)

    mock_post.assert_called_once()
    mock_reproducir.assert_called_once_with(mock_decodificar.return_value, medidor)


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
@patch("src.voice.tts.httpx.post")
def test_elevenlabs_manda_el_texto_ya_limpio(mock_post, _mock_edge, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_post.side_effect = httpx.ConnectError("sin conexion")

    tts.hablar("**Hola** 😊")

    assert mock_post.call_args.kwargs["json"]["text"] == "Hola"


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
@patch("src.voice.tts._reproducir")
@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
def test_elevenlabs_usa_voz_del_motor_en_la_url(mock_post, _mock_decodificar, _mock_reproducir, _mock_edge, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_GEMINI", "voz-gemini")
    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    tts.hablar("hola", motor="gemini")

    url_llamada = mock_post.call_args.args[0]
    assert "voz-gemini" in url_llamada


# --- ambos fallan ---


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
def test_hablar_sin_ninguna_opcion_disponible_no_crashea(_mock_edge, monkeypatch, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    tts.hablar("hola")

    salida = capsys.readouterr().out
    assert "ELEVENLABS_API_KEY" in salida
    assert "hola" in salida


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
@patch("src.voice.tts.httpx.post")
def test_hablar_error_http_de_elevenlabs_no_crashea(mock_post, _mock_edge, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_post.side_effect = httpx.ConnectError("sin conexion")

    tts.hablar("hola")

    salida = capsys.readouterr().out
    assert "hola" in salida


# --- reproducción ---


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
