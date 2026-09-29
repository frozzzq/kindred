"""Todas las herramientas del agente, con su grupo y su riesgo.

Grupos:
- "boveda": leer, listar y buscar notas; pendientes; perfil y contactos. Va siempre.
- "notas": gestionar notas libres (crear, ampliar, editar, mover, conectar, eliminar).
- "sistema": abrir apps, páginas y carpetas.
- "pantalla": click y escritura en la ventana activa.

A cada mensaje solo se le ofrecen los grupos relevantes (seleccionar_grupos), porque un modelo
local de 8B elige peor entre muchas herramientas. Gemini recibe siempre bóveda, notas y sistema.
"""

import re

from src.actions.aplicaciones import abrir_aplicacion
from src.actions.archivos import abrir_carpeta
from src.actions.navegador import abrir_url
from src.actions.system_control import escribir_texto, hacer_click
from src.herramientas.auditoria import registrar_accion
from src.herramientas.registro import Herramienta, Registro, Riesgo
from src.obsidian.herramientas import herramienta_buscar, herramienta_leer_nota, herramienta_listar_notas
from src.obsidian.notas import (
    agregar_a_nota,
    conectar_notas,
    crear_nota,
    desconectar_notas,
    editar_nota,
    eliminar_nota,
    mover_nota,
    pregunta_eliminar,
    sugerir_conexiones,
)
from src.obsidian.texto import normalizar
from src.obsidian.vault_writer import (
    agregar_pendiente,
    agregar_recurrente,
    completar_pendiente,
    guardar_contacto,
    recordar_sobre_usuario,
    reprogramar_pendiente,
)
from src.router.intent_router import es_click_riesgoso

# Por inicio de palabra: "describe" no pide escribir, "abril" no pide abrir nada.
_PIDE_PANTALLA = re.compile(r"\b(click|clic|presiona|boton|escrib|teclea|pega)")
_PIDE_SISTEMA = re.compile(
    r"\b(abr[ea]|abrir|lanza|inicia|ejecuta|pagina|sitio|web|enlace|link|url|carpeta|pestana|navegador"
    r"|aplicacion|app|programa)|\w\.(com|mx|org|net|io)\b"
)
_PIDE_NOTAS = re.compile(
    r"\b(nota|notas|apunte|apuntes|documenta|conect|enlaz|vincul|relacion|desconect|muev|mover|move|renombr"
    r"|borr|elimin|edit|actualiz|agregale|anadele|agrega a|anade a|organiz|ordena|boveda|obsidian|archiv"
    r"|crea|creame|guarda esto|guarda eso|guardalo|resum|carpeta)"
)


def seleccionar_grupos(texto: str, modelo_local: bool = False) -> set[str]:
    """Grupos de herramientas para este mensaje.

    La bóveda va siempre y "pantalla" solo si el texto pide click o escritura. "sistema" y "notas"
    van siempre para Gemini, pero al modelo local solo si el texto los pide: con herramientas de
    más, qwen3:8b dejaba de leer la bóveda y contestaba de memoria ("¿qué pendientes tengo?" leyó
    la nota 0 de 4 veces; sin ellas, 4 de 4).
    """
    texto = normalizar(texto)
    grupos = {"boveda"}
    if not modelo_local or _PIDE_SISTEMA.search(texto):
        grupos.add("sistema")
    if not modelo_local or _PIDE_NOTAS.search(texto):
        grupos.add("notas")
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


# Descripciones cortas a propósito: van en cada mensaje al modelo, y en la RX 7600 cada 1000 tokens
# de contexto bajan la generación ~3 tokens/s (medido).
_NOTA = "Nombre o ruta de la nota, ej. 'Node.js'."

