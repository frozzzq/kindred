"""Arranque común de todos los puntos de entrada: consola en UTF-8, .env, bóveda y opciones.

Opciones:
  --pruebas        usa la bóveda de pruebas (%LOCALAPPDATA%\\kindred\\boveda-pruebas) en vez de la
                   real; la crea con notas de ejemplo si no existe.
  --pruebas-nueva  igual, pero la vuelve a crear desde cero.
  --seccion NOMBRE (solo la UI) abre directo en: inicio, chat, boveda, uso o ajustes.
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from src.consola import forzar_utf8

RAIZ_REPO = Path(__file__).resolve().parents[1]


def preparar(argumentos: list[str] | None = None) -> argparse.Namespace:
    forzar_utf8()
    # override=True: OLLAMA_HOST también existe como variable de entorno de Windows para configurar
    # el SERVIDOR de Ollama (0.0.0.0:11434). Sin override, esa variable del sistema tapa la URL
    # completa del .env (pensada para el CLIENTE) y las llamadas a Ollama fallan.
    load_dotenv(RAIZ_REPO / ".env", override=True)

    lector = argparse.ArgumentParser(add_help=False)
    lector.add_argument("--pruebas", action="store_true")
    lector.add_argument("--pruebas-nueva", action="store_true")
    lector.add_argument("--seccion", default="inicio")
    opciones, _resto = lector.parse_known_args(argumentos)

    if opciones.pruebas or opciones.pruebas_nueva:
        from src.local import carpeta_local
        from src.pruebas.boveda_ejemplo import crear_boveda_de_pruebas

        boveda = carpeta_local() / "boveda-pruebas"
        if opciones.pruebas_nueva or not boveda.exists():
            boveda = crear_boveda_de_pruebas()
        os.environ["OBSIDIAN_VAULT_PATH"] = str(boveda)
        print(f"[pruebas] Usando la bóveda de pruebas: {boveda}")

    try:
        from src.obsidian.estructura import asegurar_estructura_boveda

        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")
    return opciones
