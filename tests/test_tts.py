import queue
import threading
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


class _SalidaDeAudioFalsa:
    """Imita sd.OutputStream: pide bloques al callback hasta que este avisa que terminó."""

    niveles: list[float] = []

    def __init__(self, callback, finished_callback, medidor, **_kwargs):
        self._callback, self._terminar, self._medidor = callback, finished_callback, medidor

    def __enter__(self):
        salida = np.zeros((200, 1), dtype="float32")
        try:
            while True:
                self._callback(salida, 200, None, None)
                self.niveles.append(self._medidor.nivel)
        except sd.CallbackStop:
            pass
        self._terminar()
        return self

    def __exit__(self, *_args):
        return False


class _ColaConRetraso:
    """Como queue.Queue pero los primeros `retrasos` get_nowait() fallan, simulando que la síntesis aún no termina."""

    def __init__(self, items: list, retrasos: int) -> None:
        self._items = list(items)
        self._restantes_de_retraso = retrasos

    def get_nowait(self):
        if self._restantes_de_retraso > 0:
            self._restantes_de_retraso -= 1
            raise queue.Empty
        if not self._items:
            raise queue.Empty
        return self._items.pop(0)


def test_limpiar_para_voz_quita_markdown_viñetas_y_emojis():
    texto = "¡Claro! Tienes **3 pendientes**:\n- Comprar pan\n- [ ] Comprar leche\n1. Llamar al doctor 😊📞"

    limpio = tts.limpiar_para_voz(texto)

    assert limpio == "¡Claro! Tienes 3 pendientes: Comprar pan Comprar leche Llamar al doctor"


def test_limpiar_para_voz_conserva_el_texto_de_los_enlaces():
    assert tts.limpiar_para_voz("Mira [el clima](https://x.com) hoy") == "Mira el clima hoy"


def test_partir_en_oraciones_separa_por_puntuacion():
    assert tts._partir_en_oraciones("Hola. ¿Cómo estás? Bien!") == ["Hola.", "¿Cómo estás?", "Bien!"]


def test_partir_en_oraciones_sin_puntuacion_devuelve_todo_el_texto():
    assert tts._partir_en_oraciones("una sola frase sin puntos") == ["una sola frase sin puntos"]


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


# --- edge-tts (motor de síntesis, primera opción) ---


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


