"""Los pendientes y recurrentes de la bóveda, leídos y descritos como los diría una persona.

Los usan el contexto de cada turno (para que el agente sepa qué tiene el usuario sin gastar una
llamada a herramientas), el panel de la UI y el briefing.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from src.obsidian.fechas import extraer_tags
from src.obsidian.recurrentes import parsear_linea, toca_hoy
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import MARCA_PENDIENTE, RUTA_PENDIENTES, RUTA_RECURRENTES

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_DESDE_TAGS = re.compile(r"\s*(📅|⏰|\(agregado ).*$")


@dataclass(frozen=True)
class Pendiente:
    tarea: str
    fecha: date | None
    hora: datetime | None

    def vencido(self, ahora: datetime) -> bool:
        if self.hora is not None:
            return self.hora < ahora
        return self.fecha is not None and self.fecha < ahora.date()

    def es_de_hoy(self, ahora: datetime) -> bool:
        return self.fecha == ahora.date() or (self.hora is not None and self.hora.date() == ahora.date())


def leer_pendientes() -> list[Pendiente]:
    try:
        contenido = leer_nota(RUTA_PENDIENTES) or ""
    except (RuntimeError, ValueError):
        return []
    pendientes = []
    for linea in contenido.splitlines():
        if not linea.startswith(MARCA_PENDIENTE):
            continue
        fecha, hora = extraer_tags(linea)
        tarea = _DESDE_TAGS.sub("", linea[len(MARCA_PENDIENTE):]).strip()
        if tarea:
            pendientes.append(Pendiente(tarea, fecha, hora))
    return pendientes


def recurrentes_de_hoy(ahora: datetime) -> list[tuple[str, str]]:
    """(tarea, hora "HH:MM") de las recurrentes que tocan hoy."""
    try:
        contenido = leer_nota(RUTA_RECURRENTES) or ""
    except (RuntimeError, ValueError):
        return []
    resultado = []
    for linea in contenido.splitlines():
        analizada = parsear_linea(linea)
        if analizada is not None and toca_hoy(analizada[1], ahora):
            resultado.append((analizada[0], analizada[1].hora.strftime("%H:%M")))
    return sorted(resultado, key=lambda par: par[1])


def cuando(pendiente: Pendiente, ahora: datetime) -> str:
    """ "vencido desde el sábado", "hoy a las 18:00", "mañana", "el viernes 2 de octubre"... o "" sin fecha."""
    dia = pendiente.hora.date() if pendiente.hora else pendiente.fecha
    if dia is None:
        return ""
    hora = f" a las {pendiente.hora:%H:%M}" if pendiente.hora else ""
    if pendiente.vencido(ahora):
        if dia == ahora.date():
            return f"vencido, era hoy{hora}"
        return f"vencido desde el {DIAS[dia.weekday()]} {dia.day}"
    diferencia = (dia - ahora.date()).days
    if diferencia == 0:
        return f"hoy{hora}"
    if diferencia == 1:
        return f"mañana{hora}"
    if diferencia < 7:
        return f"el {DIAS[dia.weekday()]}{hora}"
    return f"el {DIAS[dia.weekday()]} {dia.day}/{dia.month}{hora}"


def ordenar(pendientes: list[Pendiente]) -> list[Pendiente]:
    lejos = datetime.max
    return sorted(pendientes, key=lambda p: p.hora or (datetime.combine(p.fecha, datetime.max.time()) if p.fecha else lejos))


def resumen_para_contexto(ahora: datetime) -> str:
    """Pendientes agrupados por urgencia, y las recurrentes de hoy, para el contexto de cada turno.

    Agrupados y no en una lista plana: con la lista plana, qwen3:8b contestó que un pendiente del
    viernes estaba "atrasado" (visto en pruebas con la UI).
    """
    pendientes = ordenar(leer_pendientes())
    grupos = {
        "Vencidos (ya se pasó su fecha)": [p for p in pendientes if p.vencido(ahora)],
        "Para hoy": [p for p in pendientes if p.es_de_hoy(ahora) and not p.vencido(ahora)],
        "Próximos (todavía a tiempo)": [
            p for p in pendientes if not p.vencido(ahora) and not p.es_de_hoy(ahora) and (p.fecha or p.hora)
        ],
        "Sin fecha": [p for p in pendientes if not p.fecha and not p.hora],
    }
    partes = ["Pendientes:" if pendientes else "Pendientes: ninguno."]
    for titulo, elementos in grupos.items():
        if elementos:
            partes.append(f"{titulo}:")
            partes.extend(f"- {p.tarea}" + (f" ({cuando(p, ahora)})" if cuando(p, ahora) else "") for p in elementos)
    recurrentes = recurrentes_de_hoy(ahora)
    if recurrentes:
        partes.append("Recurrentes de hoy:")
        partes.extend(f"- {tarea} ({hora})" for tarea, hora in recurrentes)
    return "\n".join(partes)


def proximos(ahora: datetime, horas: int = 24) -> list[Pendiente]:
    """Pendientes con hora exacta en las próximas `horas`."""
    limite = ahora + timedelta(hours=horas)
    return [p for p in ordenar(leer_pendientes()) if p.hora is not None and ahora <= p.hora <= limite]
