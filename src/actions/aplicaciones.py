"""Abrir cualquier aplicación instalada por su nombre, aunque se diga distinto o mal transcrito.

En vez de una lista blanca fija, se usa el índice del menú Inicio de Windows
(`Get-StartApps`: nombre visible + AppID, incluye apps de escritorio y de la
Tienda) y se lanza con `explorer.exe shell:AppsFolder\\<AppID>`, que sirve
para ambos tipos. Solo se abren apps registradas en el menú Inicio, nunca un
comando arbitrario.
"""

import difflib
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from src.actions.system_control import SIGNOS_A_QUITAR, ResultadoAccion
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import normalizar

RUTA_ALIAS = "00-Sistema/Alias-Aplicaciones.md"
HORAS_VIGENCIA_INDICE = 24
# Cada palabra dicha debe parecerse a alguna palabra del nombre: "fotoshop" ↔ "photoshop" da 0.82,
# pero "pendientes" ↔ "componentes" da 0.57 (antes "mis pendientes" abría "Servicios de componentes").
SIMILITUD_PALABRA = 0.75
MARGEN_PARA_DECIDIR = 0.15  # si dos candidatas quedan más cerca que esto, se pregunta cuál
_PALABRAS_VACIAS = {"el", "la", "los", "las", "de", "del", "mi", "mis", "un", "una", "app", "aplicacion", "programa"}
MAX_OPCIONES = 3
_COMANDO_INDICE = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"

# Nombres coloquiales → nombre en el menú Inicio (en esta PC varios están en inglés).
# Se pueden agregar más en la bóveda, en Alias-Aplicaciones.md ("- el editor: Visual Studio Code").
ALIAS_BASE = {
    "calculadora": "Calculator",
    "bloc de notas": "Notepad",
    "block de notas": "Notepad",  # transcripción común de "bloc"
    "notas": "Notepad",
    "explorador": "Explorador de archivos",
    "archivos": "Explorador de archivos",
    "navegador": "Google Chrome",
    "vscode": "Visual Studio Code",
    "visual code": "Visual Studio Code",
    "configuracion": "Configuración",
}


@dataclass(frozen=True)
class App:
    nombre: str
    app_id: str


def _ruta_cache() -> Path:
    return Path(os.getenv("LOCALAPPDATA", Path.home())) / "kindred" / "apps.json"


def _leer_apps_de_windows() -> list[App]:
    salida = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _COMANDO_INDICE],
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    ).stdout
    datos = json.loads(salida)
    if isinstance(datos, dict):
        datos = [datos]
    return [App(d["Name"].strip(), d["AppID"]) for d in datos if d.get("Name") and d.get("AppID")]


def indice_apps(renovar: bool = False) -> list[App]:
    """Apps instaladas, desde una caché local que se renueva cada día (leer Windows tarda un par de segundos)."""
    ruta = _ruta_cache()
    vigente = ruta.exists() and time.time() - ruta.stat().st_mtime < HORAS_VIGENCIA_INDICE * 3600
    if vigente and not renovar:
        try:
            return [App(**d) for d in json.loads(ruta.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # caché corrupta: se regenera
    apps = _leer_apps_de_windows()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps([asdict(a) for a in apps], ensure_ascii=False), encoding="utf-8")
    return apps


def _alias() -> dict[str, str]:
    alias = {normalizar(k): v for k, v in ALIAS_BASE.items()}
    try:
        contenido = leer_nota(RUTA_ALIAS) or ""
    except (RuntimeError, ValueError):
        return alias
    for linea in contenido.splitlines():
        coincidencia = re.match(r"^\s*-\s*(.+?)\s*:\s*(.+?)\s*$", linea)
        if coincidencia:
            alias[normalizar(coincidencia.group(1))] = coincidencia.group(2)
    return alias


def _similitud(buscado: str, nombre: str) -> float:
    """Promedio del parecido de cada palabra dicha con la palabra más parecida del nombre.

    0 si alguna palabra dicha no se parece a ninguna ("fotoshop" ↔ "Adobe
    Photoshop 2021" sí; "mis pendientes" ↔ "Servicios de componentes" no).
    """
    palabras_nombre = nombre.split()
    palabras = [p for p in buscado.split() if p not in _PALABRAS_VACIAS] or buscado.split()
    if not palabras or not palabras_nombre:
        return 0.0
    parecidos = []
    for palabra in palabras:
        mejor = max(difflib.SequenceMatcher(None, palabra, p).ratio() for p in palabras_nombre)
        if mejor < SIMILITUD_PALABRA:
            return 0.0
        parecidos.append(mejor)
    return sum(parecidos) / len(parecidos)


def elegir_apps(consulta: str, apps: list[App]) -> list[App]:
    """Una sola app si hay una clara; varias si es ambiguo; ninguna si no se parece a nada."""
    buscado = normalizar(consulta)
    exactas = [a for a in apps if normalizar(a.nombre) == buscado]
    if exactas:
        return exactas[:1]

    contienen = [a for a in apps if buscado in normalizar(a.nombre)]
    if contienen:
        puntuadas = [(difflib.SequenceMatcher(None, buscado, normalizar(a.nombre)).ratio(), a) for a in contienen]
    else:
        puntuadas = [(s, a) for a in apps if (s := _similitud(buscado, normalizar(a.nombre))) > 0]
    puntuadas.sort(key=lambda par: par[0], reverse=True)

    if len(puntuadas) >= 2 and puntuadas[0][0] - puntuadas[1][0] < MARGEN_PARA_DECIDIR:
        return [a for _, a in puntuadas[:MAX_OPCIONES]]
    return [a for _, a in puntuadas[:1]]


def reconoce_aplicacion(nombre: str) -> bool:
    """¿Se parece a alguna app instalada? Para decidir si "abre X" es una app o algo para el agente.

    Si no se puede leer el índice, responde True: que la herramienta reporte el error.
    """
    consulta = nombre.strip(SIGNOS_A_QUITAR)
    consulta = _alias().get(normalizar(consulta), consulta)
    try:
        return bool(elegir_apps(consulta, indice_apps()))
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return True


def abrir_aplicacion(nombre: str) -> ResultadoAccion:
    """Abre la aplicación instalada que mejor coincida con el nombre dicho."""
    consulta = nombre.strip(SIGNOS_A_QUITAR)
    if not consulta:
        return ResultadoAccion(exito=False, mensaje="¿Qué aplicación quieres que abra?")
    consulta = _alias().get(normalizar(consulta), consulta)

    try:
        candidatas = elegir_apps(consulta, indice_apps())
        if not candidatas:  # quizá se instaló después de armar la caché
            candidatas = elegir_apps(consulta, indice_apps(renovar=True))
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as error:
        return ResultadoAccion(exito=False, mensaje=f"No pude leer la lista de aplicaciones instaladas: {error}")

    if not candidatas:
        return ResultadoAccion(exito=False, mensaje=f"No encontré ninguna aplicación instalada llamada '{nombre}'.")
    if len(candidatas) > 1:
        opciones = ", ".join(a.nombre for a in candidatas)
        return ResultadoAccion(exito=False, mensaje=f"Encontré varias: {opciones}. ¿Cuál abro?")

    app = candidatas[0]
    try:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app.app_id}"])
    except OSError as error:
        return ResultadoAccion(exito=False, mensaje=f"No se pudo abrir {app.nombre}: {error}")
    return ResultadoAccion(exito=True, mensaje=f"Abriendo {app.nombre}...")
