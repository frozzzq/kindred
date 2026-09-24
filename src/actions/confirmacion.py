"""Sistema de confirmación para acciones críticas.

Fase 4: antes de ejecutar una acción real sobre el sistema, se pide
confirmación explícita al usuario. El "cómo" preguntar (texto o voz) es
inyectable, para que el mismo flujo en src/main.py sirva tanto al CLI de
texto como al de voz.
"""

from typing import Callable

Confirmador = Callable[[str], bool]

PALABRAS_AFIRMATIVAS = ("si", "sí", "confirmo", "dale", "hazlo", "adelante", "ok", "yes")


def es_afirmativo(texto: str) -> bool:
    """Indica si un texto (tipeado o transcrito por voz) es una confirmación."""
    palabras = texto.strip().lower().replace(",", " ").replace(".", " ").split()
    return any(palabra in PALABRAS_AFIRMATIVAS for palabra in palabras)


def confirmar_por_texto(descripcion: str) -> bool:
    """Pide confirmación por consola (usado por el CLI de texto)."""
    respuesta = input(f"{descripcion} (sí/no): ")
    return es_afirmativo(respuesta)
