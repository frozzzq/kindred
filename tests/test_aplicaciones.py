import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.actions import aplicaciones
from src.actions.aplicaciones import App, abrir_aplicacion, elegir_apps, indice_apps, reconoce_aplicacion

APPS = [
    App("Adobe Photoshop 2021", "{id}\\Photoshop.exe"),
    App("Calculator", "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"),
    App("Google Chrome", "Chrome"),
    App("Chrome Remote Desktop", "chrome.remote"),
    App("Paint", "Microsoft.Paint!App"),
    App("Paint 3D", "Microsoft.MSPaint!App"),
    App("Visual Studio", "VisualStudio.1"),
    App("Visual Studio Code", "Microsoft.VisualStudioCode"),
    App("Discord", "com.squirrel.Discord.Discord"),
    App("Servicios de componentes", "comexp.msc"),
    App("Affinity", "Canva.Affinity"),
]


@pytest.fixture(autouse=True)
def cache_temporal(tmp_path, monkeypatch):
    """Nada de leer el menú Inicio real ni la caché real."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)


@pytest.mark.parametrize(
    "consulta, esperado",
    [
        ("Paint", "Paint"),  # exacta gana sobre "Paint 3D"
        ("visual studio", "Visual Studio"),
        ("photoshop", "Adobe Photoshop 2021"),  # contenida en el nombre
        ("fotoshop", "Adobe Photoshop 2021"),  # mal escrita
        ("discor", "Discord"),
        ("chrome", "Google Chrome"),  # contenida en dos, pero una es clara
    ],
)
def test_elegir_apps_encuentra_la_correcta(consulta, esperado):
    assert [a.nombre for a in elegir_apps(consulta, APPS)] == [esperado]


def test_elegir_apps_sin_parecido_no_devuelve_nada():
    assert elegir_apps("hoja de calculo de impuestos", APPS) == []


@pytest.mark.parametrize("consulta", ["mis pendientes", "la nota de pendientes", "mi correo"])
def test_frases_que_no_son_apps_no_coinciden_por_parecido_parcial(consulta):
    """Caso real: "mis pendientes" abría "Servicios de componentes" (pendientes ≈ componentes)."""
    assert elegir_apps(consulta, APPS) == []


@pytest.mark.parametrize("consulta, esperado", [("afinity", "Affinity"), ("visual code", "Visual Studio Code")])
def test_cada_palabra_dicha_se_compara_con_las_del_nombre(consulta, esperado):
    assert [a.nombre for a in elegir_apps(consulta, APPS)] == [esperado]


def test_elegir_apps_ambigua_devuelve_opciones():
    apps = [App("Notas rápidas", "a"), App("Notas de voz", "b")]

    assert {a.nombre for a in elegir_apps("notas", apps)} == {"Notas rápidas", "Notas de voz"}


@patch("src.actions.aplicaciones._leer_apps_de_windows", return_value=APPS)
def test_indice_se_guarda_en_cache_y_se_reutiliza(mock_leer):
    indice_apps()
    indice_apps()

    assert mock_leer.call_count == 1


@patch("src.actions.aplicaciones._leer_apps_de_windows", return_value=APPS)
def test_indice_se_renueva_si_la_cache_es_vieja(mock_leer):
    indice_apps()
    ruta = aplicaciones._ruta_cache()
    hace_dos_dias = time.time() - 2 * 24 * 3600
    os.utime(ruta, (hace_dos_dias, hace_dos_dias))

    indice_apps()

    assert mock_leer.call_count == 2


@patch("src.actions.aplicaciones._leer_apps_de_windows", return_value=APPS)
def test_indice_con_cache_corrupta_se_regenera(mock_leer):
    ruta = aplicaciones._ruta_cache()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{no es json", encoding="utf-8")

    assert indice_apps() == APPS


@patch("src.actions.aplicaciones.subprocess.run")
def test_leer_apps_de_windows_interpreta_el_json_de_powershell(mock_run):
    mock_run.return_value = MagicMock(stdout=json.dumps([{"Name": " Administración de equipos", "AppID": "x"}]))

    assert aplicaciones._leer_apps_de_windows() == [App("Administración de equipos", "x")]


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps", return_value=APPS)
def test_abrir_aplicacion_lanza_por_appid(_mock_indice, mock_popen):
    resultado = abrir_aplicacion("fotoshop")

    assert resultado.exito is True
    assert "Photoshop" in resultado.mensaje
    mock_popen.assert_called_once_with(["explorer.exe", "shell:AppsFolder\\{id}\\Photoshop.exe"])


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps", return_value=APPS)
def test_alias_base_calculadora(_mock_indice, mock_popen):
    resultado = abrir_aplicacion("calculadora.")

    assert resultado.exito is True
    mock_popen.assert_called_once_with(["explorer.exe", "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"])


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps", return_value=APPS)
def test_alias_de_la_boveda(_mock_indice, mock_popen, tmp_path, monkeypatch):
    boveda = tmp_path / "boveda"
    (boveda / "00-Sistema").mkdir(parents=True)
    (boveda / "00-Sistema" / "Alias-Aplicaciones.md").write_text("- el editor: Visual Studio Code\n", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(boveda))

    abrir_aplicacion("el editor")

    mock_popen.assert_called_once_with(["explorer.exe", "shell:AppsFolder\\Microsoft.VisualStudioCode"])


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps")
def test_si_no_la_encuentra_renueva_el_indice_por_si_se_instalo_hace_poco(mock_indice, mock_popen):
    mock_indice.side_effect = lambda renovar=False: APPS + [App("Obsidian", "md.obsidian")] if renovar else APPS

    resultado = abrir_aplicacion("obsidian")

    assert resultado.exito is True
    mock_indice.assert_any_call(renovar=True)


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps", return_value=APPS)
def test_app_inexistente_no_lanza_nada(_mock_indice, mock_popen):
    resultado = abrir_aplicacion("hoja de calculo de impuestos")

    assert resultado.exito is False
    mock_popen.assert_not_called()


@patch("src.actions.aplicaciones.subprocess.Popen")
@patch("src.actions.aplicaciones.indice_apps", return_value=[App("Grabadora de voz", "a"), App("Grabadora de pantalla", "b")])
def test_app_ambigua_pregunta_cual(_mock_indice, mock_popen):
    resultado = abrir_aplicacion("grabadora")

    assert resultado.exito is False
    assert "¿Cuál abro?" in resultado.mensaje
    mock_popen.assert_not_called()


@patch("src.actions.aplicaciones.indice_apps", side_effect=OSError("powershell no disponible"))
def test_si_no_puede_leer_el_indice_no_crashea(_mock_indice):
    assert abrir_aplicacion("paint").exito is False
    assert reconoce_aplicacion("paint") is True  # que la herramienta reporte el error, no el atajo


@patch("src.actions.aplicaciones.indice_apps", return_value=APPS)
def test_reconoce_aplicacion(_mock_indice):
    assert reconoce_aplicacion("discord") is True
    assert reconoce_aplicacion("mis pendientes") is False
