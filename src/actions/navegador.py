"""Abrir páginas web en el navegador predeterminado. La Fase 10 agrega manejo de pestañas y Playwright."""

import re
import webbrowser
from urllib.parse import urlparse

from src.actions.system_control import ResultadoAccion

_PARECE_DOMINIO = re.compile(r"^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$", re.IGNORECASE)


def parece_url(texto: str) -> bool:
    """Ej. "youtube.com" o "https://github.com/x" sí; "bloc de notas" no."""
    return bool(_PARECE_DOMINIO.match(texto.strip()))


def abrir_url(url: str) -> ResultadoAccion:
    """Abre la URL en una pestaña nueva. Solo http(s): nada de file:, javascript: ni similares."""
    url = url.strip()
    # Cualquier esquema ("javascript:", "file:", "ftp:") que no sea http(s) se rechaza, no se "corrige".
    # "localhost:3000" no cuenta como esquema: lo que sigue a los dos puntos es un puerto.
    tiene_esquema = re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", url, re.IGNORECASE)
    if not tiene_esquema:
        url = f"https://{url}"
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return ResultadoAccion(exito=False, mensaje=f"Solo puedo abrir páginas web (http/https), no '{url}'.")
    if not webbrowser.open_new_tab(url):
        return ResultadoAccion(exito=False, mensaje=f"No pude abrir el navegador para {partes.netloc}.")
    return ResultadoAccion(exito=True, mensaje=f"Abriendo {partes.netloc}...")
