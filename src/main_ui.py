"""Punto de entrada de la UI de escritorio (Flet). Ver src/arranque.py para --pruebas y --seccion."""

import sys

import flet as ft

from src.arranque import preparar
from src.ui.app import JarvisApp


def main() -> None:
    opciones = preparar(sys.argv[1:])

    def construir(page: ft.Page) -> None:
        app = JarvisApp(page)
        app.montar()
        app.ir_a(opciones.seccion)

    ft.run(construir)


if __name__ == "__main__":
    main()
