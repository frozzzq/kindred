"""Cliente para el motor en la nube: Gemini Flash (API de Google AI Studio)."""

import os

from src.engines.modelos import RespuestaMotor


def preguntar_gemini(prompt: str, usar_busqueda_web: bool = False) -> RespuestaMotor:
    """Envía un prompt a Gemini Flash y devuelve la respuesta generada.

    Si usar_busqueda_web=True, activa el grounding con Google Search del
    propio Gemini para que la respuesta pueda basarse en resultados reales
    de internet (Fase 4), en vez del conocimiento estático del modelo.

    Cualquier fallo (sin API key, sin cuota, sin internet) se reporta como
    RespuestaMotor(exito=False) para que el router haga fallback a Ollama,
    en vez de dejar que la excepción se propague.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    if not api_key:
        return RespuestaMotor(exito=False, error="Falta GEMINI_API_KEY en el entorno")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return RespuestaMotor(exito=False, error="El paquete 'google-genai' no está instalado")

    config = None
    if usar_busqueda_web:
        config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])

    try:
        cliente = genai.Client(api_key=api_key)
        respuesta = cliente.models.generate_content(model=modelo, contents=prompt, config=config)
    except Exception as error:  # noqa: BLE001 - cualquier fallo de la API cae a fallback, no debe crashear
        return RespuestaMotor(exito=False, error=f"Gemini falló: {error}")

    return RespuestaMotor(exito=True, texto=getattr(respuesta, "text", "") or "")
