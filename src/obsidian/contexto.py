"""Qué pasa con la bóveda después de cada respuesta.

Antes aquí se inyectaban fragmentos pasivos de la bóveda en el prompt y se
guardaba como pendiente cualquier mensaje con "pendiente"/"agenda"/
"recuérdame" (lo que llenó Pendientes.md de preguntas y frases mal
transcritas). Ahora el agente lee y escribe la bóveda con herramientas
(src/obsidian/herramientas.py), y aquí solo queda registrar la interacción
y dejar que la reflexión aprenda de ella.
"""

from src.agente.reflexion import reflexionar_si_toca
from src.obsidian.vault_writer import registrar_interaccion


def evaluar_guardado(texto: str, respuesta: str, motor: str) -> None:
    """Registra la interacción en el log y, si ya toca, lanza la reflexión en segundo plano."""
    try:
        registrar_interaccion(texto, respuesta, motor)
    except RuntimeError:
        return
    reflexionar_si_toca()
