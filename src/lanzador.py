"""Lanzador único: un menú para abrir cualquier parte del sistema (reemplaza los seis .bat de antes).

Uso:
  Jarvis.bat                 menú interactivo (Enter = abrir la app)
  Jarvis.bat ui              directo a una opción por su nombre
  Jarvis.bat ui --seccion uso      las opciones extra pasan tal cual
  Jarvis.bat texto --pruebas       cualquier modo, con la bóveda de pruebas
"""

import subprocess
import sys
from dataclasses import dataclass

from src.arranque import RAIZ_REPO
from src.consola import forzar_utf8


@dataclass(frozen=True)
class Opcion:
    clave: str
    descripcion: str
    comando: tuple[str, ...]
    grupo: str


OPCIONES = (
    Opcion("ui", "Abrir la app (voz, chat, bóveda, uso y ajustes)", ("-m", "src.main_ui"), "Usar"),
    Opcion("texto", "Chat de texto en la consola", ("-m", "src.main"), "Usar"),
    Opcion("voz", "Voz en la consola (Enter para hablar)", ("-m", "src.main_voz"), "Usar"),
    Opcion("manos-libres", "Voz manos libres (\"hey jarvis\")", ("-m", "src.main_voz_wakeword"), "Usar"),
    Opcion("nucleo", "Núcleo en esta ventana (recordatorios, briefing, diario, orden de la bóveda)", ("-m", "src.nucleo.servicio"), "Usar"),
    Opcion("pruebas", "Abrir la app con la BÓVEDA DE PRUEBAS (no toca tu bóveda real)", ("-m", "src.main_ui", "--pruebas"), "Probar"),
    Opcion("pruebas-nueva", "Igual, pero con la bóveda de pruebas recién creada", ("-m", "src.main_ui", "--pruebas-nueva"), "Probar"),
    Opcion("evaluar", "Evaluar a Crimson y Clover con escenarios reales (bóveda de pruebas)", ("-m", "src.pruebas.evaluar_agentes"), "Probar"),
    Opcion("diagnostico", "Diagnóstico: revisar que todo esté en orden", ("-m", "src.diagnostico"), "Probar"),
    Opcion("tests", "Correr los tests automáticos", ("-m", "pytest", "tests", "-q"), "Probar"),
    Opcion("indexar", "Reindexar la bóveda (memoria semántica)", ("-m", "src.obsidian.indice"), "Mantener"),
    Opcion("metricas", "Métricas de uso en la consola", ("-m", "src.main_metricas"), "Mantener"),
)


def _menu() -> Opcion | None:
    print("\n  Crimson y Clover\n")
    numero = 0
    numeradas = {}
    grupo_actual = ""
    for opcion in OPCIONES:
        if opcion.grupo != grupo_actual:
            grupo_actual = opcion.grupo
            print(f"  {grupo_actual}")
        numero += 1
        numeradas[str(numero)] = opcion
        print(f"   {numero:>2}) {opcion.descripcion}")
    print("    0) Salir\n")
    eleccion = input("  Elige una opción [Enter = 1]: ").strip() or "1"
    if eleccion == "0":
        return None
    return numeradas.get(eleccion) or next((o for o in OPCIONES if o.clave == eleccion), None)


def correr(opcion: Opcion, extra: list[str]) -> int:
    return subprocess.call([sys.executable, *opcion.comando, *extra], cwd=RAIZ_REPO)


def main() -> None:
    forzar_utf8()
    argumentos = sys.argv[1:]
    if argumentos:
        opcion = next((o for o in OPCIONES if o.clave == argumentos[0]), None)
        if opcion is None:
            print(f"No conozco la opción '{argumentos[0]}'. Opciones: {', '.join(o.clave for o in OPCIONES)}")
            sys.exit(2)
        sys.exit(correr(opcion, argumentos[1:]))
    while True:
        try:
            opcion = _menu()
        except (EOFError, KeyboardInterrupt):
            return
        if opcion is None:
            return
        try:
            correr(opcion, [])
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
