"""Router de intención: decide qué motor (o acción directa) debe atender
un comando de texto.

Fase 1: decisión simple por palabras clave, sin IA todavía. Aislado en su
propio módulo para poder ajustarlo (o reemplazarlo por algo más inteligente)
sin tocar el resto del sistema.

Fase 4: "abrir aplicación" ya no pasa por Gemini — se detecta y ejecuta
directamente (un LLM de texto no puede abrir una app de verdad), y la
búsqueda web se marca aparte para activar el grounding de Gemini.
"""

import re

MOTOR_OLLAMA = "ollama"
MOTOR_GEMINI = "gemini"
MOTOR_ACCION = "accion"
MOTOR_GEMINI_FALLO = "gemini_fallo"  # se registra cuando Gemini fue intentado pero falló (Fase 5: métricas)

# Nombres de personalidad solo para mostrar/decir (cosmético). Los
# identificadores internos (ollama/gemini/accion) no cambian, para no
# romper logs, variables de entorno ni tests existentes.
NOMBRES_MOTOR = {
    MOTOR_OLLAMA: "Crimson",
    MOTOR_GEMINI: "Clover",
    MOTOR_ACCION: "Jarvis",
}

PALABRAS_CLAVE_BUSQUEDA_WEB = ("busca", "buscar", "internet", "investiga")

PALABRAS_CLAVE_COMPLEJO = PALABRAS_CLAVE_BUSQUEDA_WEB + (
    "manda", "envía", "envia", "mensaje", "correo", "email",
    "resume", "resumir",
    "analiza", "analizar",
)

PREFIJOS_ABRIR = ("abre ", "abrir ", "ábreme ", "abreme ")
ARTICULOS = ("el ", "la ", "los ", "las ")
SIGNOS_A_QUITAR = " .,;:!¡?¿'\""

FRASES_CIERRE = (
    "ciérrate", "cierrate",
    "cierra la aplicación", "cierra la aplicacion",
    "cierra la app", "cierra el programa",
    "apágate", "apagate",
)

PREFIJOS_CLICK = (
    "haz click en ", "haz clic en ",
    "dale click a ", "dale clic a ",
    "dame click en ", "dame clic en ",
    "click en ", "clic en ",
    "presiona el botón ", "presiona el boton ",
    "toca el botón ", "toca el boton ",
)
PREFIJOS_ESCRIBIR = ("escribe ", "teclea ")

FRASES_SALIR_MODO_SEGURO = (
    "sal del modo seguro", "salir del modo seguro", "sal de modo seguro",
    "desactiva el modo seguro", "quita el modo seguro", "apaga el modo seguro",
)

# Botones cuyo texto sugiere una acción irreversible: pedir confirmación antes de hacerles click.
PALABRAS_CLAVE_RIESGO_CLICK = (
    "eliminar", "borrar", "enviar", "comprar", "pagar",
    "confirmar compra", "cancelar suscripción", "cancelar suscripcion",
    "desinstalar", "vaciar papelera", "restablecer", "formatear",
)


def _contiene_alguna(texto_normalizado: str, palabras: tuple[str, ...]) -> bool:
    """Busca cada palabra como palabra completa, nunca como parte de otra.

    Antes usaba "in" a secas: "enviar" contenía "envia" y disparaba Gemini
    sin que el usuario pidiera enviar nada (visto en pruebas reales).
    """
    return any(re.search(r"\b" + re.escape(palabra) + r"\b", texto_normalizado) for palabra in palabras)


def _primer_prefijo(texto_normalizado: str, prefijos: tuple[str, ...]) -> re.Match | None:
    """El primer prefijo de la lista (en orden de prioridad) que aparece como palabra completa.

    Antes usaba str.find, que encontraba el prefijo aunque fuera parte de
    otra palabra: "describe" contiene "escribe" y activaba el atajo de
    escritura (visto en pruebas reales). \\b exige que justo antes empiece
    una palabra nueva.
    """
    for prefijo in prefijos:
        coincidencia = re.search(r"\b" + re.escape(prefijo), texto_normalizado)
        if coincidencia:
            return coincidencia
    return None


