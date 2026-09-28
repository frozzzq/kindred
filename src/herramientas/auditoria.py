"""Registro de cada acción que el agente hace (o intenta hacer), para poder revisarlo después."""

import json
from datetime import datetime

from src.obsidian.vault_writer import escribir_nota

RUTA_REGISTRO_ACCIONES = "00-Sistema/Registro-Acciones.md"
MAX_CARACTERES_RESULTADO = 200


def registrar_accion(canal: str, herramienta: str, argumentos: dict, resultado: str) -> None:
    """Agrega una línea al registro de acciones. Si la bóveda no está disponible, no bloquea la acción."""
    detalle = json.dumps(argumentos, ensure_ascii=False)
    resultado = " ".join(resultado.split())[:MAX_CARACTERES_RESULTADO]
    linea = f"- {datetime.now():%Y-%m-%d %H:%M} · {canal} · `{herramienta}` {detalle} → {resultado}"
    try:
        escribir_nota(RUTA_REGISTRO_ACCIONES, linea)
    except (RuntimeError, OSError):
        pass
