from unittest.mock import patch

from src.nucleo.avisos import avisar
from src.router.intent_router import MOTOR_OLLAMA


@patch("src.nucleo.avisos.hablar")
@patch("src.nucleo.avisos.toast")
def test_avisar_notifica_por_windows_y_por_voz(mock_toast, mock_hablar):
    """Sin un tercer agente "Jarvis": el aviso se atribuye a Crimson (notificación y voz)."""
    avisar("Recordatorio", "Llamar al dentista")

    mock_toast.assert_called_once_with("Recordatorio", "Llamar al dentista", app_id="Crimson")
    mock_hablar.assert_called_once_with("Llamar al dentista", motor=MOTOR_OLLAMA)


@patch("src.nucleo.avisos.hablar")
@patch("src.nucleo.avisos.toast")
def test_avisar_sin_voz(mock_toast, mock_hablar):
    avisar("Recordatorio", "Llamar al dentista", con_voz=False)

    mock_toast.assert_called_once()
    mock_hablar.assert_not_called()


@patch("src.nucleo.avisos.hablar")
@patch("src.nucleo.avisos.toast", side_effect=OSError("sin permisos de notificación"))
def test_avisar_si_falla_windows_igual_avisa_por_voz(mock_toast, mock_hablar):
    """Un canal caído no debe tumbar el heartbeat ni impedir el otro canal."""
    avisar("Recordatorio", "Llamar al dentista")

    mock_hablar.assert_called_once_with("Llamar al dentista", motor=MOTOR_OLLAMA)


@patch("src.nucleo.avisos.hablar", side_effect=RuntimeError("sin bocinas"))
@patch("src.nucleo.avisos.toast")
def test_avisar_si_falla_la_voz_no_crashea(mock_toast, mock_hablar):
    avisar("Recordatorio", "Llamar al dentista")  # no debe lanzar

    mock_toast.assert_called_once()


@patch("src.nucleo.avisos.hablar", side_effect=RuntimeError("sin bocinas"))
@patch("src.nucleo.avisos.toast", side_effect=OSError("sin permisos"))
def test_avisar_si_fallan_los_dos_no_crashea(mock_toast, mock_hablar):
    avisar("Recordatorio", "Llamar al dentista")  # no debe lanzar
