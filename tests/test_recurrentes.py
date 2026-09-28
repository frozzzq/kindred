from datetime import datetime, time

import pytest

from src.obsidian.recurrentes import Recurrencia, formatear_linea, parsear_frecuencia, parsear_linea, toca_hoy

LUNES = datetime(2026, 9, 28, 10, 0)
MARTES = datetime(2026, 9, 29, 10, 0)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("diario a las 9pm", Recurrencia((), time(21, 0))),
        ("a diario a las 9pm", Recurrencia((), time(21, 0))),
        ("todos los días a las 9pm", Recurrencia((), time(21, 0))),
        ("los lunes a las 8am", Recurrencia((0,), time(8, 0))),
        ("lunes a las 8am", Recurrencia((0,), time(8, 0))),
        ("todos los lunes y miércoles a las 8am", Recurrencia((0, 2), time(8, 0))),
        ("lunes, miércoles y viernes a las 8am", Recurrencia((0, 2, 4), time(8, 0))),
        ("martes a las 21:00", Recurrencia((1,), time(21, 0))),
    ],
)
def test_parsear_frecuencia(texto, esperado):
    assert parsear_frecuencia(texto) == esperado


@pytest.mark.parametrize("texto", ["sin hora ni frecuencia clara", "diario", "a las 8"])
def test_parsear_frecuencia_sin_hora_clara_devuelve_none(texto):
    """Una recurrencia sin hora (o con una ambigua) no sirve para avisar a tiempo."""
    assert parsear_frecuencia(texto) is None


@pytest.mark.parametrize(
    "tarea, recurrencia",
    [
        ("Tomar medicina", Recurrencia((), time(21, 0))),
        ("Sacar la basura", Recurrencia((0, 2, 4), time(8, 0))),
        ("Regar las plantas", Recurrencia((6,), time(9, 30))),
    ],
)
def test_formatear_y_parsear_linea_ida_y_vuelta(tarea, recurrencia):
    linea = f"- {formatear_linea(tarea, recurrencia)} (agregado 2026-09-28 10:00)"

    assert parsear_linea(linea) == (tarea, recurrencia)


def test_formatear_linea_diario():
    assert formatear_linea("Tomar medicina", Recurrencia((), time(21, 0))) == "Tomar medicina 🔁 diario 21:00"


def test_parsear_linea_sin_tag_devuelve_none():
    assert parsear_linea("- Una nota cualquiera sin el tag") is None


def test_toca_hoy_diario():
    assert toca_hoy(Recurrencia((), time(9, 0)), LUNES) is True


def test_toca_hoy_semanal():
    recurrencia = Recurrencia((0, 2), time(9, 0))  # lunes y miércoles

    assert toca_hoy(recurrencia, LUNES) is True
    assert toca_hoy(recurrencia, MARTES) is False
