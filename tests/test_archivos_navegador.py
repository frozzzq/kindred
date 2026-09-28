from unittest.mock import patch

import pytest

from src.actions.archivos import abrir_carpeta, carpetas_permitidas, es_carpeta_conocida, resolver_carpeta
from src.actions.navegador import abrir_url, parece_url


@pytest.fixture
def inicio_falso(tmp_path, monkeypatch):
    """Un "home" de mentira con las carpetas de usuario, para no tocar las reales."""
    for nombre in ("Desktop", "Documents", "Downloads", "Pictures"):
        (tmp_path / nombre).mkdir()
    (tmp_path / "Documents" / "Proyectos").mkdir()
    (tmp_path / "Secreto").mkdir()
    monkeypatch.setattr("src.actions.archivos.Path.home", lambda: tmp_path)
    monkeypatch.delenv("CARPETAS_PERMITIDAS", raising=False)
    return tmp_path


def test_carpetas_permitidas_por_defecto_son_las_de_usuario(inicio_falso):
    assert {c.name for c in carpetas_permitidas()} == {"Desktop", "Documents", "Downloads", "Pictures"}


def test_carpetas_permitidas_configurables(inicio_falso, monkeypatch):
    monkeypatch.setenv("CARPETAS_PERMITIDAS", f"{inicio_falso / 'Documents'};")

    assert [c.name for c in carpetas_permitidas()] == ["Documents"]


@pytest.mark.parametrize(
    "dicho, esperada",
    [
        ("descargas", "Downloads"),
        ("Imágenes", "Pictures"),
        ("proyectos", "Proyectos"),
        ("documentos.", "Documents"),
        ("de descargas", "Downloads"),  # queda de "carpeta de descargas" al quitar "carpeta "
    ],
)
def test_resolver_carpeta(inicio_falso, dicho, esperada):
    assert resolver_carpeta(dicho).name == esperada


@pytest.mark.parametrize(
    "dicho, esperado",
    [
        ("descargas", True),
        ("mis documentos", True),
        ("el escritorio", False),  # es_carpeta_conocida no quita artículos: eso lo hace el router antes
        ("escritorio", True),
        ("spotify", False),
        ("proyectos", False),  # es una subcarpeta real, pero no una de las conocidas por nombre
    ],
)
def test_es_carpeta_conocida(dicho, esperado):
    assert es_carpeta_conocida(dicho) is esperado


def test_no_resuelve_carpetas_fuera_de_las_permitidas(inicio_falso):
    assert resolver_carpeta("secreto") is None
    assert resolver_carpeta(str(inicio_falso / "Secreto")) is None
    assert resolver_carpeta(str(inicio_falso / "Documents" / ".." / "Secreto")) is None


@patch("src.actions.archivos.os.startfile")
def test_abrir_carpeta(mock_startfile, inicio_falso):
    resultado = abrir_carpeta("descargas")

    assert resultado.exito is True
    mock_startfile.assert_called_once_with((inicio_falso / "Downloads").resolve())


@patch("src.actions.archivos.os.startfile")
def test_abrir_carpeta_inexistente_no_abre_nada(mock_startfile, inicio_falso):
    assert abrir_carpeta("carpeta que no existe").exito is False
    mock_startfile.assert_not_called()


@pytest.mark.parametrize("texto", ["youtube.com", "https://github.com/x", "docs.python.org/3/"])
def test_parece_url(texto):
    assert parece_url(texto) is True


@pytest.mark.parametrize("texto", ["bloc de notas", "spotify", "carpeta descargas"])
def test_no_parece_url(texto):
    assert parece_url(texto) is False


@patch("src.actions.navegador.webbrowser.open_new_tab", return_value=True)
def test_abrir_url_agrega_https(mock_abrir):
    resultado = abrir_url("youtube.com")

    assert resultado.exito is True
    mock_abrir.assert_called_once_with("https://youtube.com")


@pytest.mark.parametrize("url", ["file:///C:/Windows/win.ini", "javascript:alert(1)", "ftp://servidor/archivo"])
@patch("src.actions.navegador.webbrowser.open_new_tab")
def test_abrir_url_solo_acepta_paginas_web(mock_abrir, url):
    assert abrir_url(url).exito is False
    mock_abrir.assert_not_called()
