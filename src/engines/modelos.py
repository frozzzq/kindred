"""Tipos compartidos entre los clientes de motores (Ollama, Gemini)."""

from dataclasses import dataclass, field


@dataclass
class RespuestaMotor:
    """Resultado uniforme de preguntarle algo a un motor (local o cloud).

    Nunca se lanzan excepciones hacia afuera: un fallo se reporta aquí para
    que el router/CLI puedan decidir un fallback en vez de crashear.
    herramientas_usadas registra qué herramientas se ejecutaron de verdad,
    para poder detectar cuando el modelo dice haber hecho algo que no hizo.
    """

    exito: bool
    texto: str = ""
    error: str = ""
    herramientas_usadas: list[str] = field(default_factory=list)
