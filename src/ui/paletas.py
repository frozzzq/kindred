from dataclasses import dataclass

from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA


@dataclass(frozen=True)
class Paleta:
    principal: str
    oscuro: str
    claro: str


# Jarvis se identifica con MOTOR_ACCION: es el orquestador (router automático
# y acciones del sistema), no un motor de IA en sí.
PALETAS = {
    MOTOR_OLLAMA: Paleta(principal="#DC143C", oscuro="#4A0717", claro="#FF7A8F"),  # Crimson: carmesí elegante
    MOTOR_GEMINI: Paleta(principal="#9D4EDD", oscuro="#240046", claro="#E0AAFF"),  # Clover: violeta oscuro brillante
    MOTOR_ACCION: Paleta(principal="#00B4FF", oscuro="#001F3F", claro="#8BE9FF"),  # Jarvis: azul futurista
}
