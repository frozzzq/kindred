from datetime import datetime
from unittest.mock import patch

import pytest

from src.nucleo.recordatorios import Recordatorio
from src.nucleo.servicio import _en_horario_silencio, ciclo

LUNES_MEDIODIA = datetime(2026, 9, 28, 12, 0)


@pytest.fixture(autouse=True)
def boveda_y_estado_temporales(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("HORARIO_SILENCIO", raising=False)
    monkeypatch.delenv("HORA_BRIEFING", raising=False)
    monkeypatch.delenv("HORA_CIERRE", raising=False)


# --- _en_horario_silencio ---


@pytest.mark.parametrize(
    "hora, esperado",
    [
        (datetime(2026, 9, 28, 23, 30), True),
        (datetime(2026, 9, 29, 3, 0), True),
        (datetime(2026, 9, 29, 6, 59), True),
        (datetime(2026, 9, 29, 7, 0), False),
        (datetime(2026, 9, 28, 12, 0), False),
        (datetime(2026, 9, 28, 22, 59), False),
    ],
)
def test_horario_silencio_cruza_medianoche(hora, esperado, monkeypatch):
    monkeypatch.setenv("HORARIO_SILENCIO", "23:00-07:00")

    assert _en_horario_silencio(hora) is esperado


def test_sin_horario_silencio_configurado_nunca_hay_silencio(monkeypatch):
    monkeypatch.delenv("HORARIO_SILENCIO", raising=False)

    assert _en_horario_silencio(datetime(2026, 9, 28, 3, 0)) is False


def test_horario_silencio_mal_formado_no_crashea(monkeypatch):
    monkeypatch.setenv("HORARIO_SILENCIO", "algo raro")

    assert _en_horario_silencio(LUNES_MEDIODIA) is False


# --- ciclo() ---


@patch("src.nucleo.servicio.estado.marcar_avisado")
@patch("src.nucleo.servicio.avisos.avisar")
@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar")
def test_ciclo_avisa_los_recordatorios_pendientes(mock_pendientes, _mock_recurrentes, mock_avisar, mock_marcar):
    mock_pendientes.return_value = [Recordatorio("clave-1", "Llamar al dentista")]

    ciclo(LUNES_MEDIODIA)

    mock_avisar.assert_any_call("Recordatorio", "Llamar al dentista")
    mock_marcar.assert_called_once_with("clave-1", LUNES_MEDIODIA.isoformat())


@patch("src.nucleo.servicio.avisos.avisar")
@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", return_value=[])
def test_ciclo_en_horario_de_silencio_no_avisa_nada(_mock_p, _mock_r, mock_avisar, monkeypatch):
    monkeypatch.setenv("HORARIO_SILENCIO", "00:00-23:59")  # cubre cualquier hora del test

    ciclo(LUNES_MEDIODIA)

    mock_avisar.assert_not_called()


@patch("src.nucleo.servicio.estado.marcar_briefing")
@patch("src.nucleo.servicio.avisos.avisar")
@patch("src.nucleo.servicio.briefing.generar_matutino", return_value="Buenos días, texto.")
@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", return_value=[])
def test_ciclo_dispara_el_briefing_matutino_a_su_hora(_mp, _mr, mock_generar, mock_avisar, mock_marcar, monkeypatch):
    monkeypatch.setenv("HORA_BRIEFING", "08:00")

    ciclo(LUNES_MEDIODIA)  # son las 12:00, ya pasó la hora configurada

    mock_generar.assert_called_once_with(LUNES_MEDIODIA)
    mock_avisar.assert_any_call("Buenos días", "Buenos días, texto.")
    mock_marcar.assert_called_once_with("briefing", "2026-09-28")


@patch("src.nucleo.servicio.avisos.avisar")
@patch("src.nucleo.servicio.briefing.generar_matutino")
@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", return_value=[])
def test_ciclo_no_dispara_el_briefing_antes_de_su_hora(_mp, _mr, mock_generar, mock_avisar, monkeypatch):
    monkeypatch.setenv("HORA_BRIEFING", "20:00")

    ciclo(LUNES_MEDIODIA)  # son las 12:00, todavía no

    mock_generar.assert_not_called()


@patch("src.nucleo.servicio.estado.briefing_de_hoy", return_value="2026-09-28")
@patch("src.nucleo.servicio.avisos.avisar")
@patch("src.nucleo.servicio.briefing.generar_matutino")
@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", return_value=[])
def test_ciclo_no_repite_el_briefing_el_mismo_dia(_mp, _mr, mock_generar, mock_avisar, _mock_hoy, monkeypatch):
    monkeypatch.setenv("HORA_BRIEFING", "08:00")

    ciclo(LUNES_MEDIODIA)

    mock_generar.assert_not_called()


@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", return_value=[])
def test_ciclo_actualiza_heartbeat_md(_mp, _mr, tmp_path):
    ciclo(LUNES_MEDIODIA)

    contenido = (tmp_path / "00-Sistema" / "HEARTBEAT.md").read_text(encoding="utf-8")
    assert "2026-09-28 12:00:00" in contenido


@patch("src.nucleo.servicio.recordatorios.recurrentes_por_avisar", return_value=[])
@patch("src.nucleo.servicio.recordatorios.pendientes_por_avisar", side_effect=RuntimeError("la bóveda no responde"))
def test_ciclo_propaga_sus_errores(_mp, _mr):
    """ciclo() no atrapa nada: el atrapa-todo (para que el heartbeat nunca se muera) vive en main()."""
    with pytest.raises(RuntimeError):
        ciclo(LUNES_MEDIODIA)


@patch("src.arranque.preparar")  # no debe pisar OBSIDIAN_VAULT_PATH/LOCALAPPDATA del test con el .env real
@patch("src.nucleo.servicio._reloj.sleep")
@patch("src.nucleo.servicio.ciclo")
def test_main_sigue_corriendo_aunque_un_ciclo_falle(mock_ciclo, mock_sleep, _mock_preparar):
    """Caso real que debe evitarse: Ollama caído un momento no debe tumbar el proceso de fondo."""
    mock_ciclo.side_effect = [RuntimeError("Ollama no responde"), None]
    mock_sleep.side_effect = [None, KeyboardInterrupt]

    from src.nucleo.servicio import main

    main()  # no debe lanzar

    assert mock_ciclo.call_count == 2
