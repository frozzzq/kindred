"""Cliente para el motor en la nube: Gemini Flash (API de Google AI Studio)."""

import os
from collections.abc import Callable

from src.engines.modelos import RespuestaMotor

TIMEOUT_MS = 120_000  # mismo margen que Ollama (120s)
REINTENTOS_TRANSITORIOS = 2
CODIGOS_REINTENTABLES = (500, 502, 503, 504)  # NO incluye 429 (cuota): debe fallar rápido a Ollama
MAX_RONDAS_HERRAMIENTAS = 8  # Gemini encadena varias acciones en un turno ("abre X y escribe Y")


def _crear_cliente(genai, types, api_key: str):
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(
                attempts=REINTENTOS_TRANSITORIOS + 1,
                initial_delay=0.5,
                max_delay=1.0,
                http_status_codes=CODIGOS_REINTENTABLES,
            ),
        ),
    )


def preguntar_gemini(
    prompt: str,
    usar_busqueda_web: bool = False,
    instruccion_sistema: str | None = None,
) -> RespuestaMotor:
    """Envía un prompt a Gemini Flash y devuelve la respuesta generada.

    Si usar_busqueda_web=True, activa el grounding con Google Search del
    propio Gemini para que la respuesta pueda basarse en resultados reales
    de internet (Fase 4), en vez del conocimiento estático del modelo.
    instruccion_sistema define la identidad/personalidad del agente.

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

    opciones = {}
    if usar_busqueda_web:
        opciones["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if instruccion_sistema:
        opciones["system_instruction"] = instruccion_sistema
    config = types.GenerateContentConfig(**opciones) if opciones else None

    try:
        cliente = _crear_cliente(genai, types, api_key)
        respuesta = cliente.models.generate_content(model=modelo, contents=prompt, config=config)
    except Exception as error:  # noqa: BLE001 - cualquier fallo de la API cae a fallback, no debe crashear
        return RespuestaMotor(exito=False, error=f"Gemini falló: {error}")

    return RespuestaMotor(exito=True, texto=getattr(respuesta, "text", "") or "")


def conversar_gemini(
    prompt: str,
    herramientas: list[dict],
    ejecutar: Callable[[str, dict], str],
    instruccion_sistema: str | None = None,
) -> RespuestaMotor:
    """Como preguntar_gemini, pero dejando que Gemini use herramientas (function calling).

    La ejecución automática de funciones de la librería va desactivada: cada
    llamada pasa por `ejecutar` (el registro con permisos), así una acción
    irreversible nunca se salta la confirmación. `herramientas` son
    declaraciones {name, description, parameters_json_schema}.
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

    config = types.GenerateContentConfig(
        system_instruction=instruccion_sistema,
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**h) for h in herramientas])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contenidos = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
    usadas: list[str] = []
    resultados_texto: list[str] = []

    try:
        cliente = _crear_cliente(genai, types, api_key)
        for _ in range(MAX_RONDAS_HERRAMIENTAS):
            respuesta = cliente.models.generate_content(model=modelo, contents=contenidos, config=config)
            llamadas = respuesta.function_calls or []
            if not llamadas:
                return RespuestaMotor(
                    exito=True, texto=respuesta.text or "", herramientas_usadas=usadas,
                    resultados_herramientas=resultados_texto,
                )

            contenidos.append(respuesta.candidates[0].content)
            partes_respuesta = []
            for llamada in llamadas:
                resultado = ejecutar(llamada.name, dict(llamada.args or {}))
                usadas.append(llamada.name)
                resultados_texto.append(resultado)
                partes_respuesta.append(
                    types.Part.from_function_response(name=llamada.name, response={"resultado": resultado})
                )
            contenidos.append(types.Content(role="user", parts=partes_respuesta))
    except Exception as error:  # noqa: BLE001 - cualquier fallo de la API cae a fallback, no debe crashear
        # herramientas_usadas va también en el error: si ya actuó, el fallback no debe repetir las acciones.
        return RespuestaMotor(exito=False, error=f"Gemini falló: {error}", herramientas_usadas=usadas)

    return RespuestaMotor(
        exito=False, error="Gemini encadenó demasiadas herramientas sin responder", herramientas_usadas=usadas
    )
