from unittest.mock import patch

from src.actions.system_control import abrir_aplicacion


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
