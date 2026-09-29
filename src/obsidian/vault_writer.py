"""Escritura de las notas operativas de la bóveda: pendientes, recurrentes, perfil, contactos y log.

Las notas libres (crear, editar, conectar, mover, eliminar) están en src/obsidian/notas.py.
"""

import re
from datetime import datetime

import numpy as np

from src.engines import embeddings
from src.obsidian.config import ruta_boveda
from src.obsidian.estructura import CARPETA_LOGS
from src.obsidian.fechas import formatear_tags, parsear_fecha_hora
from src.obsidian.formato import insertar_antes_de_relacionado
from src.obsidian.texto import normalizar
from src.obsidian.vault_reader import resolver_ruta

RUTA_PENDIENTES = "02-Tareas/Pendientes.md"
RUTA_COMPLETADAS = "02-Tareas/Completadas.md"
RUTA_RECURRENTES = "02-Tareas/Recurrentes.md"
RUTA_PERFIL = "01-Perfil/Yo.md"
RUTA_CONTACTOS = "01-Perfil/Contactos.md"
RUTA_PATRONES = "01-Perfil/Patrones.md"

MARCA_PENDIENTE = "- [ ] "
MARCA_RECURRENTE = "- "


def ruta_log(momento: datetime | None = None) -> str:
    """Log de interacciones del mes: uno por mes, para que no crezca sin fin (00-Sistema/Logs/AAAA-MM.md)."""
    return f"{CARPETA_LOGS}/{(momento or datetime.now()):%Y-%m}.md"


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


_PALABRAS_VACIAS = {
    "que", "los", "las", "del", "por", "con", "sin", "una", "uno", "para", "como", "mas", "muy",
    "sus", "son", "ser", "esta", "este", "tiene", "usuario",
}
# Formas distintas de decir lo mismo que el modelo alterna ("se llama" / "su nombre es").
_SINONIMOS = {"llama": "nombre", "llamo": "nombre", "encanta": "gusta", "encantan": "gusta", "gustan": "gusta"}
UMBRAL_DUPLICADO = 0.75
# Dos oraciones cortas que dicen lo mismo con otras palabras ("Suele interactuar con su lista de
# pendientes" / "Frecuentemente interactúa con su lista de pendientes") dan > 0.85 de similitud.
UMBRAL_DUPLICADO_SEMANTICO = 0.85


def _palabras_clave(texto: str) -> set[str]:
    palabras = re.findall(r"[a-z]+", normalizar(texto))
    return {_SINONIMOS.get(p, p) for p in palabras if len(p) >= 3 and p not in _PALABRAS_VACIAS}


def _lineas_con_texto(contenido: str) -> list[str]:
    return [linea.strip("- ").strip() for linea in contenido.splitlines() if linea.strip() and not linea.startswith("#")]


def ya_esta_anotado(dato: str, contenido: str, semantico: bool = False) -> bool:
    """True si alguna línea de la nota ya dice lo mismo que `dato`, aunque sea con otras palabras.

    Primero por palabras clave (instantáneo); con semantico=True, también por significado con
    embeddings. Pasó en pruebas reales: "mi nombre es Josue" y "Su nombre es Josue" quedaban como
    dos líneas, y Patrones.md acumuló cinco versiones de "interactúa con sus pendientes". No se usa
    en pendientes: "Comprar leche" y "Comprar pan" se parecen mucho en significado y son distintos.
    """
    clave = _palabras_clave(dato)
    if not clave:
        return True
    lineas = _lineas_con_texto(contenido)
    if any(len(clave & _palabras_clave(linea)) / len(clave) >= UMBRAL_DUPLICADO for linea in lineas):
        return True
    if not semantico or not lineas:
        return False
    vectores = embeddings.embeber([dato, *lineas])
    if vectores is None or len(vectores) < 2:
        return False
    return bool(np.max(vectores[1:] @ vectores[0]) >= UMBRAL_DUPLICADO_SEMANTICO)


