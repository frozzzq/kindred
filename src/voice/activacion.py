"""Activación por nombre del agente y ventana de conversación abierta.

Decir "Crimson" (o "Clover", o "Jarvis") activa a ese agente y abre una
ventana de conversación: mientras no pase un minuto sin hablar, lo que se
diga va directo al agente sin repetir su nombre. Al cerrarse la ventana hay
que volver a llamarlo por su nombre. Decir el nombre de otro agente con la
ventana abierta le pasa la palabra a ese otro.
"""

import difflib
import re
import time
from collections.abc import Callable

from src.obsidian.vault_writer import normalizar
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA

NOMBRES = {"crimson": MOTOR_OLLAMA, "clover": MOTOR_GEMINI, "jarvis": MOTOR_ACCION}
# Cómo transcribe Whisper los nombres a veces (visto en los logs reales: "Yervis").
VARIANTES = {"yervis": "jarvis", "yarvis": "jarvis", "jarbis": "jarvis", "yarbis": "jarvis", "llervis": "jarvis"}
SIMILITUD_MINIMA = 0.8  # "grimson"/"crimsom" sí; "crimen" no
DURACION_VENTANA_SEGUNDOS = 60.0
_MULETILLAS_DE_LLAMADO = {"hey", "oye", "ey", "ok", "okay"}


def _nombre_en(palabra: str) -> str | None:
    palabra = normalizar(palabra)
    if palabra in NOMBRES:
        return palabra
    if palabra in VARIANTES:
        return VARIANTES[palabra]
    for nombre in NOMBRES:
        if difflib.SequenceMatcher(None, palabra, nombre).ratio() >= SIMILITUD_MINIMA:
            return nombre
    return None


def detectar_nombre(texto: str) -> tuple[str | None, str]:
    """Busca el nombre de un agente en lo transcrito.

    Devuelve (motor del agente o None, el texto sin el nombre). Si solo lo
    llamaron ("Crimson", "Oye Crimson"), el texto restante queda vacío.
    """
    for palabra in re.finditer(r"\w+", texto):
        nombre = _nombre_en(palabra.group())
        if nombre is None:
            continue
        antes = texto[: palabra.start()].strip()
        if normalizar(re.sub(r"[^\w\s]", "", antes)).strip() in _MULETILLAS_DE_LLAMADO | {""}:
            antes = ""  # "Oye Crimson, ..." → el "oye" era solo para llamarlo
        resto = f"{antes} {texto[palabra.end():]}"
        resto = re.sub(r"^[\s,.;:!¡]+", "", resto)
        resto = re.sub(r"\s+([,.;:!?])", r"\1", resto)
        resto = re.sub(r",\s*([?!.])", r"\1", resto)  # "¿Qué hora es, Crimson?" → "¿Qué hora es?"
        resto = re.sub(r"[\s,;:]+$", "", resto)
        return NOMBRES[nombre], resto.strip()
    return None, texto.strip()


class VentanaConversacion:
    def __init__(
        self,
        duracion: float = DURACION_VENTANA_SEGUNDOS,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._duracion = duracion
        self._reloj = reloj
        self._abierta_hasta = 0.0
        self.agente: str | None = None

    @property
    def abierta(self) -> bool:
        return self._reloj() < self._abierta_hasta

    def segundos_restantes(self) -> float:
        return max(0.0, self._abierta_hasta - self._reloj())

    def extender(self) -> None:
        """Reinicia el minuto: se llama cada vez que el usuario habla o el agente termina de hablar."""
        self._abierta_hasta = self._reloj() + self._duracion

    def cerrar(self) -> None:
        self._abierta_hasta = 0.0

    def procesar(self, texto: str) -> tuple[str | None, str | None]:
        """Decide qué hacer con una frase escuchada.

        Devuelve (agente, mensaje):
        - (None, None): no llamaron a nadie y la ventana está cerrada → se ignora.
        - (agente, ""): solo lo llamaron por su nombre → queda escuchando.
        - (agente, mensaje): hay que responderle al usuario.
        """
        motor, resto = detectar_nombre(texto)
        if motor is not None:
            self.agente = motor
            self.extender()
            return motor, resto
        if self.abierta and self.agente is not None:
            self.extender()
            return self.agente, texto.strip()
        return None, None
