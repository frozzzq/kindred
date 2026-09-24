"""Escritura de notas en la boveda de Obsidian."""

import unicodedata
from datetime import datetime

from src.obsidian.config import ruta_boveda

RUTA_PENDIENTES = "02-Tareas/Pendientes.md"
RUTA_COMPLETADAS = "02-Tareas/Completadas.md"
RUTA_PERFIL = "01-Perfil/Yo.md"
RUTA_CONTACTOS = "01-Perfil/Contactos.md"
RUTA_PATRONES = "01-Perfil/Patrones.md"
RUTA_LOG = "00-Sistema/Logs-Interacciones.md"

MARCA_PENDIENTE = "- [ ] "


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar textos sin importar cómo se escribieron."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


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


def agregar_pendiente(tarea: str) -> str:
    """Agrega una tarea a Pendientes.md. La fecha es de cuándo se agregó, no un vencimiento."""
    escribir_nota(RUTA_PENDIENTES, f"{MARCA_PENDIENTE}{tarea.strip()} (agregado {_ahora()})")
    return f"Pendiente agregado: {tarea.strip()}"


def completar_pendiente(descripcion: str) -> str:
    """Mueve de Pendientes.md a Completadas.md la tarea que coincida con la descripción.

    Si no hay coincidencia o hay varias, no toca nada y lo informa, para que
    el agente le pregunte al usuario cuál era.
    """
    ruta = ruta_boveda() / RUTA_PENDIENTES
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    buscado = normalizar(descripcion)
    coincidencias = [
        i for i, linea in enumerate(lineas)
        if linea.startswith(MARCA_PENDIENTE) and buscado in normalizar(linea)
    ]

    if not coincidencias:
        return f"No encontré ningún pendiente que coincida con '{descripcion}'."
    if len(coincidencias) > 1:
        opciones = "; ".join(lineas[i][len(MARCA_PENDIENTE):] for i in coincidencias)
        return f"Hay varios pendientes que coinciden, pregunta cuál: {opciones}"

    linea = lineas.pop(coincidencias[0])
    tarea = linea[len(MARCA_PENDIENTE):]
    escribir_nota(RUTA_PENDIENTES, "\n".join(lineas) + ("\n" if lineas else ""), sobrescribir=True)
    escribir_nota(RUTA_COMPLETADAS, f"- [x] {tarea} (completado {_ahora()})")
    return f"Pendiente completado: {tarea}"


def recordar_sobre_usuario(dato: str) -> str:
    """Anota un dato duradero sobre el usuario en su perfil (Yo.md)."""
    escribir_nota(RUTA_PERFIL, f"- {dato.strip()} ({_ahora()[:10]})")
    return f"Anotado en tu perfil: {dato.strip()}"


def guardar_contacto(nombre: str, detalle: str) -> str:
    """Agrega un contacto (persona y lo que se sabe de ella) a Contactos.md."""
    escribir_nota(RUTA_CONTACTOS, f"- **{nombre.strip()}**: {detalle.strip()} ({_ahora()[:10]})")
    return f"Contacto guardado: {nombre.strip()}"


def anotar_patron(patron: str) -> str:
    """Anota un patrón de comportamiento observado en Patrones.md."""
    escribir_nota(RUTA_PATRONES, f"- {patron.strip()} ({_ahora()[:10]})")
    return f"Patrón anotado: {patron.strip()}"


def registrar_interaccion(texto_usuario: str, respuesta: str, motor: str) -> None:
    """Agrega una entrada al log de interacciones."""
    entrada = f"### {_ahora()} ({motor})\n**Usuario:** {texto_usuario}\n**Respuesta:** {respuesta}\n"
    escribir_nota(RUTA_LOG, entrada)