def escribir_nota(ruta_relativa: str, contenido: str, sobrescribir: bool = False) -> None:
    """Crea o actualiza una nota, creando las carpetas necesarias si faltan.

    Si la nota ya existe y sobrescribir=False, el contenido nuevo se agrega al final en vez de
    reemplazar lo existente. Rechaza rutas fuera de la bóveda (pueden venir del modelo).
    """
    ruta = resolver_ruta(ruta_relativa)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists() and not sobrescribir:
        contenido_previo = ruta.read_text(encoding="utf-8")
        contenido = contenido_previo.rstrip("\n") + "\n" + contenido if contenido_previo.strip() else contenido
    ruta.write_text(contenido, encoding="utf-8")


def _leer(ruta_relativa: str) -> str:
    ruta = ruta_boveda() / ruta_relativa
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


def _agregar_linea(ruta_relativa: str, linea: str) -> None:
    """Agrega una línea al final de la nota, pero antes de su sección Relacionado si la tiene."""
    escribir_nota(ruta_relativa, insertar_antes_de_relacionado(_leer(ruta_relativa), linea, separar=False), sobrescribir=True)


# ---------- pendientes ----------


def agregar_pendiente(tarea: str, cuando: str | None = None) -> str:
    """Agrega una tarea a Pendientes.md, si no estaba ya (aunque esté redactada distinto).

    `cuando` es la fecha/hora en lenguaje natural ("mañana a las 6pm", "el viernes"); si no se
    entiende ninguna fecha ahí, el pendiente se agrega igual, sin fecha.
    El "(agregado ...)" del final es de cuándo se agregó, no un vencimiento.
    """
    tarea = tarea.strip()
    if ya_esta_anotado(tarea, _leer(RUTA_PENDIENTES)):
        return f"Ya tenías ese pendiente: {tarea}"

    etiqueta, aviso = "", ""
    if cuando:
        fecha, hora = parsear_fecha_hora(cuando)
        if fecha:
            etiqueta = " " + formatear_tags(fecha, hora)
            aviso = f" para el {fecha.isoformat()}" + (f" a las {hora.strftime('%H:%M')}" if hora else "")
    _agregar_linea(RUTA_PENDIENTES, f"{MARCA_PENDIENTE}{tarea}{etiqueta} (agregado {_ahora()})")
    return f"Pendiente agregado: {tarea}{aviso}"


def _buscar_pendiente(descripcion: str) -> tuple[list[str], list[int]]:
    ruta = ruta_boveda() / RUTA_PENDIENTES
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    buscado = normalizar(descripcion)
    coincidencias = [
        i for i, linea in enumerate(lineas) if linea.startswith(MARCA_PENDIENTE) and buscado in normalizar(linea)
    ]
    return lineas, coincidencias


def completar_pendiente(descripcion: str) -> str:
    """Mueve de Pendientes.md a Completadas.md la tarea que coincida con la descripción.

    Si no hay coincidencia o hay varias, no toca nada y lo informa, para que
    el agente le pregunte al usuario cuál era.
    """
    lineas, coincidencias = _buscar_pendiente(descripcion)
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


_TAGS_FECHA = re.compile(r"\s*(📅\s*\d{4}-\d{2}-\d{2}|⏰\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})")


def reprogramar_pendiente(descripcion: str, cuando: str) -> str:
    """Cambia la fecha/hora de un pendiente existente ("pásalo al lunes a las 9am")."""
    lineas, coincidencias = _buscar_pendiente(descripcion)
    if not coincidencias:
        return f"No encontré ningún pendiente que coincida con '{descripcion}'."
    if len(coincidencias) > 1:
        opciones = "; ".join(lineas[i][len(MARCA_PENDIENTE):] for i in coincidencias)
        return f"Hay varios pendientes que coinciden, pregunta cuál: {opciones}"
    fecha, hora = parsear_fecha_hora(cuando)
    if fecha is None:
        return f"No entendí para cuándo lo paso: '{cuando}'. Dime un día (y si quieres una hora con am o pm)."

    indice = coincidencias[0]
    sin_fecha = _TAGS_FECHA.sub("", lineas[indice])
    agregado = re.search(r"\s*\(agregado [^)]*\)\s*$", sin_fecha)
    base = sin_fecha[: agregado.start()] if agregado else sin_fecha
    sufijo = agregado.group(0) if agregado else ""
    lineas[indice] = f"{base.rstrip()} {formatear_tags(fecha, hora)}{sufijo}"
    escribir_nota(RUTA_PENDIENTES, "\n".join(lineas) + "\n", sobrescribir=True)
    tarea = base[len(MARCA_PENDIENTE):].strip()
    return f"Pendiente reprogramado: {tarea} para el {fecha.isoformat()}" + (
        f" a las {hora.strftime('%H:%M')}" if hora else ""
    )


