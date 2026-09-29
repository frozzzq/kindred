"""Estado técnico: qué se avisó, cursores internos y métricas de uso. Nada de esto va en la bóveda.

Vive en un SQLite local (%LOCALAPPDATA%\\kindred\\estado.db) que comparten los procesos del núcleo
y de la UI/voz; por eso usa WAL y un timeout generoso.
"""

from contextlib import contextmanager
from pathlib import Path

from src.local import abrir_sqlite, carpeta_local

# Aquí (y no en servicio.py) para que la UI pueda saber si el núcleo está vivo sin importar
# servicio → avisos → win11toast: winrt y onnxruntime (voz) en el mismo proceso truenan con un
# access violation nativo (visto al abrir la UI nueva: salía con código 139).
CLAVE_ULTIMA_VUELTA = "nucleo.ultima_vuelta"
INTERVALO_SEGUNDOS = 30

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS avisados (clave TEXT PRIMARY KEY, avisado_en TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS briefings (tipo TEXT PRIMARY KEY, fecha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS valores (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS turnos (
    momento TEXT NOT NULL, agente TEXT NOT NULL, canal TEXT NOT NULL, milisegundos INTEGER NOT NULL,
    herramientas TEXT NOT NULL, llamadas_modelo INTEGER NOT NULL, exito INTEGER NOT NULL
);
"""


def ruta_estado() -> Path:
    return carpeta_local() / "estado.db"


@contextmanager
def abrir():
    with abrir_sqlite(ruta_estado(), _ESQUEMA) as db:
        yield db


def leer_valor(clave: str) -> str | None:
    with abrir() as db:
        fila = db.execute("SELECT valor FROM valores WHERE clave = ?", (clave,)).fetchone()
        return fila[0] if fila else None


def guardar_valor(clave: str, valor: str) -> None:
    with abrir() as db:
        db.execute("INSERT OR REPLACE INTO valores (clave, valor) VALUES (?, ?)", (clave, valor))


def ya_avisado(clave: str) -> bool:
    with abrir() as db:
        return db.execute("SELECT 1 FROM avisados WHERE clave = ?", (clave,)).fetchone() is not None


def marcar_avisado(clave: str, ahora_iso: str) -> None:
    with abrir() as db:
        db.execute("INSERT OR REPLACE INTO avisados (clave, avisado_en) VALUES (?, ?)", (clave, ahora_iso))


def briefing_de_hoy(tipo: str) -> str | None:
    """Fecha (ISO, solo el día) del último briefing de este tipo ("matutino"/"cierre"), o None."""
    with abrir() as db:
        fila = db.execute("SELECT fecha FROM briefings WHERE tipo = ?", (tipo,)).fetchone()
        return fila[0] if fila else None


def marcar_briefing(tipo: str, fecha_iso: str) -> None:
    with abrir() as db:
        db.execute("INSERT OR REPLACE INTO briefings (tipo, fecha) VALUES (?, ?)", (tipo, fecha_iso))
