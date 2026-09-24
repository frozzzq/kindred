"""Escritura de notas en la boveda de Obsidian."""

from datetime import datetime

from src.obsidian.config import ruta_boveda


def escribir_nota(ruta_relativa: str, contenido: str, sobrescribir: bool = False) -> None:
    """Crea o actualiza una nota, creando las carpetas necesarias si faltan.

    Si la nota ya existe y sobrescribir=False, el contenido nuevo se agrega
    al final en vez de reemplazar lo existente.
    """
    ruta = ruta_boveda() / ruta_relativa
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists() and not sobrescribir:
        contenido_previo = ruta.read_text(encoding="utf-8")
        contenido = contenido_previo.rstrip("\n") + "\n" + contenido if contenido_previo else contenido
    ruta.write_text(contenido, encoding="utf-8")


def agregar_pendiente(texto: str) -> None:
    """Agrega una línea a 02-Tareas/Pendientes.md con fecha."""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    escribir_nota("02-Tareas/Pendientes.md", f"- [ ] {texto} ({fecha})")


def registrar_interaccion(texto_usuario: str, respuesta: str, motor: str) -> None:
    """Agrega una entrada al log de interacciones."""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    entrada = f"### {fecha} ({motor})\n**Usuario:** {texto_usuario}\n**Respuesta:** {respuesta}\n"
    escribir_nota("00-Sistema/Logs-Interacciones.md", entrada)
