"""Carpeta local de la app (%LOCALAPPDATA%\\kindred) y sus bases SQLite: estado técnico fuera de la bóveda.

Ahí viven el estado del núcleo, el índice semántico, los respaldos de notas editadas y los ajustes
de la UI. La bóveda es para lo que el usuario lee y edita; esto es de la máquina.
"""

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REINTENTOS_AL_PREPARAR = 6
TIMEOUT_SEGUNDOS = 30

_preparadas: set[str] = set()
_preparando = threading.Lock()


def carpeta_local() -> Path:
    carpeta = Path(os.getenv("LOCALAPPDATA", Path.home())) / "kindred"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _preparar(ruta: Path, esquema: str) -> None:
    """Modo WAL y tablas, una sola vez por base y por proceso.

    Pasar a WAL una base recién creada necesita acceso exclusivo, y el timeout de SQLite no aplica
    ahí: dos hilos abriéndola a la vez daban "database is locked" (5 de 30 intentos con 4 hilos,
    medido). Con el candado no pasa dentro del proceso; los reintentos cubren a otro proceso (la UI
    y el núcleo arrancando juntos).
    """
    clave = str(ruta)
    if clave in _preparadas:
        return
    with _preparando:
        if clave in _preparadas:
            return
        for intento in range(REINTENTOS_AL_PREPARAR):
            db = sqlite3.connect(ruta, timeout=TIMEOUT_SEGUNDOS)
            try:
                db.execute("PRAGMA journal_mode=WAL")
                db.executescript(esquema)
                db.commit()
                break
            except sqlite3.OperationalError:
                if intento == REINTENTOS_AL_PREPARAR - 1:
                    raise
                time.sleep(0.2 * (intento + 1))
            finally:
                db.close()
        _preparadas.add(clave)


@contextmanager
def abrir_sqlite(ruta: Path, esquema: str):
    """Conexión lista para usar (con commit al salir) a una base local compartida entre hilos y procesos."""
    _preparar(ruta, esquema)
    db = sqlite3.connect(ruta, timeout=TIMEOUT_SEGUNDOS)
    try:
        yield db
        db.commit()
    finally:
        db.close()
