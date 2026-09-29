from unittest.mock import patch

import pytest

from src.actions import foco


@pytest.fixture(autouse=True)
def sin_estado_previo(monkeypatch):
    """Cada test empieza sin ninguna ventana externa "recordada" de un test anterior."""
    monkeypatch.setattr(foco, "_ultima_ventana_externa", None)


def test_es_ventana_propia_compara_el_pid():
    with patch("src.actions.foco.win32process.GetWindowThreadProcessId", return_value=(1, foco._pid_propio)):
        assert foco._es_ventana_propia(123) is True
    with patch("src.actions.foco.win32process.GetWindowThreadProcessId", return_value=(1, foco._pid_propio + 1)):
        assert foco._es_ventana_propia(123) is False


def test_es_ventana_propia_ventana_invalida_no_crashea():
    with patch("src.actions.foco.win32process.GetWindowThreadProcessId", side_effect=Exception("ventana inválida")):
        assert foco._es_ventana_propia(999) is False


def test_ventana_objetivo_sin_ninguna_ventana_activa():
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=0):
        assert foco.ventana_objetivo() is None


def test_ventana_objetivo_devuelve_la_activa_si_no_es_propia():
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=42), patch.object(
        foco, "_es_ventana_propia", return_value=False
    ):
        assert foco.ventana_objetivo() == 42


@patch("src.actions.foco._traer_al_frente")
def test_ventana_objetivo_le_devuelve_el_foco_a_la_externa_si_la_activa_es_propia(mock_traer, monkeypatch):
    monkeypatch.setattr(foco, "_ultima_ventana_externa", 77)
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=1), patch.object(
        foco, "_es_ventana_propia", return_value=True
    ), patch("src.actions.foco.win32gui.IsWindow", return_value=True):
        resultado = foco.ventana_objetivo()

    assert resultado == 77
    mock_traer.assert_called_once_with(77)


def test_ventana_objetivo_sin_ventana_externa_conocida_devuelve_none():
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=1), patch.object(
        foco, "_es_ventana_propia", return_value=True
    ):
        assert foco.ventana_objetivo() is None


def test_ventana_objetivo_con_ventana_externa_ya_cerrada_devuelve_none(monkeypatch):
    monkeypatch.setattr(foco, "_ultima_ventana_externa", 77)
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=1), patch.object(
        foco, "_es_ventana_propia", return_value=True
    ), patch("src.actions.foco.win32gui.IsWindow", return_value=False):
        assert foco.ventana_objetivo() is None


@patch("src.actions.foco.win32gui.SetForegroundWindow", side_effect=RuntimeError("Windows lo bloqueó"))
@patch("src.actions.foco.win32api.keybd_event")
def test_ventana_objetivo_si_no_se_puede_traer_al_frente_igual_devuelve_la_ventana(
    _mock_keybd, _mock_set_foreground, monkeypatch
):
    monkeypatch.setattr(foco, "_ultima_ventana_externa", 77)
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=1), patch.object(
        foco, "_es_ventana_propia", return_value=True
    ), patch("src.actions.foco.win32gui.IsWindow", return_value=True), patch("src.actions.foco.time.sleep"):
        resultado = foco.ventana_objetivo()

    assert resultado == 77


def test_rastrear_actualiza_solo_con_ventanas_externas(monkeypatch):
    """Simula un par de vueltas del hilo de rastreo (sin el time.sleep real ni el bucle infinito)."""
    llamadas = {"veces": 0}

    def foreground_falso():
        llamadas["veces"] += 1
        return 5 if llamadas["veces"] == 1 else 6  # primero una ventana propia, luego una externa

    def es_propia_falsa(hwnd):
        return hwnd == 5

    def dormir_y_parar(_segundos):
        raise StopIteration  # corta el "while True" tras una vuelta

    monkeypatch.setattr(foco, "_ultima_ventana_externa", None)
    with patch("src.actions.foco.win32gui.GetForegroundWindow", side_effect=foreground_falso), patch.object(
        foco, "_es_ventana_propia", side_effect=es_propia_falsa
    ), patch("src.actions.foco.time.sleep", side_effect=dormir_y_parar):
        with pytest.raises(StopIteration):
            foco._rastrear()
    assert foco._ultima_ventana_externa is None  # la primera vuelta vio la ventana propia (5), no se guarda

    llamadas["veces"] = 0
    with patch("src.actions.foco.win32gui.GetForegroundWindow", return_value=6), patch.object(
        foco, "_es_ventana_propia", return_value=False
    ), patch("src.actions.foco.time.sleep", side_effect=dormir_y_parar):
        with pytest.raises(StopIteration):
            foco._rastrear()
    assert foco._ultima_ventana_externa == 6


def test_iniciar_rastreo_no_arranca_dos_hilos(monkeypatch):
    monkeypatch.setattr(foco, "_rastreo_iniciado", False)
    with patch("src.actions.foco.threading.Thread") as mock_thread:
        foco.iniciar_rastreo()
        foco.iniciar_rastreo()

    mock_thread.assert_called_once()
    monkeypatch.setattr(foco, "_rastreo_iniciado", False)  # no dejar el estado alterado para otros tests
