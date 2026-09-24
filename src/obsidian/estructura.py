"""Crea el esqueleto de carpetas y notas base de la boveda si no existe."""

from src.obsidian.config import ruta_boveda

NOTAS_INICIALES = (
    "00-Sistema/Configuracion.md",
    "00-Sistema/Logs-Interacciones.md",
    "01-Perfil/Yo.md",
    "01-Perfil/Contactos.md",
    "01-Perfil/Patrones.md",
    "02-Tareas/Pendientes.md",
    "02-Tareas/Completadas.md",
    "02-Tareas/Recurrentes.md",
)

CARPETAS_VACIAS = ("03-Proyectos", "04-Conocimiento", "05-Decisiones")


def asegurar_estructura_boveda() -> None:
    """Crea las carpetas y notas base de la bóveda si todavía no existen.

    Nunca sobrescribe una nota que ya tenga contenido.
    """
    boveda = ruta_boveda()

    for ruta_relativa in NOTAS_INICIALES:
        ruta = boveda / ruta_relativa
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text("", encoding="utf-8")

    for carpeta in CARPETAS_VACIAS:
        (boveda / carpeta).mkdir(parents=True, exist_ok=True)
