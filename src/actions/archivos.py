"""Acceso a carpetas del usuario, siempre dentro de CARPETAS_PERMITIDAS.

Fase 6: solo abrir carpetas. La Fase 10 agrega crear, buscar, mover y borrar
archivos, con las mismas carpetas raíz como límite.
"""

import os
from pathlib import Path

from src.actions.system_control import SIGNOS_A_QUITAR, ResultadoAccion
from src.obsidian.texto import normalizar

# Cómo se dicen en español → carpeta real (en disco se llaman en inglés aunque Windows las muestre traducidas).
NOMBRES_CARPETAS = {
    "escritorio": "Desktop",
    "documentos": "Documents",
    "mis documentos": "Documents",
    "descargas": "Downloads",
    "imagenes": "Pictures",
    "fotos": "Pictures",
}


def carpetas_permitidas() -> list[Path]:
    """Carpetas raíz donde el agente puede trabajar: CARPETAS_PERMITIDAS (separadas por ';') o las de usuario."""
    configuradas = os.getenv("CARPETAS_PERMITIDAS", "").strip()
    if configuradas:
        return [Path(c.strip()).expanduser().resolve() for c in configuradas.split(";") if c.strip()]
    inicio = Path.home()
    return [(inicio / nombre).resolve() for nombre in dict.fromkeys(NOMBRES_CARPETAS.values())]


def _dentro_de_permitidas(ruta: Path) -> bool:
    return any(ruta == raiz or ruta.is_relative_to(raiz) for raiz in carpetas_permitidas())


def es_carpeta_conocida(nombre: str) -> bool:
    """True si el nombre (sin "abre "/artículo) es una de las carpetas de usuario reconocidas.

    Se usa para decidir la intención ANTES de buscarlo entre las aplicaciones instaladas: "el
    escritorio" o "mis documentos" se confundían con apps de nombre parecido ("Conexión a
    Escritorio remoto", "Documentación de Referencia") porque el atajo probaba primero como app.
    """
    return normalizar(nombre.strip(SIGNOS_A_QUITAR)) in NOMBRES_CARPETAS


def resolver_carpeta(nombre: str) -> Path | None:
    """Carpeta permitida que corresponde al nombre: una raíz ("descargas"), una ruta, o una subcarpeta directa."""
    consulta = nombre.strip(SIGNOS_A_QUITAR)
    # "carpeta de descargas" deja "de descargas" tras quitar el prefijo "carpeta "; el "de" no es
    # parte del nombre.
    if normalizar(consulta).startswith("de "):
        consulta = consulta[len("de "):].strip(SIGNOS_A_QUITAR)
    clave = normalizar(consulta)
    inicio = Path.home()

    if clave in NOMBRES_CARPETAS:
        ruta = (inicio / NOMBRES_CARPETAS[clave]).resolve()
        return ruta if _dentro_de_permitidas(ruta) else None

    ruta_directa = Path(consulta).expanduser()
    if ruta_directa.is_absolute():
        ruta = ruta_directa.resolve()
        return ruta if ruta.is_dir() and _dentro_de_permitidas(ruta) else None

    for raiz in carpetas_permitidas():
        if normalizar(raiz.name) == clave:
            return raiz
        if raiz.is_dir():
            for hija in raiz.iterdir():
                if hija.is_dir() and normalizar(hija.name) == clave:
                    return hija
    return None


def abrir_carpeta(nombre: str) -> ResultadoAccion:
    """Abre una carpeta permitida en el Explorador de archivos."""
    ruta = resolver_carpeta(nombre)
    if ruta is None:
        return ResultadoAccion(exito=False, mensaje=f"No encontré una carpeta permitida llamada '{nombre}'.")
    try:
        os.startfile(ruta)
    except OSError as error:
        return ResultadoAccion(exito=False, mensaje=f"No se pudo abrir la carpeta {ruta.name}: {error}")
    return ResultadoAccion(exito=True, mensaje=f"Abriendo la carpeta {ruta.name}...")
