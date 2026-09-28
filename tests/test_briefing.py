from datetime import date, datetime, time
from unittest.mock import patch

import pytest

from src.engines.modelos import RespuestaMotor
from src.nucleo.briefing import generar_cierre, generar_matutino
from src.obsidian.fechas import formatear_tags
from src.obsidian.recurrentes import Recurrencia, formatear_linea
from src.obsidian.vault_writer import RUTA_PENDIENTES, RUTA_RECURRENTES, escribir_nota

AHORA = datetime(2026, 9, 28, 8, 0)  # lunes


@pytest.fixture(autouse=True)
def boveda_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))


def _pendiente(tarea, fecha=None, hora=None):
    etiqueta = f" {formatear_tags(fecha, hora)}" if fecha else ""
    escribir_nota(RUTA_PENDIENTES, f"- [ ] {tarea}{etiqueta} (agregado x)")


def _recurrente(tarea, recurrencia):
    escribir_nota(RUTA_RECURRENTES, f"- {formatear_linea(tarea, recurrencia)} (agregado x)")


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_matutino_le_pasa_los_datos_reales_a_ollama_sin_inventar(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Buenos días, tienes esto para hoy.")
    _pendiente("Entregar el reporte", date(2026, 9, 28), time(18, 0))
    _pendiente("Pagar la luz", date(2026, 9, 20))  # vencido
    _recurrente("Tomar medicina", Recurrencia((), time(9, 0)))

    resultado = generar_matutino(AHORA)

    prompt = mock_ollama.call_args.args[0]
    assert "Entregar el reporte" in prompt
    assert "Pagar la luz" in prompt
    assert "Tomar medicina" in prompt
    assert resultado == "Buenos días, tienes esto para hoy."


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_matutino_sin_nada_pendiente(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Buenos días, no tienes nada para hoy.")

    generar_matutino(AHORA)

    prompt = mock_ollama.call_args.args[0]
    assert prompt.count("(ninguno)") >= 3  # las 3 listas vacías, más la instrucción que las explica


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_matutino_si_ollama_falla_usa_el_respaldo_sin_ia(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=False, error="Ollama no responde")
    _pendiente("Entregar el reporte", date(2026, 9, 28), time(18, 0))

    resultado = generar_matutino(AHORA)

    assert "Entregar el reporte" in resultado


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_matutino_sin_nada_y_ollama_caido(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=False, error="Ollama no responde")

    resultado = generar_matutino(AHORA)

    assert "no tienes nada pendiente" in resultado.lower()


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_cierre_incluye_solo_pendientes_de_hoy(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Cierre del día.")
    _pendiente("Entregar el reporte", date(2026, 9, 28), time(18, 0))
    _pendiente("Algo de la próxima semana", date(2026, 10, 5))

    generar_cierre(AHORA)

    prompt = mock_ollama.call_args.args[0]
    assert "Entregar el reporte" in prompt
    assert "próxima semana" not in prompt


@patch("src.nucleo.briefing.preguntar_ollama")
def test_generar_cierre_si_ollama_falla_usa_el_respaldo(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=False, error="Ollama no responde")

    resultado = generar_cierre(AHORA)

    assert "terminaste todo" in resultado.lower()