def agregar_recurrente(tarea: str, frecuencia: str) -> str:
    """Agrega una tarea recurrente a Recurrentes.md ("tomar medicina, diario a las 9pm").

    Si no se entiende cuándo debe repetirse (falta la hora, o no dice ni "diario" ni un día de la
    semana), no la agrega y lo dice, para poder pedírsela de nuevo con más detalle.
    """
    from src.obsidian.recurrentes import formatear_linea, parsear_frecuencia

    tarea = tarea.strip()
    recurrencia = parsear_frecuencia(frecuencia)
    if recurrencia is None:
        return (
            f"No entendí cuándo se repite \"{tarea}\". Dime un día de la semana o \"diario\", y a "
            'qué hora, por ejemplo "diario a las 9pm" o "los lunes a las 8am".'
        )
    if ya_esta_anotado(tarea, _leer(RUTA_RECURRENTES)):
        return f"Ya tenías esa tarea recurrente: {tarea}"
    _agregar_linea(RUTA_RECURRENTES, f"{MARCA_RECURRENTE}{formatear_linea(tarea, recurrencia)} (agregado {_ahora()})")
    return f"Tarea recurrente agregada: {tarea}"


# ---------- perfil ----------


def recordar_sobre_usuario(dato: str) -> str:
    """Anota un dato duradero sobre el usuario en su perfil (Yo.md), si no estaba ya."""
    if ya_esta_anotado(dato, _leer(RUTA_PERFIL), semantico=True):
        return f"Ya estaba anotado en tu perfil: {dato.strip()}"
    _agregar_linea(RUTA_PERFIL, f"- {dato.strip()} ({_ahora()[:10]})")
    return f"Anotado en tu perfil: {dato.strip()}"


def guardar_contacto(nombre: str, detalle: str) -> str:
    """Agrega un contacto (persona y lo que se sabe de ella) a Contactos.md, o le suma el detalle si ya estaba."""
    nombre, detalle = nombre.strip(), detalle.strip()
    contenido = _leer(RUTA_CONTACTOS)
    lineas = contenido.splitlines()
    marca = f"- **{normalizar(nombre)}**"
    for i, linea in enumerate(lineas):
        if normalizar(linea).startswith(marca):
            if ya_esta_anotado(detalle, linea, semantico=True):
                return f"Ya tenía eso de {nombre}."
            lineas[i] = f"{linea.rstrip()}; {detalle}"
            escribir_nota(RUTA_CONTACTOS, "\n".join(lineas) + "\n", sobrescribir=True)
            return f"Contacto actualizado: {nombre}"
    _agregar_linea(RUTA_CONTACTOS, f"- **{nombre}**: {detalle} ({_ahora()[:10]})")
    return f"Contacto guardado: {nombre}"


def anotar_patron(patron: str) -> str:
    """Anota un patrón de comportamiento observado en Patrones.md, si no estaba ya."""
    if ya_esta_anotado(patron, _leer(RUTA_PATRONES), semantico=True):
        return f"Ya estaba anotado el patrón: {patron.strip()}"
    _agregar_linea(RUTA_PATRONES, f"- {patron.strip()} ({_ahora()[:10]})")
    return f"Patrón anotado: {patron.strip()}"


def registrar_interaccion(texto_usuario: str, respuesta: str, motor: str) -> None:
    """Agrega una entrada al log de interacciones del mes."""
    entrada = f"### {_ahora()} ({motor})\n**Usuario:** {texto_usuario}\n**Respuesta:** {respuesta}\n"
    escribir_nota(ruta_log(), entrada)
