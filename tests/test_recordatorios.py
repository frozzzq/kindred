from datetime import date, datetime, time

import pytest

from src.nucleo.estado import marcar_avisado
from src.nucleo.recordatorios import pendientes_por_avisar, recurrentes_por_avisar
from src.obsidian.fechas import formatear_tags
from src.obsidian.recurrentes import Recurrencia, formatear_linea
from src.obsidian.vault_writer import RUTA_PENDIENTES, RUTA_RECURRENTES, escribir_nota

AHORA = datetime(2026, 9, 28, 18, 5)  # lunes


@pytest.fixture(autouse=True)
def boveda_y_estado_temporales(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))


def _pendiente(tarea, fecha=None, hora=None):
    """Escribe directo en Pendientes.md (no vía agregar_pendiente, que usaría la hora real del
    reloj para interpretar "cuando"): así la fecha/hora del pendiente queda bajo control del test."""
    etiqueta = f" {formatear_tags(fecha, hora)}" if fecha else ""
    escribir_nota(RUTA_PENDIENTES, f"- [ ] {tarea}{etiqueta} (agregado 2026-09-27 09:00)")


def _recurrente(tarea, recurrencia):
    escribir_nota(RUTA_RECURRENTES, f"- {formatear_linea(tarea, recurrencia)} (agregado 2026-09-27 09:00)")


def test_pendiente_con_hora_vencida_se_avisa():
    _pendiente("Llamar al dentista", date(2026, 9, 28), time(18, 0))

    resultado = pendientes_por_avisar(AHORA)

    assert [r.tarea for r in resultado] == ["Llamar al dentista"]


def test_pendiente_con_hora_futura_no_se_avisa_todavia():
    _pendiente("Llamar al dentista", date(2026, 9, 28), time(20, 0))

    assert pendientes_por_avisar(AHORA) == []


def test_pendiente_sin_hora_no_se_avisa():
    """📅 sin ⏰ es una fecha de referencia (sale en el briefing), no dispara un aviso puntual."""
    _pendiente("Entregar el reporte", date(2026, 10, 2), None)

    assert pendientes_por_avisar(AHORA) == []


def test_pendiente_sin_fecha_no_se_avisa():
    _pendiente("Comprar leche")

    assert pendientes_por_avisar(AHORA) == []


def test_pendiente_ya_avisado_no_se_repite():
    _pendiente("Llamar al dentista", date(2026, 9, 28), time(18, 0))

    primera = pendientes_por_avisar(AHORA)
    for recordatorio in primera:
        marcar_avisado(recordatorio.clave, AHORA.isoformat())
    segunda = pendientes_por_avisar(AHORA)

    assert len(primera) == 1
    assert segunda == []


def test_recurrente_diario_con_hora_pasada_se_avisa():
    _recurrente("Tomar medicina", Recurrencia((), time(18, 0)))

    resultado = recurrentes_por_avisar(AHORA)

    assert [r.tarea for r in resultado] == ["Tomar medicina"]


def test_recurrente_diario_con_hora_futura_no_se_avisa():
    _recurrente("Tomar medicina", Recurrencia((), time(21, 0)))

    assert recurrentes_por_avisar(AHORA) == []


def test_recurrente_semanal_solo_avisa_el_dia_que_toca():
    _recurrente("Sacar la basura", Recurrencia((1,), time(18, 0)))  # martes; AHORA es lunes

    assert recurrentes_por_avisar(AHORA) == []


def test_recurrente_ya_avisado_hoy_no_se_repite():
    _recurrente("Tomar medicina", Recurrencia((), time(18, 0)))

    primera = recurrentes_por_avisar(AHORA)
    for recordatorio in primera:
        marcar_avisado(recordatorio.clave, AHORA.isoformat())
    segunda = recurrentes_por_avisar(AHORA)

    assert len(primera) == 1
    assert segunda == []


def test_recurrente_se_vuelve_a_avisar_al_dia_siguiente():
    _recurrente("Tomar medicina", Recurrencia((), time(18, 0)))
    primera = recurrentes_por_avisar(AHORA)
    for recordatorio in primera:
        marcar_avisado(recordatorio.clave, AHORA.isoformat())

    otro_dia = datetime(2026, 9, 29, 18, 5)
    resultado = recurrentes_por_avisar(otro_dia)

    assert [r.tarea for r in resultado] == ["Tomar medicina"]


def test_con_boveda_vacia_no_falla():
    assert pendientes_por_avisar(AHORA) == []
    assert recurrentes_por_avisar(AHORA) == []
