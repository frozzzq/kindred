"""Cliente HTTP para el motor local: Ollama corriendo en la PC con GPU."""

import os

import httpx

from src.engines.modelos import RespuestaMotor

TIMEOUT_SEGUNDOS = 60
# Ollama usa 4096 tokens de contexto por defecto aunque el modelo soporte
# mucho más. Con el contexto de Obsidian + búsqueda web que le inyectamos,
# se saturaba fácil. 8192 da margen real sin arriesgar la VRAM disponible.
CONTEXTO_TOKENS = 8192


def preguntar_ollama(prompt: str) -> RespuestaMotor:
    """Envía un prompt a Ollama remoto y devuelve la respuesta generada."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    modelo = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    url = f"{host.rstrip('/')}/api/generate"

    try:
        respuesta = httpx.post(
            url,
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": CONTEXTO_TOKENS},
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
    except httpx.RequestError as error:
        return RespuestaMotor(exito=False, error=f"No se pudo conectar a Ollama en {url}: {error}")
    except httpx.HTTPStatusError as error:
        codigo = error.response.status_code
        return RespuestaMotor(exito=False, error=f"Ollama respondió con error {codigo}")

    datos = respuesta.json()
    return RespuestaMotor(exito=True, texto=datos.get("response", ""))
