from datetime import date, datetime, time

import pytest

from src.obsidian.fechas import extraer_hora, extraer_tags, formatear_tags, parsear_fecha_hora

AHORA = datetime(2026, 9, 28, 10, 0)  # lunes


@pytest.mark.parametrize(
    "texto, fecha_esperada, hora_esperada",
    [
        ("mañana a las 6pm", date(2026, 9, 29), time(18, 0)),
        ("el viernes", date(2026, 10, 2), None),
        ("este viernes", date(2026, 10, 2), None),
        ("para el viernes", date(2026, 10, 2), None),
        ("pasado mañana", date(2026, 9, 30), None),
        ("pasado mañana a las 6pm", date(2026, 9, 30), time(18, 0)),
        ("en 2 horas", date(2026, 9, 28), time(12, 0)),
        ("en 30 minutos", date(2026, 9, 28), time(10, 30)),
        ("el 5 de octubre a las 9am", date(2026, 10, 5), time(9, 0)),
        ("hoy a las 21:00", date(2026, 9, 28), time(21, 0)),
        ("medianoche", date(2026, 9, 28), time(0, 0)),
        ("recuérdame mañana a las 6pm que llame al doctor", date(2026, 9, 29), time(18, 0)),
        ("el lunes a las 8 de la mañana", date(2026, 10, 5), time(8, 0)),
        ("el 10 de noviembre a las 5pm", date(2026, 11, 10), time(17, 0)),
        ("en una semana", date(2026, 10, 5), None),
        ("dentro de 3 días", date(2026, 10, 1), None),
        ("8 de la noche", date(2026, 9, 28), time(20, 0)),
        ("12 de la noche", date(2026, 9, 28), time(0, 0)),
        ("12 de la tarde", date(2026, 9, 28), time(12, 0)),
        ("12 de la mañana", date(2026, 9, 28), time(0, 0)),
    ],
)
def test_parsear_fecha_hora(texto, fecha_esperada, hora_esperada):
    assert parsear_fecha_hora(texto, AHORA) == (fecha_esperada, hora_esperada)


@pytest.mark.parametrize("texto", ["comprar leche", "algo sin fecha ni hora", "llamar al dentista", "pagar la luz"])
def test_parsear_fecha_hora_sin_fecha_ni_hora_devuelve_nada(texto):
    """Caso real: dateparser leía la palabra suelta "hora" como si fuera "hoy" y le ponía fecha a
    cualquier pendiente que la mencionara."""
    assert parsear_fecha_hora(texto, AHORA) == (None, None)


def test_a_las_ocho_sin_am_pm_no_adivina_la_hora():
    """"a las 8" solo, sin am/pm ni "de la tarde/mañana/noche", es ambiguo: mejor sin hora exacta
    que arriesgarse a sonar 12 horas antes o después de lo que quiso decir el usuario."""
    assert parsear_fecha_hora("a las 8", AHORA) == (None, None)


@pytest.mark.parametrize(
    "texto, hora_esperada",
    [
        ("a las 6pm", time(18, 0)),
        ("a las 6 pm", time(18, 0)),
        ("a las 6:30pm", time(18, 30)),
        ("a las 6am", time(6, 0)),
        ("14:00", time(14, 0)),
        ("8 de la mañana", time(8, 0)),
        ("8 de la tarde", time(20, 0)),
        ("8 de la noche", time(20, 0)),
        ("a las 8", None),
    ],
)
def test_extraer_hora(texto, hora_esperada):
    assert extraer_hora(texto) == hora_esperada


def test_formatear_tags_con_hora():
    assert formatear_tags(date(2026, 9, 30), time(18, 0)) == "📅 2026-09-30 ⏰ 2026-09-30 18:00"


def test_formatear_tags_sin_hora():
    assert formatear_tags(date(2026, 9, 30), None) == "📅 2026-09-30"


def test_extraer_tags_ida_y_vuelta():
    linea = "- [ ] Entregar tarea " + formatear_tags(date(2026, 9, 30), time(18, 0)) + " (agregado 2026-09-28)"

    fecha, hora = extraer_tags(linea)

    assert fecha == date(2026, 9, 30)
    assert hora == datetime(2026, 9, 30, 18, 0)


def test_extraer_tags_sin_tags_devuelve_nada():
    assert extraer_tags("- [ ] Comprar leche (agregado 2026-09-28)") == (None, None)
