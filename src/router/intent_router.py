"""Router de intención: decide qué motor debe atender un comando de texto.

Fase 1: decisión simple por palabras clave, sin IA todavía. Aislado en su
propio módulo para poder ajustarlo (o reemplazarlo por algo más inteligente)
sin tocar el resto del sistema.
"""

MOTOR_OLLAMA = "ollama"
MOTOR_GEMINI = "gemini"

PALABRAS_CLAVE_COMPLEJO = (
    "busca", "buscar", "internet", "investiga",
    "abre", "abrir",
    "manda", "envía", "envia", "mensaje", "correo", "email",
    "resume", "resumir",
    "analiza", "analizar",
)


def decidir_motor(texto: str) -> str:
    """Decide qué motor debe atender el texto, según palabras clave simples.

    Comandos simples (pendientes, notas, contexto ya guardado) → Ollama.
    Comandos complejos (buscar en internet, abrir apps, mensajes, resumir/analizar) → Gemini.
    """
    texto_normalizado = texto.lower()
    if any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_COMPLEJO):
        return MOTOR_GEMINI
    return MOTOR_OLLAMA
