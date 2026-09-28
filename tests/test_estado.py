import pytest

from src.nucleo.estado import briefing_de_hoy, marcar_avisado, marcar_briefing, ruta_estado, ya_avisado


@pytest.fixture(autouse=True)
def local_appdata_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_ya_avisado_falso_si_nunca_se_marco():
    assert ya_avisado("pendiente:comprar leche:2026-09-30 18:00") is False


def test_marcar_avisado_lo_deja_avisado():
    marcar_avisado("clave-1", "2026-09-28 10:00")

    assert ya_avisado("clave-1") is True
    assert ya_avisado("clave-2") is False


def test_marcar_avisado_es_idempotente():
    marcar_avisado("clave-1", "2026-09-28 10:00")
    marcar_avisado("clave-1", "2026-09-28 10:00")  # una segunda vuelta del heartbeat no debe fallar

    assert ya_avisado("clave-1") is True


def test_briefing_de_hoy_ninguno_todavia():
    assert briefing_de_hoy("matutino") is None


def test_marcar_briefing_y_leerlo():
    marcar_briefing("matutino", "2026-09-28")

    assert briefing_de_hoy("matutino") == "2026-09-28"
    assert briefing_de_hoy("cierre") is None  # tipos distintos, no se mezclan


def test_marcar_briefing_actualiza_la_fecha():
    marcar_briefing("matutino", "2026-09-28")
    marcar_briefing("matutino", "2026-09-29")

    assert briefing_de_hoy("matutino") == "2026-09-29"


def test_el_estado_persiste_entre_conexiones(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    marcar_avisado("clave-1", "2026-09-28 10:00")

    assert ruta_estado().exists()
    assert ya_avisado("clave-1") is True  # nueva conexión (cada llamada abre y cierra la suya)
