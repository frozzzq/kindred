import json
from unittest.mock import patch

from src.agente import reflexion
from src.engines.modelos import RespuestaMotor


def _log(tmp_path, cantidad, inicio=0):
    carpeta = tmp_path / "00-Sistema"
    carpeta.mkdir(exist_ok=True)
    entradas = [
        f"### 2026-09-24 12:{i:02d} (ollama)\n**Usuario:** mensaje {i}\n**Respuesta:** ok\n"
        for i in range(inicio, inicio + cantidad)
    ]
    ruta = carpeta / "Logs-Interacciones.md"
    previo = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    ruta.write_text(previo + "".join(entradas), encoding="utf-8")


def test_la_primera_vez_solo_marca_el_punto_de_partida(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _log(tmp_path, 25)

    assert reflexion.debe_reflexionar() is False
    config = (tmp_path / "00-Sistema" / "Configuracion.md").read_text(encoding="utf-8")
    assert "ultima_reflexion: 25" in config


def test_toca_reflexionar_tras_suficientes_interacciones_nuevas(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _log(tmp_path, 5)
    reflexion.debe_reflexionar()  # marca el punto de partida en 5

    _log(tmp_path, reflexion.CADA_N_INTERACCIONES - 1, inicio=5)
    assert reflexion.debe_reflexionar() is False

    _log(tmp_path, 1, inicio=20)
    assert reflexion.debe_reflexionar() is True


@patch("src.agente.reflexion.preguntar_ollama")
def test_reflexionar_anota_datos_y_patrones_nuevos(mock_ollama, tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _log(tmp_path, 3)
    reflexion.debe_reflexionar()
    _log(tmp_path, 2, inicio=3)
    mock_ollama.return_value = RespuestaMotor(
        exito=True,
        texto=json.dumps({"datos_usuario": ["Se llama Luis"], "patrones": ["Pide sus pendientes por la mañana"]}),
    )

    anotado = reflexion.reflexionar()

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    patrones = (tmp_path / "01-Perfil" / "Patrones.md").read_text(encoding="utf-8")
    assert "Se llama Luis" in perfil
    assert "Pide sus pendientes por la mañana" in patrones
    assert len(anotado) == 2
    # Solo se le mandan las interacciones nuevas, no el historial previo.
    prompt = mock_ollama.call_args.args[0]
    assert "mensaje 3" in prompt and "mensaje 0" not in prompt
    config = (tmp_path / "00-Sistema" / "Configuracion.md").read_text(encoding="utf-8")
    assert "ultima_reflexion: 5" in config


@patch("src.agente.reflexion.preguntar_ollama")
def test_reflexionar_no_duplica_lo_que_ya_esta_en_el_perfil(mock_ollama, tmp_path, monkeypatch):
    """Caso real: el perfil ya decía el nombre y el café, y el modelo los volvió a proponer por separado."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text(
        "- Se llama Luis y le encanta el café sin azúcar (2026-09-24)\n", encoding="utf-8"
    )
    _log(tmp_path, 1)
    reflexion.debe_reflexionar()
    _log(tmp_path, 1, inicio=1)
    mock_ollama.return_value = RespuestaMotor(
        exito=True,
        texto=json.dumps({
            "datos_usuario": ["Se llama Luis.", "Le encanta el cafe sin azucar", "Vive en Guadalajara", "Vive en Guadalajara"],
            "patrones": [],
        }),
    )

    anotado = reflexion.reflexionar()

    assert anotado == ["Anotado en tu perfil: Vive en Guadalajara"]


class _HiloInmediato:
    """Sustituto de threading.Thread que ejecuta el trabajo en el acto, para poder verificarlo."""

    def __init__(self, target, daemon=None):
        self._target = target

    def start(self):
        self._target()


@patch("src.agente.reflexion.threading.Thread", _HiloInmediato)
@patch("src.agente.reflexion.preguntar_ollama")
def test_dato_personal_sin_guardar_se_extrae_en_el_momento(mock_ollama, tmp_path, monkeypatch):
    """Caso real: respondió 'Mucho gusto, Josué' sin llamar a recordar_sobre_usuario."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    mock_ollama.return_value = RespuestaMotor(exito=True, texto=json.dumps({"datos_usuario": ["Se llama Josué"]}))

    reflexion.aprender_si_quedo_sin_guardar("Ok, mi nombre es Josue", herramientas_usadas=[])

    assert "Se llama Josué" in (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")


@patch("src.agente.reflexion.threading.Thread", _HiloInmediato)
@patch("src.agente.reflexion.preguntar_ollama")
def test_no_extrae_si_el_agente_ya_lo_guardo(mock_ollama):
    reflexion.aprender_si_quedo_sin_guardar("mi nombre es Josue", herramientas_usadas=["recordar_sobre_usuario"])

    mock_ollama.assert_not_called()


@patch("src.agente.reflexion.threading.Thread", _HiloInmediato)
@patch("src.agente.reflexion.preguntar_ollama")
def test_no_extrae_de_mensajes_que_no_son_personales(mock_ollama):
    reflexion.aprender_si_quedo_sin_guardar("¿cuál es la capital de Francia?", herramientas_usadas=[])

    mock_ollama.assert_not_called()


@patch("src.agente.reflexion.preguntar_ollama")
def test_reflexionar_tolera_json_invalido(mock_ollama, tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _log(tmp_path, 1)
    reflexion.debe_reflexionar()
    _log(tmp_path, 1, inicio=1)
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="esto no es json")

    assert reflexion.reflexionar() == []
