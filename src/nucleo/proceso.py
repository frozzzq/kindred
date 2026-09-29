"""Iniciar, detener y vigilar el núcleo como proceso de fondo (sin ventana), desde la UI o el lanzador.

El núcleo corre en su propio proceso (ver el aviso de win11toast/onnxruntime en src/nucleo/avisos.py).
Su salida va a %LOCALAPPDATA%\\kindred\\nucleo.log. Está "vivo" si su última vuelta fue hace poco.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.local import carpeta_local
from src.nucleo import estado
from src.nucleo.estado import CLAVE_ULTIMA_VUELTA, INTERVALO_SEGUNDOS

RAIZ_REPO = Path(__file__).resolve().parents[2]
CLAVE_PID = "nucleo.pid"
SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW de Windows


def ruta_log() -> Path:
    return carpeta_local() / "nucleo.log"


def segundos_desde_ultima_vuelta() -> float | None:
    ultima = estado.leer_valor(CLAVE_ULTIMA_VUELTA)
    if not ultima:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(ultima)).total_seconds()
    except ValueError:
        return None


def esta_vivo() -> bool:
    segundos = segundos_desde_ultima_vuelta()
    return segundos is not None and segundos < INTERVALO_SEGUNDOS * 3


def iniciar() -> str:
    if esta_vivo():
        return "El núcleo ya está corriendo."
    entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with open(ruta_log(), "a", encoding="utf-8") as log:
        log.write(f"\n--- inicio {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        log.flush()
        proceso = subprocess.Popen(
            [sys.executable, "-m", "src.nucleo.servicio"],
            cwd=RAIZ_REPO,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=entorno,
            creationflags=SIN_VENTANA if sys.platform == "win32" else 0,
        )
    estado.guardar_valor(CLAVE_PID, str(proceso.pid))
    return f"Núcleo iniciado en segundo plano (registro en {ruta_log()})."


def detener() -> str:
    pid = estado.leer_valor(CLAVE_PID)
    if not pid:
        return "No tengo registrado ningún núcleo iniciado desde aquí."
    try:
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, timeout=15, check=True)
    except (subprocess.SubprocessError, OSError):
        return "No se pudo detener el núcleo (quizá ya estaba cerrado)."
    estado.guardar_valor(CLAVE_PID, "")
    estado.guardar_valor(CLAVE_ULTIMA_VUELTA, "")
    return "Núcleo detenido."
