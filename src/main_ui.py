"""Punto de entrada de la UI de escritorio (Flet)."""

import flet as ft
from dotenv import load_dotenv

from src.consola import forzar_utf8
from src.obsidian.estructura import asegurar_estructura_boveda
from src.ui.app import construir_app


def main() -> None:
    forzar_utf8()
    # override=True: ver comentario en src/main.py sobre el choque de
    # OLLAMA_HOST con la variable de entorno del servidor de Ollama.
    load_dotenv(override=True)
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[aviso] No se pudo preparar la bóveda de Obsidian: {error}")

    ft.run(construir_app)


if __name__ == "__main__":
    main()
