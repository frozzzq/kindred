"""Cliente HTTP para el motor local: Ollama corriendo en la PC con GPU."""

import os

import httpx

from src.engines.modelos import RespuestaMotor

TIMEOUT_SEGUNDOS = 60
# Ollama usa 4096 tokens de contexto por defecto aunque el modelo soporte
# mucho más. Con el contexto de Obsidian + búsqueda web que le inyectamos,
# se saturaba fácil. 8192 da margen real sin arriesgar la VRAM disponible.
CONTEXTO_TOKENS = 8192
# Sin esto, Ollama descarga el modelo de la VRAM tras 5 minutos sin uso
# (default del servidor) y cada mensaje siguiente paga la recarga completa
# desde disco (varios segundos) antes de poder generar nada. 30 minutos
# alcanza para una sesión de uso normal sin quedarse cargado para siempre.
KEEP_ALIVE = "30m"


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
                # think=False: modelos tipo Qwen3 generan un razonamiento
                # interno largo por defecto (varios segundos extra por
                # respuesta) que nunca mostramos ni usamos. Desactivarlo
                # bajó una respuesta trivial de ~5.8s a ~0.6s en pruebas.
                "think": False,
                "keep_alive": KEEP_ALIVE,
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
