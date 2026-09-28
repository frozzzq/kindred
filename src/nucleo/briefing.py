"""Briefing matutino y cierre del día: un resumen breve y natural de los pendientes de hoy, los
vencidos y las tareas recurrentes de hoy, redactado por Crimson (Ollama) a partir de datos reales
de la bóveda (nunca inventados). Si Ollama falla, hay un resumen simple armado sin IA de respaldo.
"""

from datetime import datetime

from src.engines.ollama_client import preguntar_ollama
from src.nucleo.recordatorios import texto_pendiente
from src.obsidian.fechas import extraer_tags
from src.obsidian.recurrentes import parsear_linea, toca_hoy
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import RUTA_PENDIENTES, RUTA_RECURRENTES

PROMPT_MATUTINO = """Eres Crimson, el asistente personal del usuario. Redacta un breve saludo de buenos días \
(2 a 4 oraciones, para leer en voz alta: nada de markdown, viñetas ni emojis) con lo que tiene para hoy. Usa \
SOLO los datos de abajo, nunca inventes nada que no esté ahí.

Pendientes de hoy:
{pendientes_hoy}

Vencidos (no se hicieron a tiempo):
{vencidos}

Tareas recurrentes de hoy:
{recurrentes_hoy}

Si las tres listas dicen "(ninguno)", dile que no tiene nada pendiente para hoy y que tenga un buen día. Si hay \
vencidos, menciónalos con amabilidad, sin regañarlo."""

PROMPT_CIERRE = """Eres Crimson, el asistente personal del usuario. Redacta un breve resumen de cierre del día \
(2 a 4 oraciones, para leer en voz alta: nada de markdown, viñetas ni emojis). Usa SOLO los datos de abajo.

Pendientes de hoy que no se completaron:
{pendientes_hoy}

Si la lista dice "(ninguno)", felicítalo por terminar todo, con naturalidad y sin exagerar."""


def _listar(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "(ninguno)"


def _datos_del_dia(ahora: datetime) -> tuple[list[str], list[str], list[str]]:
    """(pendientes de hoy, vencidos, recurrentes de hoy), todos como texto simple de la tarea."""
    pendientes_hoy: list[str] = []
    vencidos: list[str] = []
    for linea in (leer_nota(RUTA_PENDIENTES) or "").splitlines():
        if not linea.strip():
            continue
        fecha, _hora = extraer_tags(linea)
        if fecha is None:
            continue
        tarea = texto_pendiente(linea)
        if fecha == ahora.date():
            pendientes_hoy.append(tarea)
        elif fecha < ahora.date():
            vencidos.append(tarea)

    recurrentes_hoy = []
    for linea in (leer_nota(RUTA_RECURRENTES) or "").splitlines():
        analizada = parsear_linea(linea)
        if analizada is not None and toca_hoy(analizada[1], ahora):
            recurrentes_hoy.append(analizada[0])

    return pendientes_hoy, vencidos, recurrentes_hoy


def _respaldo_matutino(pendientes_hoy: list[str], vencidos: list[str], recurrentes_hoy: list[str]) -> str:
    if not (pendientes_hoy or vencidos or recurrentes_hoy):
        return "Buenos días. No tienes nada pendiente para hoy."
    partes = ["Buenos días."]
    if pendientes_hoy:
        partes.append(f"Para hoy: {', '.join(pendientes_hoy)}.")
    if vencidos:
        partes.append(f"Vencidos: {', '.join(vencidos)}.")
    if recurrentes_hoy:
        partes.append(f"También: {', '.join(recurrentes_hoy)}.")
    return " ".join(partes)


def _respaldo_cierre(pendientes_hoy: list[str]) -> str:
    if not pendientes_hoy:
        return "Terminaste todo lo de hoy. Buen trabajo."
    return f"Te quedaron pendientes de hoy: {', '.join(pendientes_hoy)}."


def generar_matutino(ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    pendientes_hoy, vencidos, recurrentes_hoy = _datos_del_dia(ahora)
    prompt = PROMPT_MATUTINO.format(
        pendientes_hoy=_listar(pendientes_hoy), vencidos=_listar(vencidos), recurrentes_hoy=_listar(recurrentes_hoy)
    )
    respuesta = preguntar_ollama(prompt)
    if respuesta.exito and respuesta.texto.strip():
        return respuesta.texto.strip()
    return _respaldo_matutino(pendientes_hoy, vencidos, recurrentes_hoy)


def generar_cierre(ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    pendientes_hoy, _vencidos, _recurrentes_hoy = _datos_del_dia(ahora)
    prompt = PROMPT_CIERRE.format(pendientes_hoy=_listar(pendientes_hoy))
    respuesta = preguntar_ollama(prompt)
    if respuesta.exito and respuesta.texto.strip():
        return respuesta.texto.strip()
    return _respaldo_cierre(pendientes_hoy)