@patch("src.voice.tts.httpx.post")
def test_elevenlabs_manda_el_texto_recibido(mock_post, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_post.side_effect = httpx.ConnectError("sin conexion")

    tts._sintetizar_elevenlabs("Hola", None)

    assert mock_post.call_args.kwargs["json"]["text"] == "Hola"


@patch("src.voice.tts.decode_audio")
@patch("src.voice.tts.httpx.post")
def test_elevenlabs_usa_voz_del_motor_en_la_url(mock_post, _mock_decodificar, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID_GEMINI", "voz-gemini")
    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    tts._sintetizar_elevenlabs("hola", "gemini")

    url_llamada = mock_post.call_args.args[0]
    assert "voz-gemini" in url_llamada


def test_elevenlabs_sin_api_key_devuelve_none(monkeypatch, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    assert tts._sintetizar_elevenlabs("hola", None) is None
    assert "ELEVENLABS_API_KEY" in capsys.readouterr().out


# --- síntesis oración por oración (con cola de reproducción) ---


def test_sintetizar_oraciones_pone_cada_fragmento_en_la_cola_y_termina_con_el_centinela():
    cola = queue.Queue()
    with patch("src.voice.tts._sintetizar_edge_tts", side_effect=[np.array([1.0]), np.array([2.0])]):
        tts._sintetizar_oraciones(["Hola.", "Adiós."], None, cola)

    assert np.array_equal(cola.get(), [1.0])
    assert np.array_equal(cola.get(), [2.0])
    assert cola.get() is tts._FIN_DE_AUDIO


def test_sintetizar_oraciones_sigue_con_la_siguiente_si_una_oracion_falla_en_ambos_motores():
    cola = queue.Queue()
    with (
        patch("src.voice.tts._sintetizar_edge_tts", side_effect=[None, np.array([9.0])]),
        patch("src.voice.tts._sintetizar_elevenlabs", return_value=None),
    ):
        tts._sintetizar_oraciones(["falla.", "funciona."], None, cola)

    assert np.array_equal(cola.get(), [9.0])
    assert cola.get() is tts._FIN_DE_AUDIO


def test_sintetizar_oraciones_avisa_si_nada_se_pudo_sintetizar(capsys):
    cola = queue.Queue()
    with (
        patch("src.voice.tts._sintetizar_edge_tts", return_value=None),
        patch("src.voice.tts._sintetizar_elevenlabs", return_value=None),
    ):
        tts._sintetizar_oraciones(["hola"], None, cola)

    assert cola.get() is tts._FIN_DE_AUDIO
    assert "No se pudo sintetizar voz" in capsys.readouterr().out


# --- reproducción en secuencia ---


def test_reproducir_secuencia_reproduce_fragmentos_en_orden_sin_cortes():
    medidor = tts.MedidorDeVolumen()
    cola = queue.Queue()
    cola.put(np.full(300, 0.2, dtype="float32"))
    cola.put(np.full(300, 0.02, dtype="float32"))
    cola.put(tts._FIN_DE_AUDIO)
    _SalidaDeAudioFalsa.niveles = []

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts._reproducir_secuencia(cola, medidor)

    assert max(_SalidaDeAudioFalsa.niveles) == 1.0  # el fragmento fuerte sonó
    assert 0 < min(n for n in _SalidaDeAudioFalsa.niveles if n > 0) < 1.0  # el suave también, distinto del fuerte
    assert medidor.nivel == 0.0  # al terminar se apaga


def test_reproducir_secuencia_espera_sin_cortar_si_la_siguiente_oracion_tarda():
    """Mientras la próxima oración se sintetiza, debe rellenar con silencio, no terminar de golpe."""
    medidor = tts.MedidorDeVolumen()
    cola = _ColaConRetraso([np.full(300, 0.2, dtype="float32"), tts._FIN_DE_AUDIO], retrasos=3)
    _SalidaDeAudioFalsa.niveles = []

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts._reproducir_secuencia(cola, medidor)

    assert _SalidaDeAudioFalsa.niveles[0] == 0.0  # silencio mientras "tardaba", no corte
    assert max(_SalidaDeAudioFalsa.niveles) == 1.0  # la oración llegó y sonó después


def test_reproducir_secuencia_no_reproduce_nada_si_ya_esta_detenido():
    """Interrupción marcada antes de empezar (ej. al tocar el micrófono): no debe sonar nada."""
    medidor = tts.MedidorDeVolumen()
    detener = threading.Event()
    detener.set()
    cola = queue.Queue()
    cola.put(np.full(300, 0.2, dtype="float32"))
    cola.put(tts._FIN_DE_AUDIO)
    _SalidaDeAudioFalsa.niveles = []

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts._reproducir_secuencia(cola, medidor, detener)

    assert _SalidaDeAudioFalsa.niveles == []  # se detuvo en el primer callback, antes de sonar nada
    assert medidor.nivel == 0.0


def test_reproducir_secuencia_se_corta_al_activar_detener_a_medio_reproducir():
    medidor = tts.MedidorDeVolumen()
    detener = threading.Event()
    cola = queue.Queue()
    cola.put(np.full(100_000, 0.2, dtype="float32"))  # audio largo: si no se corta, tomaría muchas vueltas
    cola.put(tts._FIN_DE_AUDIO)
    _SalidaDeAudioFalsa.niveles = []

    class _SalidaQueInterrumpeTrasElPrimerBloque(_SalidaDeAudioFalsa):
        def __enter__(self):
            salida = np.zeros((200, 1), dtype="float32")
            try:
                self._callback(salida, 200, None, None)
                self.niveles.append(self._medidor.nivel)
                detener.set()  # el usuario interrumpe justo después del primer bloque reproducido
                while True:
                    self._callback(salida, 200, None, None)
                    self.niveles.append(self._medidor.nivel)
            except sd.CallbackStop:
                pass
            self._terminar()
            return self

    with patch(
        "src.voice.tts.sd.OutputStream",
        side_effect=lambda **kw: _SalidaQueInterrumpeTrasElPrimerBloque(medidor=medidor, **kw),
    ):
        tts._reproducir_secuencia(cola, medidor, detener)

    assert len(_SalidaDeAudioFalsa.niveles) <= 2  # se cortó casi de inmediato, no consumió el audio "largo"
    assert medidor.nivel == 0.0


def test_sintetizar_oraciones_se_detiene_si_lo_interrumpen():
    detener = threading.Event()

    def falso_edge_tts(oracion, _motor):
        if oracion == "Segunda.":
            detener.set()  # se interrumpe mientras se sintetiza esta oración
        return np.array([1.0])

    cola = queue.Queue()
    with patch("src.voice.tts._sintetizar_edge_tts", side_effect=falso_edge_tts):
        tts._sintetizar_oraciones(["Primera.", "Segunda.", "Tercera."], None, cola, detener)

    fragmentos = []
    while (item := cola.get()) is not tts._FIN_DE_AUDIO:
        fragmentos.append(item)
    assert len(fragmentos) == 2  # "Tercera." ya no se sintetiza: se marcó la interrupción antes de llegar a ella


def test_reproducir_secuencia_sin_medidor_no_crashea():
    cola = queue.Queue()
    cola.put(np.full(300, 0.2, dtype="float32"))
    cola.put(tts._FIN_DE_AUDIO)

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=MagicMock(nivel=0.0), **kw)):
        tts._reproducir_secuencia(cola, None)


# --- hablar() de punta a punta ---


@patch("src.voice.tts._sintetizar_edge_tts")
def test_hablar_reproduce_con_edge_tts_sin_tocar_elevenlabs(mock_edge, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    mock_edge.return_value = np.full(300, 0.2, dtype="float32")
    medidor = tts.MedidorDeVolumen()
    _SalidaDeAudioFalsa.niveles = []

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts.hablar("Hola mundo.", medidor=medidor)

    assert max(_SalidaDeAudioFalsa.niveles) == 1.0
    assert medidor.nivel == 0.0


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
@patch("src.voice.tts.httpx.post")
def test_hablar_cae_a_elevenlabs_si_edge_tts_falla(mock_post, _mock_edge, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")
    mock_respuesta = MagicMock()
    mock_respuesta.content = b"contenido-mp3-falso"
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta
    medidor = tts.MedidorDeVolumen()
    _SalidaDeAudioFalsa.niveles = []

    with (
        patch("src.voice.tts.decode_audio", return_value=np.full(300, 0.2, dtype="float32")),
        patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)),
    ):
        tts.hablar("hola mundo", medidor=medidor)

    mock_post.assert_called_once()
    assert max(_SalidaDeAudioFalsa.niveles) == 1.0


@patch("src.voice.tts._sintetizar_edge_tts", return_value=None)
def test_hablar_sin_ninguna_opcion_disponible_no_crashea(_mock_edge, monkeypatch, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    medidor = tts.MedidorDeVolumen()

    with patch("src.voice.tts.sd.OutputStream", side_effect=lambda **kw: _SalidaDeAudioFalsa(medidor=medidor, **kw)):
        tts.hablar("hola", medidor=medidor)

    salida = capsys.readouterr().out
    assert "ELEVENLABS_API_KEY" in salida
    assert "hola" in salida
