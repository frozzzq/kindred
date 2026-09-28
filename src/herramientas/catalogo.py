"""Todas las herramientas del agente, con su grupo y su riesgo.

Grupos: "boveda" (notas de Obsidian), "sistema" (abrir apps, páginas y
carpetas) y "pantalla" (click y escritura en la ventana activa). A cada
mensaje solo se le ofrecen los grupos relevantes (seleccionar_grupos), porque
un modelo local de 8B elige peor entre muchas herramientas.
"""

import re

from src.actions.aplicaciones import abrir_aplicacion
from src.actions.archivos import abrir_carpeta
from src.actions.navegador import abrir_url
from src.actions.system_control import escribir_texto, hacer_click
from src.herramientas.auditoria import registrar_accion
from src.herramientas.registro import Herramienta, Registro, Riesgo
from src.obsidian.herramientas import herramienta_buscar, herramienta_leer_nota, herramienta_listar_notas
from src.obsidian.vault_writer import (
    agregar_pendiente,
    agregar_recurrente,
    completar_pendiente,
    guardar_contacto,
    normalizar,
    recordar_sobre_usuario,
)
from src.router.intent_router import es_click_riesgoso

# Por inicio de palabra: "describe" no pide escribir, "abril" no pide abrir nada.
_PIDE_PANTALLA = re.compile(r"\b(click|clic|presiona|boton|escrib|teclea|pega)")
_PIDE_SISTEMA = re.compile(
    r"\b(abr[ea]|abrir|lanza|inicia|ejecuta|pagina|sitio|web|enlace|link|url|carpeta|pestana|navegador"
    r"|aplicacion|app|programa)|\w\.(com|mx|org|net|io)\b"
)


def seleccionar_grupos(texto: str, modelo_local: bool = False) -> set[str]:
    """Grupos de herramientas para este mensaje.

    La bóveda va siempre y "pantalla" solo si el texto pide click o escritura.
    "sistema" va siempre para Gemini, pero al modelo local solo si el texto pide
    abrir algo: con esas herramientas de más, qwen3:8b dejaba de leer la bóveda
    y contestaba de memoria ("¿qué pendientes tengo?" leyó la nota 0 de 4 veces;
    sin ellas, 4 de 4).
    """
    texto = normalizar(texto)
    grupos = {"boveda"}
    if not modelo_local or _PIDE_SISTEMA.search(texto):
        grupos.add("sistema")
    if _PIDE_PANTALLA.search(texto):
        grupos.add("pantalla")
    return grupos


def _abrir_aplicacion(nombre: str) -> str:
    return abrir_aplicacion(nombre).mensaje


def _abrir_url(url: str) -> str:
    return abrir_url(url).mensaje


def _abrir_carpeta(nombre: str) -> str:
    return abrir_carpeta(nombre).mensaje


def _hacer_click(texto: str) -> str:
    return hacer_click(texto).mensaje


def _escribir_texto(texto: str) -> str:
    return escribir_texto(texto).mensaje


def _riesgo_click(argumentos: dict) -> Riesgo:
    return Riesgo.ALTO if es_click_riesgoso(argumentos.get("texto", "")) else Riesgo.BAJO


