"""Estado técnico del núcleo: qué recordatorios y briefings ya se avisaron, para no repetirlos.

Vive fuera de la bóveda (que es para lo que el usuario lee/edita) en un SQLite local, igual patrón
que la caché de apps en src/actions/aplicaciones.py::_ruta_cache.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def ruta_estado() -> Path:
    return Path(os.getenv("LOCALAPPDATA", Path.home())) / "kindred" / "estado.db"


@contextmanager
def _conexion():
    ruta = ruta_estado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    try:
        conexion.execute("CREATE TABLE IF NOT EXISTS avisados (clave TEXT PRIMARY KEY, avisado_en TEXT NOT NULL)")
        conexion.execute("CREATE TABLE IF NOT EXISTS briefings (tipo TEXT PRIMARY KEY, fecha TEXT NOT NULL)")
        yield conexion
        conexion.commit()
    finally:
        conexion.close()


def ya_avisado(clave: str) -> bool:
    with _conexion() as conexion:
        fila = conexion.execute("SELECT 1 FROM avisados WHERE clave = ?", (clave,)).fetchone()
        return fila is not None


def marcar_avisado(clave: str, ahora_iso: str) -> None:
    with _conexion() as conexion:
        conexion.execute("INSERT OR REPLACE INTO avisados (clave, avisado_en) VALUES (?, ?)", (clave, ahora_iso))


def briefing_de_hoy(tipo: str) -> str | None:
    """Fecha (ISO, solo el día) del último briefing de este tipo ("matutino"/"cierre"), o None."""
    with _conexion() as conexion:
        fila = conexion.execute("SELECT fecha FROM briefings WHERE tipo = ?", (tipo,)).fetchone()
        return fila[0] if fila else None


def marcar_briefing(tipo: str, fecha_iso: str) -> None:
    with _conexion() as conexion:
        conexion.execute("INSERT OR REPLACE INTO briefings (tipo, fecha) VALUES (?, ?)", (tipo, fecha_iso))
