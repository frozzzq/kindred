"""Lectura y búsqueda sobre la bóveda de Obsidian.

La búsqueda es por coincidencia de palabras clave. Se puede mejorar a
embeddings más adelante sin cambiar la interfaz pública de este módulo.
"""

from dataclasses import dataclass
from pathlib import Path

from src.obsidian.config import ruta_boveda

CARPETA_CONFIG_OBSIDIAN = ".obsidian"
LONGITUD_MINIMA_PALABRA = 4
CONTEXTO_FRAGMENTO = 150

# El log de conversaciones contiene todo lo que se ha dicho, así que ganaba
# casi cualquier búsqueda y le metía al agente fragmentos de charlas viejas.
# Se sigue usando para métricas, pero no como fuente de conocimiento.
EXCLUIDAS_DE_BUSQUEDA = ("00-Sistema/Logs-Interacciones.md",)


def resolver_ruta(ruta_relativa: str) -> Path:
    """Ruta absoluta dentro de la bóveda; rechaza rutas que intenten salir de ella.

    Las rutas pueden venir del modelo (herramienta leer_nota), así que no se
    confía en ellas: "../../algo" o una ruta absoluta se rechazan.
    """
    boveda = ruta_boveda().resolve()
    ruta = (boveda / ruta_relativa).resolve()
    if not ruta.is_relative_to(boveda):
        raise ValueError(f"La ruta '{ruta_relativa}' está fuera de la bóveda")
    return ruta


def _relativa(ruta: Path) -> str:
    return ruta.relative_to(ruta_boveda()).as_posix()


def listar_notas() -> list[Path]:
    """Devuelve las rutas de todas las notas .md de la bóveda (excluye .obsidian)."""
    boveda = ruta_boveda()
    if not boveda.exists():
        return []
    return sorted(
        ruta for ruta in boveda.rglob("*.md")
        if CARPETA_CONFIG_OBSIDIAN not in ruta.parts
    )


def listar_rutas_relativas() -> list[str]:
    """Rutas de todas las notas, relativas a la bóveda y con '/' (ej. '02-Tareas/Pendientes.md')."""
    return [_relativa(ruta) for ruta in listar_notas()]


def leer_nota(ruta_relativa: str) -> str | None:
    """Lee el contenido de una nota dada su ruta relativa a la bóveda."""
    ruta = resolver_ruta(ruta_relativa)
    if not ruta.is_file():
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

    resultados: list[ResultadoBusqueda] = []
    for ruta in listar_notas():
        relativa = _relativa(ruta)
        if relativa in EXCLUIDAS_DE_BUSQUEDA:
            continue
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        contenido_normalizado = contenido.lower()
        coincidencias = sum(1 for palabra in palabras if palabra in contenido_normalizado)
        if coincidencias == 0:
            continue
        resultados.append(
            ResultadoBusqueda(
                ruta_relativa=relativa,
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
