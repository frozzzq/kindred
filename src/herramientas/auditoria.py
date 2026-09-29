"""Registro de cada acción que el agente hace (o intenta hacer), para poder revisarlo después."""

import json
import re
from dataclasses import dataclass
from datetime import datetime

from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import escribir_nota

RUTA_REGISTRO_ACCIONES = "00-Sistema/Registro-Acciones.md"
MAX_CARACTERES_RESULTADO = 200
_LINEA = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (\w+) · `(\w+)` .*?→ (.*)$")


@dataclass(frozen=True)
class Accion:
    momento: str
    canal: str
    herramienta: str
    resultado: str


def ultimas_acciones(cantidad: int = 8) -> list[Accion]:
    """Las acciones más recientes del registro, de la más nueva a la más vieja."""
    try:
        contenido = leer_nota(RUTA_REGISTRO_ACCIONES) or ""
    except (RuntimeError, ValueError):
        return []
    acciones = []
    for linea in reversed(contenido.splitlines()):
        coincidencia = _LINEA.match(linea)
        if coincidencia:
            acciones.append(Accion(*coincidencia.groups()))
            if len(acciones) >= cantidad:
                break
    return acciones


def registrar_accion(canal: str, herramienta: str, argumentos: dict, resultado: str) -> None:
    """Agrega una línea al registro de acciones. Si la bóveda no está disponible, no bloquea la acción."""
    detalle = json.dumps(argumentos, ensure_ascii=False)
    resultado = " ".join(resultado.split())[:MAX_CARACTERES_RESULTADO]
    linea = f"- {datetime.now():%Y-%m-%d %H:%M} · {canal} · `{herramienta}` {detalle} → {resultado}"
    try:
        escribir_nota(RUTA_REGISTRO_ACCIONES, linea)
    except (RuntimeError, OSError):
        pass
