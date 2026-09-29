"""Registrar el núcleo para que arranque solo al iniciar sesión en Windows (Programador de tareas).

No se ejecuta automáticamente: es un cambio persistente del sistema, fuera del repositorio. Se
ofrece como una función aparte para que el usuario (o el agente, con su confirmación explícita) la
corra cuando de verdad quiera activarlo.
"""

import subprocess
from pathlib import Path

NOMBRE_TAREA = "Jarvis-Nucleo"
RUTA_LANZADOR = Path(__file__).resolve().parent.parent.parent / "Jarvis.bat"


def registrar_tarea_programada() -> str:
    """Crea (o reemplaza) una tarea del Programador de tareas que corre "Jarvis.bat nucleo" al iniciar sesión."""
    if not RUTA_LANZADOR.exists():
        return f"No encontré el lanzador en {RUTA_LANZADOR}; no se registró nada."
    try:
        subprocess.run(
            [
                "schtasks", "/create", "/tn", NOMBRE_TAREA, "/tr", f'"{RUTA_LANZADOR}" nucleo',
                "/sc", "onlogon", "/rl", "limited", "/f",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        return f"No se pudo registrar el autoarranque: {error.stderr or error.stdout}"
    except (subprocess.SubprocessError, OSError) as error:
        return f"No se pudo registrar el autoarranque: {error}"
    return f"Listo: \"{NOMBRE_TAREA}\" arrancará solo la próxima vez que inicies sesión en Windows."


def quitar_tarea_programada() -> str:
    """Quita la tarea programada (si existe)."""
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", NOMBRE_TAREA, "/f"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        return f"No se pudo quitar el autoarranque: {error.stderr or error.stdout}"
    except (subprocess.SubprocessError, OSError) as error:
        return f"No se pudo quitar el autoarranque: {error}"
    return f'Listo: se quitó la tarea "{NOMBRE_TAREA}". El núcleo ya no arrancará solo.'


if __name__ == "__main__":
    print(registrar_tarea_programada())
