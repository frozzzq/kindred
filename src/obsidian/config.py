"""Configuracion compartida para el modulo de Obsidian."""

import os
from pathlib import Path


def ruta_boveda() -> Path:
    """Devuelve la ruta a la bóveda de Obsidian configurada por variable de entorno."""
    ruta = os.getenv("OBSIDIAN_VAULT_PATH")
    if not ruta:
        raise RuntimeError("OBSIDIAN_VAULT_PATH no está configurada")
    return Path(ruta)
