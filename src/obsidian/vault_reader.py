"""Lectura de la bóveda de Obsidian: listar, leer y encontrar una nota por su nombre.

La búsqueda por contenido vive en src/obsidian/indice.py (semántica + palabras clave).
"""

import difflib
from pathlib import Path, PurePosixPath

from src.obsidian.config import ruta_boveda
from src.obsidian.texto import normalizar

CARPETA_CONFIG_OBSIDIAN = ".obsidian"
SIMILITUD_MINIMA_NOMBRE = 0.85  # "Nodejs" → "Node.js", pero "Proyecto X" no se confunde con "Proyecto Y"


def resolver_ruta(ruta_relativa: str) -> Path:
    """Ruta absoluta dentro de la bóveda; rechaza rutas que intenten salir de ella.

    Las rutas pueden venir del modelo, así que no se confía en ellas: "../../algo" o una ruta
    absoluta se rechazan.
    """
    boveda = ruta_boveda().resolve()
    ruta = (boveda / ruta_relativa).resolve()
    if not ruta.is_relative_to(boveda):
        raise ValueError(f"La ruta '{ruta_relativa}' está fuera de la bóveda")
    return ruta


def _relativa(ruta: Path) -> str:
    return ruta.relative_to(ruta_boveda()).as_posix()


def listar_notas() -> list[Path]:
    """Rutas de todas las notas .md de la bóveda (excluye .obsidian)."""
    boveda = ruta_boveda()
    if not boveda.exists():
        return []
    return sorted(ruta for ruta in boveda.rglob("*.md") if CARPETA_CONFIG_OBSIDIAN not in ruta.parts)


def listar_rutas_relativas() -> list[str]:
    """Rutas de todas las notas, relativas a la bóveda y con '/' (ej. '02-Tareas/Pendientes.md')."""
    return [_relativa(ruta) for ruta in listar_notas()]


def leer_nota(ruta_relativa: str) -> str | None:
    """Contenido de una nota dada su ruta relativa, o None si no existe."""
    ruta = resolver_ruta(ruta_relativa)
    if not ruta.is_file():
        return None
    return ruta.read_text(encoding="utf-8")


def limpiar_nombre(nombre: str) -> str:
    """Quita lo que no es parte del nombre: "[[Nota|alias]]" → "Nota", "Nota#Encabezado" → "Nota"."""
    nombre = nombre.strip().strip("[]").strip()
    for separador in ("|", "#", "^"):
        nombre = nombre.split(separador, 1)[0]
    return nombre.strip().removesuffix(".md").removesuffix(".MD").strip("/ ")


def resolver_nombre(destino: str, rutas: list[str]) -> str | None:
    """Como Obsidian: por ruta si la incluye, si no por nombre de archivo; sin distinguir acentos ni mayúsculas."""
    buscado = normalizar(limpiar_nombre(destino))
    if not buscado:
        return None
    for ruta in rutas:
        if normalizar(ruta.removesuffix(".md")) == buscado:
            return ruta
    nombre = PurePosixPath(buscado).name
    for ruta in rutas:
        if normalizar(PurePosixPath(ruta).stem) == nombre:
            return ruta
    return None


def resolver_nota(nombre_o_ruta: str) -> str | None:
    """La nota que el usuario (o el modelo) quiso decir, aunque no dé la ruta exacta.

    Acepta "03-Proyectos/Jarvis.md", "Jarvis", "jarvis", "[[Jarvis]]" o un nombre casi igual
    ("Nodejs" → "Node.js"). None si no existe ninguna parecida.
    """
    rutas = listar_rutas_relativas()
    exacta = resolver_nombre(nombre_o_ruta, rutas)
    if exacta:
        return exacta
    buscado = normalizar(PurePosixPath(limpiar_nombre(nombre_o_ruta)).name)
    nombres = {normalizar(PurePosixPath(ruta).stem): ruta for ruta in rutas}
    parecidos = difflib.get_close_matches(buscado, list(nombres), n=1, cutoff=SIMILITUD_MINIMA_NOMBRE)
    return nombres[parecidos[0]] if parecidos else None
