"""Cliente para el motor en la nube: Gemini Flash (API de Google AI Studio)."""

import os

from src.engines.modelos import RespuestaMotor


def preguntar_gemini(prompt: str) -> RespuestaMotor:
    """Envía un prompt a Gemini Flash y devuelve la respuesta generada.

    Cualquier fallo (sin API key, sin cuota, sin internet) se reporta como
    RespuestaMotor(exito=False) para que el router haga fallback a Ollama,
    en vez de dejar que la excepción se propague.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    modelo = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    if not api_key:
        return RespuestaMotor(exito=False, error="Falta GEMINI_API_KEY en el entorno")

    try:
        from google import genai
    except ImportError:
        return RespuestaMotor(exito=False, error="El paquete 'google-genai' no está instalado")

    try:
        cliente = genai.Client(api_key=api_key)
        respuesta = cliente.models.generate_content(model=modelo, contents=prompt)
    except Exception as error:  # noqa: BLE001 - cualquier fallo de la API cae a fallback, no debe crashear
        return RespuestaMotor(exito=False, error=f"Gemini falló: {error}")

    return RespuestaMotor(exito=True, texto=getattr(respuesta, "text", "") or "")
