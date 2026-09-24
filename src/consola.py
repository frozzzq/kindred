"""Utilidad de consola: fuerza salida en UTF-8.

La consola de Windows (cp1252) no puede imprimir ciertos caracteres que
los modelos generan (emojis, etc.), lo que crasheaba el CLI con
UnicodeEncodeError. Se fuerza UTF-8 en stdout/stderr al arrancar cada
punto de entrada, reemplazando lo que no se pueda mostrar en vez de
crashear.
"""

import sys


def forzar_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
