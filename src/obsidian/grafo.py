"""Grafo de la bóveda de Obsidian: notas, carpetas y las conexiones entre ellas.

Dos tipos de conexión:
- Enlace: un [[enlace]] (o [texto](nota.md)) de una nota a otra, igual que en
  el grafo de Obsidian.
- Carpeta: cada carpeta es un nodo unido a sus notas y a su carpeta padre. No
  existe en Obsidian, pero le da estructura al grafo aunque las notas todavía
  no estén enlazadas entre sí.

Las notas de 00-Sistema (registros, estado) no son parte del "cerebro": no se dibujan.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote

from src.obsidian.estructura import es_de_sistema
from src.obsidian.vault_reader import leer_nota, listar_notas, listar_rutas_relativas, resolver_nombre

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

    @property
    def total_notas(self) -> int:
        return sum(1 for nodo in self.nodos if not nodo.es_carpeta)

    @property
    def total_enlaces(self) -> int:
        return sum(1 for arista in self.aristas if arista.es_enlace)

    def huerfanas(self) -> list[str]:
        """Notas sin ningún enlace (ni entrante ni saliente)."""
        enlazadas = {extremo for arista in self.aristas if arista.es_enlace for extremo in (arista.origen, arista.destino)}
        return [nodo.id for nodo in self.nodos if not nodo.es_carpeta and nodo.id not in enlazadas]


def enlaces_de(contenido: str, rutas: list[str]) -> set[str]:
    """Rutas de las notas a las que enlaza un contenido (solo las que existen)."""
    destinos = _ENLACE_WIKI.findall(contenido) + [unquote(d) for d in _ENLACE_MARKDOWN.findall(contenido)]
    return {resuelto for destino in destinos if (resuelto := resolver_nombre(destino, rutas))}


def firma_boveda() -> tuple[tuple[str, int], ...]:
    """Huella barata de la bóveda (rutas + fecha de modificación) para saber si cambió algo."""
    return tuple((ruta.as_posix(), ruta.stat().st_mtime_ns) for ruta in listar_notas())


def construir_grafo() -> Grafo:
    rutas = [ruta for ruta in listar_rutas_relativas() if not es_de_sistema(ruta)]
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
        for destino in enlaces_de(leer_nota(ruta) or "", rutas):
            agregar_arista(ruta, destino, es_enlace=True)

    return Grafo(nodos=tuple(nodos.values()), aristas=tuple(aristas.values()))
