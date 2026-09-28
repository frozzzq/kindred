from dataclasses import dataclass

from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA


@dataclass(frozen=True)
class Paleta:
    principal: str
    oscuro: str
    claro: str


# MOTOR_ACCION son las acciones directas del sistema (abrir apps, modo seguro...), que no contesta
# ningún motor de IA. No hay un tercer agente para esto: la UI lo muestra con este color propio,
# pero lo atribuye al agente seleccionado (Crimson/Clover) para el nombre, la voz y el grafo — ver
# JarvisApp._motor_mostrado en src/ui/app.py.
PALETAS = {
    MOTOR_OLLAMA: Paleta(principal="#DC143C", oscuro="#4A0717", claro="#FF7A8F"),  # Crimson: carmesí elegante
    MOTOR_GEMINI: Paleta(principal="#9D4EDD", oscuro="#240046", claro="#E0AAFF"),  # Clover: violeta oscuro brillante
    MOTOR_ACCION: Paleta(principal="#00B4FF", oscuro="#001F3F", claro="#8BE9FF"),  # acción directa: azul futurista
}
