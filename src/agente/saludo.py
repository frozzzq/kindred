"""Saludo al abrir la app: lo que el usuario tiene para hoy, dicho con la personalidad del agente.

Se arma sin IA (es instantáneo y nunca inventa): con los pendientes reales de la bóveda.
"""

from datetime import datetime

from src.agente.personalidad import nombre_usuario
from src.obsidian.tareas import cuando, leer_pendientes, recurrentes_de_hoy
from src.router.intent_router import MOTOR_GEMINI

MAX_MENCIONADOS = 3


def _franja(ahora: datetime) -> str:
    if ahora.hour < 12:
        return "Buenos días"
    return "Buenas tardes" if ahora.hour < 19 else "Buenas noches"


def _lista(elementos: list[str]) -> str:
    if len(elementos) <= 1:
        return "".join(elementos)
    return ", ".join(elementos[:-1]) + " y " + elementos[-1]


def saludo_del_dia(motor: str, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    nombre = nombre_usuario()
    pendientes = leer_pendientes()
    vencidos = [p for p in pendientes if p.vencido(ahora)][:MAX_MENCIONADOS]
    de_hoy = [p for p in pendientes if p.es_de_hoy(ahora) and not p.vencido(ahora)][:MAX_MENCIONADOS]
    recurrentes = recurrentes_de_hoy(ahora)
    hoy = [f"{p.tarea} {cuando(p, ahora).removeprefix('hoy ')}".strip() for p in de_hoy]
    atrasado = [f"{p.tarea} ({cuando(p, ahora)})" for p in vencidos]

    if motor == MOTOR_GEMINI:
        partes = [f"{_franja(ahora)}{', ' + nombre if nombre else ''}."]
        if hoy:
            partes.append(f"Hoy: {_lista(hoy)}.")
        if atrasado:
            partes.append(f"Pendiente vencido: {_lista(atrasado)}.")
        if not hoy and not atrasado:
            partes.append("No tienes pendientes para hoy." + (" Solo tus recurrentes." if recurrentes else ""))
        return " ".join(partes)

    partes = [f"¡{_franja(ahora)}{', ' + nombre if nombre else ''}!"]
    if hoy:
        partes.append(f"Para hoy tienes {_lista(hoy)}.")
    if atrasado:
        partes.append(f"Y ojo, sigue pendiente {_lista(atrasado)}.")
    if not hoy and not atrasado:
        partes.append("Hoy no tienes nada pendiente, así que tómatelo con calma." if not recurrentes else "Hoy solo tienes tus recurrentes de siempre.")
    return " ".join(partes)
