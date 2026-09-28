from unittest.mock import MagicMock, patch

from src.actions import system_control
from src.actions.system_control import abrir_aplicacion, escribir_texto, hacer_click


@patch("src.actions.system_control.os.startfile")
def test_abrir_aplicacion_conocida(mock_startfile):
    resultado = abrir_aplicacion("calculadora")

    assert resultado.exito is True
    mock_startfile.assert_called_once_with("calc.exe")


def test_abrir_aplicacion_desconocida_no_crashea():
    resultado = abrir_aplicacion("una app que no existe")

    assert resultado.exito is False
    assert "una app que no existe" in resultado.mensaje


@patch("src.actions.system_control.os.startfile")
def test_abrir_aplicacion_quita_puntuacion(mock_startfile):
    resultado = abrir_aplicacion("calculadora.")

    assert resultado.exito is True
    mock_startfile.assert_called_once_with("calc.exe")


@patch("src.actions.system_control.os.startfile")
def test_abrir_aplicacion_error_del_sistema_no_crashea(mock_startfile):
    mock_startfile.side_effect = OSError("no encontrado")

    resultado = abrir_aplicacion("chrome")

    assert resultado.exito is False
    assert "chrome" in resultado.mensaje


# --- hacer_click ---


@patch("src.actions.system_control.Desktop")
@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=123)
def test_hacer_click_encuentra_control_por_texto_exacto(_mock_hwnd, mock_desktop_cls):
    boton, otro = MagicMock(), MagicMock()
    boton.window_text.return_value = "Guardar"
    otro.window_text.return_value = "Cancelar"
    mock_desktop_cls.return_value.window.return_value.descendants.return_value = [otro, boton]

    resultado = hacer_click("Guardar")

    assert resultado.exito is True
    boton.click_input.assert_called_once()
    otro.click_input.assert_not_called()


@patch("src.actions.system_control.Desktop")
@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=123)
def test_hacer_click_usa_coincidencia_parcial_si_no_hay_exacta(_mock_hwnd, mock_desktop_cls):
    boton = MagicMock()
    boton.window_text.return_value = "Guardar cambios"
    mock_desktop_cls.return_value.window.return_value.descendants.return_value = [boton]

    resultado = hacer_click("guardar")

    assert resultado.exito is True
    boton.click_input.assert_called_once()


@patch("src.actions.system_control.Desktop")
@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=123)
def test_hacer_click_sin_coincidencia_no_crashea(_mock_hwnd, mock_desktop_cls):
    mock_desktop_cls.return_value.window.return_value.descendants.return_value = []

    resultado = hacer_click("algo que no existe")

    assert resultado.exito is False
    assert "algo que no existe" in resultado.mensaje


@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=0)
def test_hacer_click_sin_ventana_activa_no_crashea(_mock_hwnd):
    resultado = hacer_click("Guardar")

    assert resultado.exito is False


@patch("src.actions.system_control.Desktop")
@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=123)
def test_hacer_click_ventana_inaccesible_no_crashea(_mock_hwnd, mock_desktop_cls):
    mock_desktop_cls.return_value.window.return_value.descendants.side_effect = RuntimeError("boom")

    resultado = hacer_click("Guardar")

    assert resultado.exito is False


@patch("src.actions.system_control.Desktop")
@patch("src.actions.system_control.win32gui.GetForegroundWindow", return_value=123)
def test_hacer_click_error_al_ejecutar_el_click_no_crashea(_mock_hwnd, mock_desktop_cls):
    boton = MagicMock()
    boton.window_text.return_value = "Guardar"
    boton.click_input.side_effect = RuntimeError("boom")
    mock_desktop_cls.return_value.window.return_value.descendants.return_value = [boton]

    resultado = hacer_click("Guardar")

    assert resultado.exito is False


def test_hacer_click_sin_texto_no_crashea():
    resultado = hacer_click("   ")

    assert resultado.exito is False


# --- escribir_texto ---


@patch("src.actions.system_control._escribir_portapapeles")
@patch("src.actions.system_control._leer_portapapeles", return_value="contenido anterior")
@patch("src.actions.system_control._ventana_activa")
def test_escribir_texto_pega_y_restaura_el_portapapeles(mock_ventana_activa, _mock_leer, mock_escribir):
    ventana = MagicMock()
    mock_ventana_activa.return_value = ventana

    resultado = escribir_texto("hola mundo")

    assert resultado.exito is True
    ventana.type_keys.assert_called_once_with("^v")
    assert [llamada.args[0] for llamada in mock_escribir.call_args_list] == ["hola mundo", "contenido anterior"]


@patch("src.actions.system_control._escribir_portapapeles")
@patch("src.actions.system_control._leer_portapapeles", return_value=None)
@patch("src.actions.system_control._ventana_activa")
def test_escribir_texto_sin_portapapeles_previo_no_intenta_restaurar(mock_ventana_activa, _mock_leer, mock_escribir):
    mock_ventana_activa.return_value = MagicMock()

    escribir_texto("hola")

    mock_escribir.assert_called_once_with("hola")


@patch("src.actions.system_control._ventana_activa", return_value=None)
def test_escribir_texto_sin_ventana_activa_no_crashea(_mock_ventana):
    resultado = escribir_texto("hola")

    assert resultado.exito is False


@patch("src.actions.system_control._escribir_portapapeles")
@patch("src.actions.system_control._leer_portapapeles", return_value=None)
@patch("src.actions.system_control._ventana_activa")
def test_escribir_texto_error_no_crashea(mock_ventana_activa, _mock_leer, _mock_escribir):
    ventana = MagicMock()
    ventana.type_keys.side_effect = RuntimeError("boom")
    mock_ventana_activa.return_value = ventana

    resultado = escribir_texto("hola")

    assert resultado.exito is False


def test_escribir_texto_vacio_no_crashea():
    resultado = escribir_texto("   ")

    assert resultado.exito is False


@patch("src.actions.system_control.win32clipboard")
def test_leer_portapapeles_sin_texto_devuelve_none(mock_clipboard):
    mock_clipboard.GetClipboardData.side_effect = TypeError()

    assert system_control._leer_portapapeles() is None
    mock_clipboard.CloseClipboard.assert_called_once()
