"""Métricas de uso por turno: qué agente respondió, en cuánto tiempo, con qué herramientas.

Van en estado.db (tabla turnos) y alimentan el panel de la UI: uso de cada agente, velocidad
promedio, cuota de Gemini consumida hoy y herramientas más usadas.
"""

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.nucleo import estado


def registrar_turno(
    agente: str, canal: str, milisegundos: int, herramientas: list[str], llamadas_modelo: int, exito: bool
) -> None:
    """Nunca lanza: una métrica perdida no debe cortar la conversación."""
    try:
        with estado.abrir() as db:
            db.execute(
                "INSERT INTO turnos VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"), agente, canal, int(milisegundos),
                    json.dumps(herramientas), int(llamadas_modelo), int(exito),
                ),
            )
    except (sqlite3.Error, OSError):
        pass


@dataclass
class ResumenUso:
    hoy_por_agente: Counter = field(default_factory=Counter)
    semana_por_agente: Counter = field(default_factory=Counter)
    promedio_ms: dict[str, int] = field(default_factory=dict)
    llamadas_gemini_hoy: int = 0
    herramientas_top: list[tuple[str, int]] = field(default_factory=list)
    por_dia: list[tuple[str, Counter]] = field(default_factory=list)  # (AAAA-MM-DD, conteo por agente), 7 días
    fallos_semana: int = 0


def resumen(ahora: datetime | None = None, dias: int = 7) -> ResumenUso:
    ahora = ahora or datetime.now()
    desde = (ahora - timedelta(days=dias - 1)).date().isoformat()
    hoy = ahora.date().isoformat()
    try:
        with estado.abrir() as db:
            filas = db.execute(
                "SELECT momento, agente, milisegundos, herramientas, llamadas_modelo, exito FROM turnos WHERE momento >= ?",
                (desde,),
            ).fetchall()
    except (sqlite3.Error, OSError):
        return ResumenUso()

    uso = ResumenUso()
    tiempos: dict[str, list[int]] = {}
    herramientas: Counter = Counter()
    por_dia: dict[str, Counter] = {(ahora - timedelta(days=i)).date().isoformat(): Counter() for i in range(dias - 1, -1, -1)}
    for momento, agente, milisegundos, usadas, llamadas, exito in filas:
        dia = momento[:10]
        uso.semana_por_agente[agente] += 1
        if dia in por_dia:
            por_dia[dia][agente] += 1
        if dia == hoy:
            uso.hoy_por_agente[agente] += 1
            if agente == "gemini":
                uso.llamadas_gemini_hoy += llamadas
        if exito:
            tiempos.setdefault(agente, []).append(milisegundos)
        else:
            uso.fallos_semana += 1
        herramientas.update(json.loads(usadas or "[]"))
    uso.promedio_ms = {agente: int(sum(t) / len(t)) for agente, t in tiempos.items() if t}
    uso.herramientas_top = herramientas.most_common(5)
    uso.por_dia = list(por_dia.items())
    return uso
