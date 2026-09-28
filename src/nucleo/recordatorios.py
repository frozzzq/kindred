"""Qué recordatorios tocan avisar ahora: pendientes con ⏰ ya vencido, y tareas recurrentes cuya
hora ya llegó hoy. No marca nada como avisado por sí solo (eso lo hace servicio.py, después de
avisar de verdad): así un fallo al avisar no queda registrado como si sí se hubiera avisado.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from src.nucleo import estado
from src.obsidian.fechas import extraer_tags
from src.obsidian.recurrentes import parsear_linea, toca_hoy
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import RUTA_PENDIENTES, RUTA_RECURRENTES

_MARCAS_PENDIENTE = ("- [ ] ", "- [x] ")
_DESDE_EL_TAG_DE_FECHA = re.compile(r"\s*📅.*$")


@dataclass(frozen=True)
class Recordatorio:
    clave: str  # única y estable, para no avisar dos veces lo mismo (estado.ya_avisado)
    tarea: str


def texto_pendiente(linea: str) -> str:
    """La tarea sola, sin la marca de checkbox ni los tags de fecha/hora ni el "(agregado ...)".

    Pública porque también la usa src/nucleo/briefing.py.
    """
    texto = linea.strip()
    for marca in _MARCAS_PENDIENTE:
        if texto.startswith(marca):
            texto = texto[len(marca):]
            break
    return _DESDE_EL_TAG_DE_FECHA.sub("", texto).strip()


def pendientes_por_avisar(ahora: datetime | None = None) -> list[Recordatorio]:
    """Pendientes con un ⏰ ya vencido y que todavía no se avisaron."""
    ahora = ahora or datetime.now()
    contenido = leer_nota(RUTA_PENDIENTES) or ""
    resultado = []
    for linea in contenido.splitlines():
        if not linea.strip():
            continue
        _fecha, hora = extraer_tags(linea)
        if hora is None or hora > ahora:
            continue
        tarea = texto_pendiente(linea)
        clave = f"pendiente:{tarea}:{hora.isoformat()}"
        if not estado.ya_avisado(clave):
            resultado.append(Recordatorio(clave, tarea))
    return resultado


def recurrentes_por_avisar(ahora: datetime | None = None) -> list[Recordatorio]:
    """Tareas recurrentes que tocan hoy, cuya hora ya llegó y que todavía no se avisaron hoy."""
    ahora = ahora or datetime.now()
    contenido = leer_nota(RUTA_RECURRENTES) or ""
    resultado = []
    for linea in contenido.splitlines():
        analizada = parsear_linea(linea)
        if analizada is None or not toca_hoy(analizada[1], ahora):
            continue
        tarea, recurrencia = analizada
        objetivo = ahora.replace(hour=recurrencia.hora.hour, minute=recurrencia.hora.minute, second=0, microsecond=0)
        if ahora < objetivo:
            continue
        clave = f"recurrente:{tarea}:{ahora.date().isoformat()}"
        if not estado.ya_avisado(clave):
            resultado.append(Recordatorio(clave, tarea))
    return resultado
