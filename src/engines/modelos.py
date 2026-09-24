"""Tipos compartidos entre los clientes de motores (Ollama, Gemini)."""

from dataclasses import dataclass


@dataclass
class RespuestaMotor:
    """Resultado uniforme de preguntarle algo a un motor (local o cloud).

    Nunca se lanzan excepciones hacia afuera: un fallo se reporta aquí para
    que el router/CLI puedan decidir un fallback en vez de crashear.
    """

    exito: bool
    texto: str = ""
    error: str = ""
