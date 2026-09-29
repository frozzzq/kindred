"""Tareas recurrentes en lenguaje natural (Fase 7): "tomar medicina, diario a las 9pm",
"sacar la basura los lunes y jueves a las 8am".

Se guardan en `02-Tareas/Recurrentes.md`, una por línea, con un tag propio (🔁, no es de Obsidian
Tasks) que guarda cuándo toca: "diario HH:MM" o una lista de días de la semana + HH:MM.
"""

import re
from dataclasses import dataclass
from datetime import datetime, time

from src.obsidian.fechas import extraer_hora
from src.obsidian.texto import normalizar

# Índice 0 = lunes ... 6 = domingo, igual que datetime.weekday().
DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

_DIARIO = re.compile(r"\b(a diario|diari[oa]|todos los d[ií]as)\b")


@dataclass(frozen=True)
class Recurrencia:
    """dias vacío = todos los días; si no, los índices (0=lunes) en que toca."""

    dias: tuple[int, ...]
    hora: time


def parsear_frecuencia(texto: str) -> Recurrencia | None:
    """"diario a las 9pm", "los lunes y miércoles a las 8am"... None si no se entiende cuándo."""
    normalizado = normalizar(texto)
    hora = extraer_hora(texto)
    if hora is None:  # una recurrencia sin hora clara no sirve para avisar a tiempo
        return None
    if _DIARIO.search(normalizado):
        return Recurrencia((), hora)
    dias = tuple(sorted({indice for indice, dia in enumerate(DIAS_SEMANA) if re.search(rf"\b{normalizar(dia)}\b", normalizado)}))
    return Recurrencia(dias, hora) if dias else None


def formatear_linea(tarea: str, recurrencia: Recurrencia) -> str:
    cuando = "diario" if not recurrencia.dias else ", ".join(DIAS_SEMANA[dia] for dia in recurrencia.dias)
    return f"{tarea.strip()} 🔁 {cuando} {recurrencia.hora.strftime('%H:%M')}"


_LINEA_RECURRENTE = re.compile(r"^-?\s*(.+?)\s*🔁\s*([^\d]+?)\s*(\d{1,2}):(\d{2})")


def parsear_linea(linea: str) -> tuple[str, Recurrencia] | None:
    """Lee una línea ya guardada en Recurrentes.md. None si no tiene el formato esperado."""
    coincidencia = _LINEA_RECURRENTE.search(linea)
    if not coincidencia:
        return None
    tarea = coincidencia.group(1).strip()
    frecuencia_texto = normalizar(coincidencia.group(2))
    hora = time(int(coincidencia.group(3)), int(coincidencia.group(4)))
    if _DIARIO.search(frecuencia_texto) or not frecuencia_texto.strip():
        return tarea, Recurrencia((), hora)
    dias = tuple(sorted({indice for indice, dia in enumerate(DIAS_SEMANA) if normalizar(dia) in frecuencia_texto}))
    if not dias:
        return None
    return tarea, Recurrencia(dias, hora)


def toca_hoy(recurrencia: Recurrencia, ahora: datetime) -> bool:
    return not recurrencia.dias or ahora.weekday() in recurrencia.dias
