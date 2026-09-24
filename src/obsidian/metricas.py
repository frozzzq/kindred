"""Métricas de uso del asistente, a partir del log de interacciones que ya
se guarda en la bóveda de Obsidian (Fase 2).

Fase 5: responde "qué % resuelve Ollama vs Gemini" reutilizando lo que ya
se registra, sin un sistema de logging aparte. También cuenta los intentos
fallidos de Gemini (MOTOR_GEMINI_FALLO) para poder medir su tasa de éxito
real y decidir si vale la pena ajustar el router.
"""

import re
from dataclasses import dataclass, field

from src.obsidian.vault_reader import leer_nota
from src.router.intent_router import MOTOR_GEMINI, MOTOR_GEMINI_FALLO

RUTA_LOG = "00-Sistema/Logs-Interacciones.md"
PATRON_ENTRADA = re.compile(r"^### .+ \((\w+)\)\s*$", re.MULTILINE)


@dataclass
class Metricas:
    conteo_por_motor: dict[str, int] = field(default_factory=dict)

    @property
    def total_resueltas(self) -> int:
        """Interacciones que terminaron con una respuesta (no cuenta los fallos de Gemini)."""
        return sum(cantidad for motor, cantidad in self.conteo_por_motor.items() if motor != MOTOR_GEMINI_FALLO)

    def porcentaje(self, motor: str) -> float:
        """% de las interacciones resueltas que atendió este motor."""
        if self.total_resueltas == 0:
            return 0.0
        return round(self.conteo_por_motor.get(motor, 0) / self.total_resueltas * 100, 1)

    def tasa_exito_gemini(self) -> float | None:
        """% de las veces que se intentó Gemini y sí respondió. None si nunca se intentó."""
        exitos = self.conteo_por_motor.get(MOTOR_GEMINI, 0)
        fallos = self.conteo_por_motor.get(MOTOR_GEMINI_FALLO, 0)
        intentos = exitos + fallos
        if intentos == 0:
            return None
        return round(exitos / intentos * 100, 1)


def calcular_metricas() -> Metricas:
    """Lee el log de interacciones de la bóveda y cuenta cuántas atendió cada motor."""
    contenido = leer_nota(RUTA_LOG)
    if not contenido:
        return Metricas()

    conteo: dict[str, int] = {}
    for motor in PATRON_ENTRADA.findall(contenido):
        conteo[motor] = conteo.get(motor, 0) + 1

    return Metricas(conteo_por_motor=conteo)
