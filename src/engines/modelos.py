"""Tipos compartidos entre los clientes de motores (Ollama, Gemini)."""

from dataclasses import dataclass, field


@dataclass
class RespuestaMotor:
    """Resultado uniforme de preguntarle algo a un motor (local o cloud).

    Nunca se lanzan excepciones hacia afuera: un fallo se reporta aquí para
    que el router/CLI puedan decidir un fallback en vez de crashear.
    herramientas_usadas registra qué herramientas se ejecutaron de verdad,
    para poder detectar cuando el modelo dice haber hecho algo que no hizo.
    resultados_herramientas es lo que cada una devolvió, en el mismo orden
    (mismo índice que herramientas_usadas): sirve para el caso contrario,
    cuando el modelo niega un cambio que sí hizo — se puede corregir con lo
    que la herramienta ya confirmó, sin tener que preguntarle de nuevo.
    """

    exito: bool
    texto: str = ""
    error: str = ""
    herramientas_usadas: list[str] = field(default_factory=list)
    resultados_herramientas: list[str] = field(default_factory=list)
