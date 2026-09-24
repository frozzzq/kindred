"""Cliente HTTP para el motor local: Ollama corriendo en la PC con GPU."""

import json
import os
from collections.abc import Callable

import httpx

from src.engines.modelos import RespuestaMotor

# Una recarga en frío del modelo (~5-6GB a VRAM) llegó a tardar ~30s en
# pruebas; 120s deja margen para eso más una respuesta larga.
TIMEOUT_SEGUNDOS = 120
# Ollama usa 4096 tokens de contexto por defecto aunque el modelo soporte
# mucho más. Con el prompt de sistema + historial + notas leídas, 8192 da
# margen real sin arriesgar la VRAM disponible.
CONTEXTO_TOKENS = 8192
# Sin esto, Ollama descarga el modelo de la VRAM tras 5 minutos sin uso
# (default del servidor) y cada mensaje siguiente paga la recarga completa
# desde disco (varios segundos) antes de poder generar nada. 30 minutos
# alcanza para una sesión de uso normal sin quedarse cargado para siempre.
KEEP_ALIVE = "30m"
# Tope de rondas modelo → herramienta → modelo por mensaje, para que un
# modelo confundido no se quede llamando herramientas en bucle.
MAX_RONDAS_HERRAMIENTAS = 5

EjecutorHerramientas = Callable[[str, dict], str]


def _cuerpo_base(modelo: str) -> dict:
    return {
        "model": modelo,
        "stream": False,
        # think=False: modelos tipo Qwen3 generan un razonamiento interno largo
        # por defecto (varios segundos extra por respuesta) que nunca mostramos
        # ni usamos. Desactivarlo bajó una respuesta trivial de ~5.8s a ~0.6s.
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": CONTEXTO_TOKENS},
    }


def _enviar(endpoint: str, cuerpo: dict) -> dict | RespuestaMotor:
    """POST a Ollama. Devuelve el JSON de respuesta, o un RespuestaMotor de error."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host.rstrip('/')}/api/{endpoint}"
    try:
        respuesta = httpx.post(url, json=cuerpo, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
    except httpx.RequestError as error:
        return RespuestaMotor(exito=False, error=f"No se pudo conectar a Ollama en {url}: {error}")
    except httpx.HTTPStatusError as error:
        codigo = error.response.status_code
        return RespuestaMotor(exito=False, error=f"Ollama respondió con error {codigo}")
    return respuesta.json()


def _modelo() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3:8b")


def preguntar_ollama(prompt: str, formato: str | None = None) -> RespuestaMotor:
    """Envía un prompt suelto a Ollama (sin historial ni herramientas).

    formato="json" fuerza una respuesta en JSON válido (útil para tareas
    internas como la reflexión, no para conversar).
    """
    cuerpo = _cuerpo_base(_modelo()) | {"prompt": prompt}
    if formato:
        cuerpo["format"] = formato
    datos = _enviar("generate", cuerpo)
    if isinstance(datos, RespuestaMotor):
        return datos
    return RespuestaMotor(exito=True, texto=datos.get("response", ""))


def _llamada_escrita_como_texto(contenido: str, nombres_validos: set[str]) -> dict | None:
    """Recupera una llamada a herramienta que el modelo escribió como JSON en el texto.

    Pasó en pruebas reales: en vez de usar tool_calls respondió literalmente
    '{"name": "recordar_sobre_usuario", "arguments": {...}}', y eso se habría
    leído en voz alta sin guardar nada.
    """
    inicio, fin = contenido.find("{"), contenido.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(contenido[inicio : fin + 1])
    except json.JSONDecodeError:
        return None
    if isinstance(datos, dict) and datos.get("name") in nombres_validos:
        return {"function": {"name": datos["name"], "arguments": datos.get("arguments") or {}}}
    return None


def conversar_ollama(
    mensajes: list[dict],
    herramientas: list[dict] | None = None,
    ejecutar: EjecutorHerramientas | None = None,
) -> RespuestaMotor:
    """Conversa con Ollama (modo chat) dejando que el modelo use herramientas.

    Si el modelo pide herramientas, se ejecutan con `ejecutar(nombre, argumentos)`,
    se le devuelven los resultados y se le vuelve a preguntar, hasta que
    responda con texto o se alcance MAX_RONDAS_HERRAMIENTAS.
    """
    mensajes = list(mensajes)
    usadas: list[str] = []
    nombres_validos = {h["function"]["name"] for h in herramientas or []}
    for _ in range(MAX_RONDAS_HERRAMIENTAS):
        cuerpo = _cuerpo_base(_modelo()) | {"messages": mensajes}
        if herramientas:
            cuerpo["tools"] = herramientas
        datos = _enviar("chat", cuerpo)
        if isinstance(datos, RespuestaMotor):
            return datos

        mensaje = datos.get("message", {})
        llamadas = mensaje.get("tool_calls") or []
        if not llamadas and ejecutar is not None:
            escrita = _llamada_escrita_como_texto(mensaje.get("content", ""), nombres_validos)
            if escrita:
                llamadas = [escrita]
                mensaje = {"role": "assistant", "content": "", "tool_calls": llamadas}
        if not llamadas or ejecutar is None:
            return RespuestaMotor(exito=True, texto=mensaje.get("content", ""), herramientas_usadas=usadas)

        mensajes.append(mensaje)
        for llamada in llamadas:
            funcion = llamada.get("function", {})
            argumentos = funcion.get("arguments") or {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos or "{}")
                except json.JSONDecodeError:
                    argumentos = {}
            resultado = ejecutar(funcion.get("name", ""), argumentos)
            usadas.append(funcion.get("name", ""))
            mensajes.append({"role": "tool", "tool_name": funcion.get("name", ""), "content": resultado})

    return RespuestaMotor(exito=False, error="El modelo encadenó demasiadas herramientas sin responder")