def decidir_motor(texto: str) -> str:
    """Decide qué motor debe atender el texto, según palabras clave simples.

    Comandos simples (pendientes, notas, contexto ya guardado) → Ollama.
    Comandos complejos (buscar en internet, mensajes, resumir/analizar) → Gemini.
    """
    if _contiene_alguna(texto.lower(), PALABRAS_CLAVE_COMPLEJO):
        return MOTOR_GEMINI
    return MOTOR_OLLAMA


def nombre_motor(motor: str) -> str:
    """Nombre de personalidad para mostrar/decir, según qué motor respondió."""
    return NOMBRES_MOTOR.get(motor, "Jarvis")


def es_busqueda_web(texto: str) -> bool:
    """Indica si el comando pide buscar algo en internet (activa grounding en Gemini)."""
    return _contiene_alguna(texto.lower(), PALABRAS_CLAVE_BUSQUEDA_WEB)


def es_cierre(texto: str) -> bool:
    """Indica si el comando pide cerrar la aplicación."""
    texto_normalizado = texto.lower().strip(SIGNOS_A_QUITAR)
    return any(frase in texto_normalizado for frase in FRASES_CIERRE)


_VARIAS_INSTRUCCIONES = re.compile(r",|\s(y|e|luego|después|despues|para|con)\s", re.IGNORECASE)


def parece_varias_instrucciones(texto: str) -> bool:
    """Ej. "spotify y pon mi playlist" son dos cosas: mejor que lo resuelva el agente con herramientas."""
    return bool(_VARIAS_INSTRUCCIONES.search(texto))


def cambio_de_modo_seguro(texto: str) -> bool | None:
    """True si pide activar el modo seguro, False si pide salir de él, None si no habla de eso.

    Ante la duda (ej. "¿estás en modo seguro?") se activa: equivocarse hacia
    lo más restrictivo es inofensivo.
    """
    texto_normalizado = texto.lower()
    if any(frase in texto_normalizado for frase in FRASES_SALIR_MODO_SEGURO):
        return False
    if "modo seguro" in texto_normalizado:
        return True
    return None


def extraer_texto_click(texto: str) -> str | None:
    """Si el texto pide hacer click en algo, devuelve el texto del control a buscar (o None)."""
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR).lower()
    coincidencia = _primer_prefijo(texto_normalizado, PREFIJOS_CLICK)
    if coincidencia is None:
        return None
    resto = texto_normalizado[coincidencia.end():].strip(SIGNOS_A_QUITAR)
    return resto or None


def extraer_texto_a_escribir(texto: str) -> str | None:
    """Si el texto pide escribir/teclear algo, devuelve lo que hay que escribir (o None).

    Conserva mayúsculas/minúsculas originales (a diferencia de extraer_texto_click):
    lo que se va a teclear debe verse como se dictó, no forzado a minúsculas.
    """
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR)
    en_minusculas = texto_normalizado.lower()
    coincidencia = _primer_prefijo(en_minusculas, PREFIJOS_ESCRIBIR)
    if coincidencia is None:
        return None
    # .lower() no cambia la longitud, así que el índice encontrado en minúsculas
    # sirve igual para recortar el texto original (con sus mayúsculas intactas).
    resto = texto_normalizado[coincidencia.end():].strip(SIGNOS_A_QUITAR)
    return resto or None


def es_click_riesgoso(texto_boton: str) -> bool:
    """Indica si el texto del control sugiere una acción irreversible (eliminar, enviar, comprar...)."""
    return _contiene_alguna(texto_boton.lower(), PALABRAS_CLAVE_RIESGO_CLICK)


def extraer_nombre_app(texto: str) -> str | None:
    """Si el texto contiene un comando de "abrir <app>", devuelve el nombre de la app.

    Busca "abre "/"abrir " en cualquier parte del texto (no solo al inicio),
    para reconocerlo aunque venga precedido de un saludo o el nombre del
    motor (ej. "Hey Crimson, abre calculadora"). Devuelve None si no
    aparece. Quita signos de puntuación sueltos (Whisper suele agregar
    puntos o signos de exclamación al transcribir).
    """
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR).lower()
    coincidencia = _primer_prefijo(texto_normalizado, PREFIJOS_ABRIR)
    if coincidencia is None:
        return None
    resto = texto_normalizado[coincidencia.end():].strip(SIGNOS_A_QUITAR)
    for articulo in ARTICULOS:
        if resto.startswith(articulo):
            resto = resto[len(articulo):].strip(SIGNOS_A_QUITAR)
    return resto or None
