"""Lectura y busqueda simple sobre la boveda de Obsidian.

Fase 2: busqueda por coincidencia de palabras clave. Se puede mejorar a
embeddings mas adelante sin cambiar la interfaz publica de este modulo.
"""

from dataclasses import dataclass
from pathlib import Path

from src.obsidian.config import ruta_boveda

CARPETA_CONFIG_OBSIDIAN = ".obsidian"
LONGITUD_MINIMA_PALABRA = 4
CONTEXTO_FRAGMENTO = 80


def listar_notas() -> list[Path]:
    """Devuelve las rutas de todas las notas .md de la bóveda (excluye .obsidian)."""
    boveda = ruta_boveda()
    if not boveda.exists():
        return []
    return [
        ruta for ruta in boveda.rglob("*.md")
        if CARPETA_CONFIG_OBSIDIAN not in ruta.parts
    ]


def leer_nota(ruta_relativa: str) -> str | None:
    """Lee el contenido de una nota dada su ruta relativa a la bóveda."""
    ruta = ruta_boveda() / ruta_relativa
    if not ruta.exists():
        return None
    return ruta.read_text(encoding="utf-8")


@dataclass
class ResultadoBusqueda:
    ruta_relativa: str
    fragmento: str
    coincidencias: int


def buscar_en_boveda(texto: str, max_resultados: int = 3) -> list[ResultadoBusqueda]:
    """Busca notas relevantes por coincidencia simple de palabras clave."""
    palabras = _palabras_significativas(texto)
    if not palabras:
        return []

    boveda = ruta_boveda()
    resultados: list[ResultadoBusqueda] = []

    for ruta in listar_notas():
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        contenido_normalizado = contenido.lower()
        coincidencias = sum(1 for palabra in palabras if palabra in contenido_normalizado)
        if coincidencias == 0:
            continue
        resultados.append(
            ResultadoBusqueda(
                ruta_relativa=str(ruta.relative_to(boveda)),
                fragmento=_extraer_fragmento(contenido, palabras),
                coincidencias=coincidencias,
            )
        )

    resultados.sort(key=lambda r: r.coincidencias, reverse=True)
    return resultados[:max_resultados]


def _palabras_significativas(texto: str) -> set[str]:
    palabras = texto.lower().split()
    return {p.strip(".,;:!?¿¡") for p in palabras if len(p) >= LONGITUD_MINIMA_PALABRA}


def _extraer_fragmento(contenido: str, palabras: set[str]) -> str:
    contenido_normalizado = contenido.lower()
    for palabra in palabras:
        indice = contenido_normalizado.find(palabra)
        if indice != -1:
            inicio = max(0, indice - CONTEXTO_FRAGMENTO)
            fin = min(len(contenido), indice + CONTEXTO_FRAGMENTO)
            return contenido[inicio:fin].strip()
    return contenido[:CONTEXTO_FRAGMENTO].strip()
