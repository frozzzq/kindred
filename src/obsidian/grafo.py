"""Grafo de la bóveda de Obsidian: notas, carpetas y las conexiones entre ellas.

Dos tipos de conexión:
- Enlace: un [[enlace]] (o [texto](nota.md)) de una nota a otra, igual que en
  el grafo de Obsidian.
- Carpeta: cada carpeta es un nodo unido a sus notas y a su carpeta padre. No
  existe en Obsidian, pero le da estructura al grafo aunque las notas todavía
  no estén enlazadas entre sí.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote

from src.obsidian.vault_reader import leer_nota, listar_notas, listar_rutas_relativas

# [[Nota]], [[Nota|alias]], [[Nota#Encabezado]], ![[Nota]] — el destino es lo que va antes de | # ^
_ENLACE_WIKI = re.compile(r"\[\[([^\]|#^]+)[^\]]*\]\]")
_ENLACE_MARKDOWN = re.compile(r"\]\(([^)\s]+?\.md)\)")


@dataclass(frozen=True)
class Nodo:
    id: str  # ruta relativa: "01-Perfil/Yo.md" para notas, "01-Perfil" para carpetas
    nombre: str
    es_carpeta: bool


@dataclass(frozen=True)
class Arista:
    origen: str
    destino: str
    es_enlace: bool  # False: pertenencia a una carpeta


@dataclass(frozen=True)
class Grafo:
    nodos: tuple[Nodo, ...]
    aristas: tuple[Arista, ...]


def firma_boveda() -> tuple[tuple[str, int], ...]:
    """Huella barata de la bóveda (rutas + fecha de modificación) para saber si cambió algo."""
    return tuple((ruta.as_posix(), ruta.stat().st_mtime_ns) for ruta in listar_notas())


def construir_grafo() -> Grafo:
    rutas = listar_rutas_relativas()
    nodos: dict[str, Nodo] = {}
    aristas: dict[frozenset[str], Arista] = {}

    def agregar_arista(origen: str, destino: str, es_enlace: bool) -> None:
        clave = frozenset((origen, destino))
        if origen == destino:
            return
        if clave not in aristas or es_enlace:  # un enlace real gana sobre la conexión por carpeta
            aristas[clave] = Arista(origen, destino, es_enlace)

    for ruta in rutas:
        nodos[ruta] = Nodo(ruta, PurePosixPath(ruta).stem, es_carpeta=False)
        hijo = ruta
        for carpeta in PurePosixPath(ruta).parents:
            if str(carpeta) == ".":
                break
            nodos.setdefault(str(carpeta), Nodo(str(carpeta), carpeta.name, es_carpeta=True))
            agregar_arista(str(carpeta), hijo, es_enlace=False)
            hijo = str(carpeta)

    for ruta in rutas:
        contenido = leer_nota(ruta) or ""
        destinos = _ENLACE_WIKI.findall(contenido) + [unquote(d) for d in _ENLACE_MARKDOWN.findall(contenido)]
        for destino in destinos:
            resuelto = _resolver_enlace(destino, rutas)
            if resuelto:
                agregar_arista(ruta, resuelto, es_enlace=True)

    return Grafo(nodos=tuple(nodos.values()), aristas=tuple(aristas.values()))


def _resolver_enlace(destino: str, rutas: list[str]) -> str | None:
    """Como Obsidian: por ruta si la incluye, si no por nombre de archivo (sin distinguir mayúsculas)."""
    destino = destino.strip().removesuffix(".md").lower()
    if not destino:
        return None
    for ruta in rutas:
        if ruta.removesuffix(".md").lower() == destino:
            return ruta
    nombre = PurePosixPath(destino).name
    for ruta in rutas:
        if PurePosixPath(ruta).stem.lower() == nombre:
            return ruta
    return None  # imágenes u otros adjuntos, o notas que aún no existen