HERRAMIENTAS = (
    # --- bóveda: consultar ---
    Herramienta(
        "listar_notas",
        "Lista las notas por carpeta.",
        "boveda",
        herramienta_listar_notas,
        {"carpeta": "Opcional, ej. '04-Conocimiento'."},
        opcionales=frozenset({"carpeta"}),
    ),
    Herramienta("leer_nota", "Lee una nota completa.", "boveda", herramienta_leer_nota, {"ruta": _NOTA}),
    Herramienta(
        "buscar_en_boveda",
        "Busca en sus notas por tema o palabras (entiende sinónimos).",
        "boveda",
        herramienta_buscar,
        {"consulta": "Qué buscar."},
    ),
    # --- bóveda: pendientes ---
    Herramienta(
        "agregar_pendiente",
        "Agrega una tarea a sus pendientes. Si no dijo cuál, pregúntale antes.",
        "boveda",
        agregar_pendiente,
        {
            "tarea": "La tarea, corta, ej. 'Comprar leche'.",
            "cuando": "Fecha/hora en lenguaje natural, solo si la dijo, ej. 'mañana a las 6pm'.",
        },
        opcionales=frozenset({"cuando"}),
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "completar_pendiente",
        "Marca como hecha una tarea de sus pendientes.",
        "boveda",
        completar_pendiente,
        {"descripcion": "Parte del texto de la tarea, ej. 'leche'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "reprogramar_pendiente",
        "Cambia la fecha/hora de un pendiente que ya existe: \"pásame lo del reporte para mañana a las 5pm\", "
        "\"muévelo al lunes\", \"posponlo\".",
        "boveda",
        reprogramar_pendiente,
        {"descripcion": "Parte del texto del pendiente.", "cuando": "Nueva fecha/hora, ej. 'el lunes a las 9am'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "agregar_recurrente",
        "Agrega una tarea que se repite (diario o ciertos días), siempre con hora.",
        "boveda",
        agregar_recurrente,
        {"tarea": "La tarea, ej. 'Tomar medicina'.", "frecuencia": "Ej. 'diario a las 9pm', 'lunes y jueves a las 8am'."},
        riesgo=Riesgo.BAJO,
    ),
    # --- bóveda: perfil ---
    Herramienta(
        "recordar_sobre_usuario",
        "Guarda en su perfil un dato duradero del usuario (gustos, datos, rutinas, metas).",
        "boveda",
        recordar_sobre_usuario,
        {"dato": "Una oración, ej. 'Le gusta el café sin azúcar'."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "guardar_contacto",
        "Guarda a una persona importante para el usuario, o le suma un dato.",
        "boveda",
        guardar_contacto,
        {"nombre": "Nombre de la persona.", "detalle": "Relación y datos."},
        riesgo=Riesgo.BAJO,
    ),
    # --- notas libres ---
    Herramienta(
        "crear_nota",
        "Crea una nota nueva (idea, tema de estudio, proyecto, decisión); no para pendientes, perfil ni "
        "contactos. Se acomoda en su carpeta y se conecta sola con su tema.",
        "notas",
        crear_nota,
        {
            "ruta": "Título, con carpeta si la sabes: 'Node.js' o '04-Conocimiento/Programación/Node.js'.",
            "contenido": "El contenido, en Markdown.",
            "etiquetas": "Opcional, separadas por coma.",
        },
        opcionales=frozenset({"etiquetas"}),
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "agregar_a_nota",
        "Agrega texto al final de una nota que ya existe.",
        "notas",
        agregar_a_nota,
        {"ruta": _NOTA, "texto": "Lo que se agrega, en Markdown."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "editar_nota",
        "Reescribe una nota existente (léela antes); conserva sus enlaces y respalda la versión anterior.",
        "notas",
        editar_nota,
        {"ruta": _NOTA, "contenido": "El contenido completo nuevo."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "mover_nota",
        "Mueve o renombra una nota y actualiza los enlaces a ella.",
        "notas",
        mover_nota,
        {"ruta": _NOTA, "destino": "Carpeta, nombre nuevo o ruta completa."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "conectar_notas",
        "Enlaza dos notas relacionadas; di el motivo.",
        "notas",
        conectar_notas,
        {"origen": _NOTA, "destino": "La otra nota.", "motivo": "Opcional: por qué se relacionan."},
        opcionales=frozenset({"motivo"}),
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "desconectar_notas",
        "Quita el enlace de una nota a otra.",
        "notas",
        desconectar_notas,
        {"origen": _NOTA, "destino": "La otra nota."},
        riesgo=Riesgo.BAJO,
    ),
    Herramienta(
        "sugerir_conexiones",
        "Dice con qué notas se relaciona una nota y por qué.",
        "notas",
        sugerir_conexiones,
        {"ruta": _NOTA},
    ),
    Herramienta(
        "eliminar_nota",
        "Manda una nota a la papelera de Windows (recuperable).",
        "notas",
        eliminar_nota,
        {"ruta": "Nombre o ruta exacta de la nota."},
        riesgo=Riesgo.ALTO,
        pregunta=pregunta_eliminar,
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
