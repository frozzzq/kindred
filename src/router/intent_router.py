"""Router de intención: decide qué motor (o acción directa) debe atender
un comando de texto.

Fase 1: decisión simple por palabras clave, sin IA todavía. Aislado en su
propio módulo para poder ajustarlo (o reemplazarlo por algo más inteligente)
sin tocar el resto del sistema.

Fase 4: "abrir aplicación" ya no pasa por Gemini — se detecta y ejecuta
directamente (un LLM de texto no puede abrir una app de verdad), y la
búsqueda web se marca aparte para activar el grounding de Gemini.
"""

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

PREFIJOS_ABRIR = ("abre ", "abrir ")
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
    "click en ", "clic en ",
    "presiona el botón ", "presiona el boton ",
    "toca el botón ", "toca el boton ",
)
PREFIJOS_ESCRIBIR = ("escribe ", "teclea ")

# Botones cuyo texto sugiere una acción irreversible: pedir confirmación antes de hacerles click.
PALABRAS_CLAVE_RIESGO_CLICK = (
    "eliminar", "borrar", "enviar", "comprar", "pagar",
    "confirmar compra", "cancelar suscripción", "cancelar suscripcion",
    "desinstalar", "vaciar papelera", "restablecer", "formatear",
)


def decidir_motor(texto: str) -> str:
    """Decide qué motor debe atender el texto, según palabras clave simples.

    Comandos simples (pendientes, notas, contexto ya guardado) → Ollama.
    Comandos complejos (buscar en internet, mensajes, resumir/analizar) → Gemini.
    """
    texto_normalizado = texto.lower()
    if any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_COMPLEJO):
        return MOTOR_GEMINI
    return MOTOR_OLLAMA


def nombre_motor(motor: str) -> str:
    """Nombre de personalidad para mostrar/decir, según qué motor respondió."""
    return NOMBRES_MOTOR.get(motor, "Jarvis")


def es_busqueda_web(texto: str) -> bool:
    """Indica si el comando pide buscar algo en internet (activa grounding en Gemini)."""
    texto_normalizado = texto.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_BUSQUEDA_WEB)


def es_cierre(texto: str) -> bool:
    """Indica si el comando pide cerrar la aplicación."""
    texto_normalizado = texto.lower().strip(SIGNOS_A_QUITAR)
    return any(frase in texto_normalizado for frase in FRASES_CIERRE)


def extraer_texto_click(texto: str) -> str | None:
    """Si el texto pide hacer click en algo, devuelve el texto del control a buscar (o None)."""
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR).lower()
    for prefijo in PREFIJOS_CLICK:
        indice = texto_normalizado.find(prefijo)
        if indice == -1:
            continue
        resto = texto_normalizado[indice + len(prefijo):].strip(SIGNOS_A_QUITAR)
        return resto or None
    return None


def extraer_texto_a_escribir(texto: str) -> str | None:
    """Si el texto pide escribir/teclear algo, devuelve lo que hay que escribir (o None).

    Conserva mayúsculas/minúsculas originales (a diferencia de extraer_texto_click):
    lo que se va a teclear debe verse como se dictó, no forzado a minúsculas.
    """
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR)
    en_minusculas = texto_normalizado.lower()
    for prefijo in PREFIJOS_ESCRIBIR:
        indice = en_minusculas.find(prefijo)
        if indice == -1:
            continue
        resto = texto_normalizado[indice + len(prefijo):].strip(SIGNOS_A_QUITAR)
        return resto or None
    return None


def es_click_riesgoso(texto_boton: str) -> bool:
    """Indica si el texto del control sugiere una acción irreversible (eliminar, enviar, comprar...)."""
    texto_normalizado = texto_boton.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_RIESGO_CLICK)


def extraer_nombre_app(texto: str) -> str | None:
    """Si el texto contiene un comando de "abrir <app>", devuelve el nombre de la app.

    Busca "abre "/"abrir " en cualquier parte del texto (no solo al inicio),
    para reconocerlo aunque venga precedido de un saludo o el nombre del
    motor (ej. "Hey Crimson, abre calculadora"). Devuelve None si no
    aparece. Quita signos de puntuación sueltos (Whisper suele agregar
    puntos o signos de exclamación al transcribir).
    """
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR).lower()
    for prefijo in PREFIJOS_ABRIR:
        indice = texto_normalizado.find(prefijo)
        if indice == -1:
            continue
        resto = texto_normalizado[indice + len(prefijo):].strip(SIGNOS_A_QUITAR)
        for articulo in ARTICULOS:
            if resto.startswith(articulo):
                resto = resto[len(articulo):].strip(SIGNOS_A_QUITAR)
        return resto or None
    return None
