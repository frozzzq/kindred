"""Registro de herramientas con permisos: la única puerta por la que el agente actúa.

Cada herramienta declara su riesgo, y ejecutar() aplica la misma política sin
importar quién la pida (Crimson, Clover, un atajo por palabras clave y, más
adelante, Telegram o una llamada): modo seguro → confirmación → ejecución →
auditoría. Así una acción irreversible nunca depende de que el modelo "se
acuerde" de preguntar.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum

from src.actions.confirmacion import Confirmador


class Riesgo(Enum):
    LECTURA = "lectura"  # solo consulta: se ejecuta directo y no se audita
    BAJO = "bajo"  # acción reversible: se ejecuta directo y se audita
    ALTO = "alto"  # irreversible o hacia afuera (borrar, enviar): confirma siempre
    CRITICO = "critico"  # ej. comandos de terminal: confirma mostrando exactamente qué hará


RIESGOS_QUE_CONFIRMAN = {Riesgo.ALTO, Riesgo.CRITICO}

MENSAJE_MODO_SEGURO = (
    "Estoy en modo seguro: solo puedo consultar, no hacer acciones. Di \"sal del modo seguro\" para permitirlas."
)
MENSAJE_CANCELADO = "Cancelado: no lo confirmaste, así que no hice nada."

Auditor = Callable[[str, str, dict, str], None]  # (canal, herramienta, argumentos, resultado)


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    grupo: str
    funcion: Callable[..., str]
    parametros: dict[str, str] = field(default_factory=dict)  # nombre → descripción; todos requeridos
    riesgo: Riesgo | Callable[[dict], Riesgo] = Riesgo.LECTURA  # puede depender de los argumentos
    pregunta: Callable[[dict], str] | None = None  # qué preguntar al confirmar; si no, una genérica

    def riesgo_para(self, argumentos: dict) -> Riesgo:
        return self.riesgo(argumentos) if callable(self.riesgo) else self.riesgo

    def pregunta_para(self, argumentos: dict) -> str:
        if self.pregunta is not None:
            return self.pregunta(argumentos)
        detalle = ", ".join(f"{clave}: {valor}" for clave, valor in argumentos.items())
        return f"¿Confirmas que haga esto: {self.nombre} ({detalle})?"

    def esquema_parametros(self) -> dict:
        return {
            "type": "object",
            "properties": {nombre: {"type": "string", "description": d} for nombre, d in self.parametros.items()},
            "required": list(self.parametros),
        }


@dataclass(frozen=True)
class ContextoEjecucion:
    """Desde dónde se pidió la acción y cómo confirmarla en ese canal (diálogo, voz, Telegram...)."""

    confirmador: Confirmador
    canal: str = "texto"


class Registro:
    def __init__(self, herramientas: Iterable[Herramienta], auditar: Auditor | None = None) -> None:
        self._por_nombre: dict[str, Herramienta] = {}
        for herramienta in herramientas:
            if herramienta.nombre in self._por_nombre:
                raise ValueError(f"Herramienta duplicada: {herramienta.nombre}")
            self._por_nombre[herramienta.nombre] = herramienta
        self._auditar = auditar
        self.modo_seguro = False

    def nombres(self) -> set[str]:
        return set(self._por_nombre)

    def _de_grupos(self, grupos: Iterable[str] | None) -> list[Herramienta]:
        herramientas = list(self._por_nombre.values())
        if grupos is None:
            return herramientas
        grupos = set(grupos)
        return [h for h in herramientas if h.grupo in grupos]

    def esquemas_ollama(self, grupos: Iterable[str] | None = None) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {"name": h.nombre, "description": h.descripcion, "parameters": h.esquema_parametros()},
            }
            for h in self._de_grupos(grupos)
        ]

    def declaraciones_gemini(self, grupos: Iterable[str] | None = None) -> list[dict]:
        return [
            {"name": h.nombre, "description": h.descripcion, "parameters_json_schema": h.esquema_parametros()}
            for h in self._de_grupos(grupos)
        ]

    def ejecutar(self, nombre: str, argumentos: dict | None, contexto: ContextoEjecucion) -> str:
        """Aplica la política de permisos y ejecuta. Siempre devuelve texto, nunca lanza."""
        herramienta = self._por_nombre.get(nombre)
        if herramienta is None:
            return f"La herramienta '{nombre}' no existe."
        argumentos = argumentos or {}
        riesgo = herramienta.riesgo_para(argumentos)

        if self.modo_seguro and riesgo is not Riesgo.LECTURA:
            resultado = MENSAJE_MODO_SEGURO
        elif riesgo in RIESGOS_QUE_CONFIRMAN and not contexto.confirmador(herramienta.pregunta_para(argumentos)):
            resultado = MENSAJE_CANCELADO
        else:
            try:
                resultado = herramienta.funcion(**argumentos)
            except (TypeError, ValueError, OSError, RuntimeError) as error:
                resultado = f"Error al usar {nombre}: {error}"

        if riesgo is not Riesgo.LECTURA and self._auditar is not None:
            self._auditar(contexto.canal, nombre, argumentos, resultado)
        return resultado

    def ejecutor(self, contexto: ContextoEjecucion) -> Callable[[str, dict], str]:
        """La función que reciben los motores para ejecutar herramientas en este contexto."""
        return lambda nombre, argumentos: self.ejecutar(nombre, argumentos, contexto)
