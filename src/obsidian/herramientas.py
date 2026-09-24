"""Herramientas de la bóveda que el agente decide usar por sí mismo (tool calling).

En vez de inyectarle fragmentos pasivos, el modelo pide lo que necesita:
leer una nota completa, buscar, o escribir (pendientes, perfil, contactos).
Cada herramienta devuelve texto para el modelo y nunca lanza excepciones
hacia afuera: un error se le devuelve como texto para que lo explique.
"""

import re
from collections.abc import Callable

from src.obsidian.vault_reader import buscar_en_boveda, leer_nota, listar_rutas_relativas
from src.obsidian.vault_writer import (
    agregar_pendiente,
    completar_pendiente,
    guardar_contacto,
    recordar_sobre_usuario,
)

MAX_CARACTERES_NOTA = 6000


def _definicion(nombre: str, descripcion: str, parametros: dict[str, str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": nombre,
            "description": descripcion,
            "parameters": {
                "type": "object",
                "properties": {p: {"type": "string", "description": d} for p, d in parametros.items()},
                "required": list(parametros),
            },
        },
    }


DEFINICIONES = [
    _definicion("listar_notas", "Lista todas las notas que existen en la bóveda del usuario.", {}),
    _definicion(
        "leer_nota",
        "Lee el contenido completo de una nota. Úsala siempre que necesites saber qué dice una nota.",
        {"ruta": "Ruta relativa de la nota, por ejemplo '02-Tareas/Pendientes.md'."},
    ),
    _definicion(
        "buscar_en_boveda",
        "Busca en todas las notas por palabras clave y devuelve en qué notas aparece. "
        "Después usa leer_nota para ver la nota completa.",
        {"consulta": "Palabras a buscar."},
    ),
    _definicion(
        "agregar_pendiente",
        "Agrega una tarea a la lista de pendientes. Úsala solo cuando sepas exactamente cuál es la tarea; "
        "si el usuario no la dijo, pregúntale primero.",
        {"tarea": "Descripción corta y clara de la tarea, ej. 'Comprar leche'."},
    ),
    _definicion(
        "completar_pendiente",
        "Marca como hecha una tarea de la lista de pendientes.",
        {"descripcion": "Parte del texto de la tarea a completar, ej. 'leche'."},
    ),
    _definicion(
        "recordar_sobre_usuario",
        "Guarda en el perfil del usuario un dato duradero sobre él (gustos, datos personales, rutinas, "
        "metas). No lo uses para cosas pasajeras.",
        {"dato": "El dato en una oración, ej. 'Le gusta el café sin azúcar'."},
    ),
    _definicion(
        "guardar_contacto",
        "Guarda una persona que el usuario menciona y lo relevante sobre ella.",
        {"nombre": "Nombre de la persona.", "detalle": "Relación con el usuario y datos relevantes."},
    ),
]


def _leer_nota(ruta: str) -> str:
    contenido = leer_nota(ruta)
    if contenido is None:
        return f"La nota '{ruta}' no existe. Usa listar_notas para ver las disponibles."
    if not contenido.strip():
        return f"La nota '{ruta}' está vacía."
    if len(contenido) > MAX_CARACTERES_NOTA:
        return contenido[-MAX_CARACTERES_NOTA:] + "\n[nota recortada: se muestran solo las últimas líneas]"
    return contenido


def _listar_notas() -> str:
    return "\n".join(listar_rutas_relativas()) or "La bóveda está vacía."


def _buscar(consulta: str) -> str:
    resultados = buscar_en_boveda(consulta)
    if not resultados:
        return f"No encontré nada sobre '{consulta}' en la bóveda."
    return "\n".join(f"[{r.ruta_relativa}]: {r.fragmento}" for r in resultados)


IMPLEMENTACIONES: dict[str, Callable[..., str]] = {
    "listar_notas": _listar_notas,
    "leer_nota": _leer_nota,
    "buscar_en_boveda": _buscar,
    "agregar_pendiente": agregar_pendiente,
    "completar_pendiente": completar_pendiente,
    "recordar_sobre_usuario": recordar_sobre_usuario,
    "guardar_contacto": guardar_contacto,
}


HERRAMIENTAS_DE_ESCRITURA = {"agregar_pendiente", "completar_pendiente", "recordar_sobre_usuario", "guardar_contacto"}

# "He agregado", "anoté", "marqué como completada", "guardé", "añadí"...
_AFIRMA_CAMBIO = re.compile(
    r"\b(agreg|añad|anot|guard|marc|complet|registr|elimin|borr)(ad[oa]s?|u?é|í)\b", re.IGNORECASE
)

MENSAJE_VERIFICACION = (
    "Verificación del sistema: en este turno no ejecutaste ninguna herramienta de escritura, así que ese "
    "cambio NO se hizo en la bóveda. Si el usuario pidió un cambio, llama ahora la herramienta correcta. "
    "Si no pidió ningún cambio, responde de nuevo sin afirmar que hiciste algo."
)


def afirma_cambio_sin_hacerlo(texto: str, herramientas_usadas: list[str]) -> bool:
    """True si el modelo dice haber cambiado la bóveda sin haber llamado ninguna herramienta de escritura.

    Los modelos pequeños, después de ver en el historial un "He agregado...",
    tienden a repetir la frase sin llamar la herramienta (pasó en pruebas reales).
    """
    return bool(_AFIRMA_CAMBIO.search(texto)) and not HERRAMIENTAS_DE_ESCRITURA.intersection(herramientas_usadas)


def ejecutar_herramienta(nombre: str, argumentos: dict) -> str:
    """Ejecuta una herramienta pedida por el modelo y devuelve su resultado como texto."""
    funcion = IMPLEMENTACIONES.get(nombre)
    if funcion is None:
        return f"La herramienta '{nombre}' no existe."
    try:
        return funcion(**argumentos)
    except (TypeError, ValueError, OSError, RuntimeError) as error:
        return f"Error al usar {nombre}: {error}"