HERRAMIENTAS = (
    # --- bóveda ---
    Herramienta(
        "listar_notas",
        "Lista todas las notas que existen en la bóveda del usuario.",
        "boveda",
        herramienta_listar_notas,
    ),
    Herramienta(
        "leer_nota",
        "Lee el contenido completo de una nota. Úsala siempre que necesites saber qué dice una nota.",
        "boveda",
        herramienta_leer_nota,
        {"ruta": "Ruta relativa de la nota, por ejemplo '02-Tareas/Pendientes.md'."},
    ),
    Herramienta(
        "buscar_en_boveda",
        "Busca en todas las notas por palabras clave y devuelve en qué notas aparece. "
        "Después usa leer_nota para ver la nota completa.",
        "boveda",
        herramienta_buscar,
        {"consulta": "Palabras a buscar."},
    ),
    Herramienta(
        "agregar_pendiente",
        "Agrega una tarea a la lista de pendientes. Úsala solo cuando sepas exactamente cuál es la tarea; "
        "si el usuario no la dijo, pregúntale primero.",
        "boveda",
        agregar_pendiente,
        {
            "tarea": "Descripción corta y clara de la tarea, ej. 'Comprar leche'.",
            "cuando": "Fecha y/o hora en que debe hacerse o recordarse, en lenguaje natural, ej. "
            "'mañana a las 6pm', 'el viernes'. Solo si el usuario la mencionó; si no, se omite.",
        },
        opcionales=frozenset({"cuando"}),
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "agregar_recurrente",
        "Agrega una tarea que se repite (diario, o en ciertos días de la semana), ej. \"tomar la "
        "medicina diario a las 9pm\" o \"sacar la basura los lunes y jueves a las 8am\". No la uses "
        "para algo que pasa una sola vez: para eso es agregar_pendiente.",
        "boveda",
        agregar_recurrente,
        {
            "tarea": "Descripción corta de la tarea, ej. 'Tomar medicina'.",
            "frecuencia": "Cuándo se repite, en lenguaje natural: 'diario a las 9pm', 'los lunes y "
            "miércoles a las 8am'. Debe incluir una hora concreta.",
        },
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "completar_pendiente",
        "Marca como hecha una tarea de la lista de pendientes.",
        "boveda",
        completar_pendiente,
        {"descripcion": "Parte del texto de la tarea a completar, ej. 'leche'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "recordar_sobre_usuario",
        "Guarda en el perfil del usuario un dato duradero sobre él (gustos, datos personales, rutinas, "
        "metas). No lo uses para cosas pasajeras.",
        "boveda",
        recordar_sobre_usuario,
        {"dato": "El dato en una oración, ej. 'Le gusta el café sin azúcar'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "guardar_contacto",
        "Guarda una persona que el usuario menciona y lo relevante sobre ella.",
        "boveda",
        guardar_contacto,
        {"nombre": "Nombre de la persona.", "detalle": "Relación con el usuario y datos relevantes."},
        riesgo=Riesgo.BAJO,
    ),
    # --- sistema ---
    Herramienta(
        "abrir_aplicacion",
        "Abre una aplicación instalada en la computadora del usuario, ej. 'Spotify', 'Photoshop', 'Discord'. "
        "Acepta el nombre aunque esté mal escrito.",
        "sistema",
        _abrir_aplicacion,
        {"nombre": "Nombre de la aplicación."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "abrir_url",
        "Abre una página web en una pestaña nueva del navegador, ej. 'youtube.com'.",
        "sistema",
        _abrir_url,
        {"url": "Dirección de la página, ej. 'youtube.com' o 'https://github.com'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "abrir_carpeta",
        "Abre una carpeta del usuario en el Explorador de archivos: 'descargas', 'documentos', "
        "'escritorio', 'imágenes' o el nombre de una carpeta dentro de ellas.",
        "sistema",
        _abrir_carpeta,
        {"nombre": "Nombre de la carpeta."},
        riesgo=Riesgo.BAJO,
    ),
    # --- pantalla ---
    Herramienta(
        "hacer_click",
        "Hace click en un botón, pestaña o casilla de la ventana que el usuario tiene activa, "
        "buscándolo por su texto visible.",
        "pantalla",
        _hacer_click,
        {"texto": "Texto visible del control, ej. 'Guardar'."},
        riesgo=_riesgo_click,
        pregunta=lambda argumentos: f"¿Confirmas que haga click en '{argumentos.get('texto', '')}'?",
    ),
    Herramienta(
        "escribir_texto",
        "Escribe texto donde está el cursor en la ventana activa del usuario.",
        "pantalla",
        _escribir_texto,
        {"texto": "El texto exacto a escribir."},
        riesgo=Riesgo.BAJO,
    ),
)

REGISTRO = Registro(HERRAMIENTAS, auditar=registrar_accion)
