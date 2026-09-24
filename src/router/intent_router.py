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

PALABRAS_CLAVE_BUSQUEDA_WEB = ("busca", "buscar", "internet", "investiga")

PALABRAS_CLAVE_COMPLEJO = PALABRAS_CLAVE_BUSQUEDA_WEB + (
    "manda", "envía", "envia", "mensaje", "correo", "email",
    "resume", "resumir",
    "analiza", "analizar",
)

PREFIJOS_ABRIR = ("abre ", "abrir ")
ARTICULOS = ("el ", "la ", "los ", "las ")
SIGNOS_A_QUITAR = " .,;:!¡?¿'\""


def decidir_motor(texto: str) -> str:
    """Decide qué motor debe atender el texto, según palabras clave simples.

    Comandos simples (pendientes, notas, contexto ya guardado) → Ollama.
    Comandos complejos (buscar en internet, mensajes, resumir/analizar) → Gemini.
    """
    texto_normalizado = texto.lower()
    if any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_COMPLEJO):
        return MOTOR_GEMINI
    return MOTOR_OLLAMA


def es_busqueda_web(texto: str) -> bool:
    """Indica si el comando pide buscar algo en internet (activa grounding en Gemini)."""
    texto_normalizado = texto.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_BUSQUEDA_WEB)


def extraer_nombre_app(texto: str) -> str | None:
    """Si el texto es un comando de "abrir <app>", devuelve el nombre de la app.

    Devuelve None si el texto no empieza con un prefijo de apertura
    ("abre "/"abrir "), para no interceptar comandos que no son de este tipo.
    Quita signos de puntuación sueltos (Whisper suele agregar puntos o
    signos de exclamación al transcribir).
    """
    texto_normalizado = texto.strip(SIGNOS_A_QUITAR).lower()
    for prefijo in PREFIJOS_ABRIR:
        if texto_normalizado.startswith(prefijo):
            resto = texto_normalizado[len(prefijo):].strip(SIGNOS_A_QUITAR)
            for articulo in ARTICULOS:
                if resto.startswith(articulo):
                    resto = resto[len(articulo):].strip(SIGNOS_A_QUITAR)
            return resto or None
    return None
