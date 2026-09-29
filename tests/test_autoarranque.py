import subprocess
from unittest.mock import patch

from src.nucleo.autoarranque import NOMBRE_TAREA, quitar_tarea_programada, registrar_tarea_programada


@patch("src.nucleo.autoarranque.RUTA_LANZADOR")
@patch("src.nucleo.autoarranque.subprocess.run")
def test_registrar_tarea_programada(mock_run, mock_ruta):
    mock_ruta.exists.return_value = True
    mock_ruta.__str__.return_value = r"C:\kindred\Jarvis.bat"
    mock_run.return_value = subprocess.CompletedProcess([], 0)

    resultado = registrar_tarea_programada()

    comando = mock_run.call_args.args[0]
    assert comando[:3] == ["schtasks", "/create", "/tn"]
    assert NOMBRE_TAREA in comando
    assert "/sc" in comando and "onlogon" in comando
    assert comando[comando.index("/tr") + 1] == r'"C:\kindred\Jarvis.bat" nucleo'  # el lanzador único, modo núcleo
    assert "Listo" in resultado


@patch("src.nucleo.autoarranque.RUTA_LANZADOR")
def test_registrar_sin_el_lanzador_no_llama_a_schtasks(mock_ruta):
    mock_ruta.exists.return_value = False

    with patch("src.nucleo.autoarranque.subprocess.run") as mock_run:
        resultado = registrar_tarea_programada()

    mock_run.assert_not_called()
    assert "No encontré" in resultado


@patch("src.nucleo.autoarranque.RUTA_LANZADOR")
@patch("src.nucleo.autoarranque.subprocess.run")
def test_registrar_si_schtasks_falla_lo_dice(mock_run, mock_ruta):
    mock_ruta.exists.return_value = True
    mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks", stderr="sin permisos")

    resultado = registrar_tarea_programada()

    assert "No se pudo registrar" in resultado


@patch("src.nucleo.autoarranque.subprocess.run")
def test_quitar_tarea_programada(mock_run):
    mock_run.return_value = subprocess.CompletedProcess([], 0)

    resultado = quitar_tarea_programada()

    comando = mock_run.call_args.args[0]
    assert comando == ["schtasks", "/delete", "/tn", NOMBRE_TAREA, "/f"]
    assert "Listo" in resultado


@patch("src.nucleo.autoarranque.subprocess.run")
def test_quitar_si_no_existe_lo_dice(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "schtasks", stderr="no existe la tarea")

    resultado = quitar_tarea_programada()

    assert "No se pudo quitar" in resultado
