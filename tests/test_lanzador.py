from unittest.mock import patch

import pytest

from src import lanzador


def test_cada_opcion_tiene_un_nombre_unico_y_un_modulo_que_existe():
    import importlib.util

    claves = [o.clave for o in lanzador.OPCIONES]
    assert len(claves) == len(set(claves))
    for opcion in lanzador.OPCIONES:
        modulo = opcion.comando[1]
        assert importlib.util.find_spec(modulo) is not None, modulo


@patch("src.lanzador.subprocess.call", return_value=0)
def test_por_nombre_pasa_las_opciones_extra(mock_call, monkeypatch):
    monkeypatch.setattr("sys.argv", ["lanzador", "texto", "--pruebas"])

    with pytest.raises(SystemExit) as salida:
        lanzador.main()

    assert salida.value.code == 0
    assert mock_call.call_args.args[0][1:] == ["-m", "src.main", "--pruebas"]


@patch("src.lanzador.subprocess.call", return_value=0)
def test_el_menu_con_enter_abre_la_app_y_0_sale(mock_call, monkeypatch):
    respuestas = iter(["", "0"])
    monkeypatch.setattr("builtins.input", lambda _texto: next(respuestas))
    monkeypatch.setattr("sys.argv", ["lanzador"])

    lanzador.main()

    assert mock_call.call_count == 1
    assert mock_call.call_args.args[0][1:] == ["-m", "src.main_ui"]


def test_opcion_desconocida(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["lanzador", "no-existe"])

    with pytest.raises(SystemExit):
        lanzador.main()

    assert "No conozco la opción" in capsys.readouterr().out
