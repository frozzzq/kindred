"""Cliente HTTP para el motor local: Ollama corriendo en la PC con GPU."""

import json
import os
import re
import time
from collections.abc import Callable

import httpx

from src.engines.modelos import RespuestaMotor

# Una recarga en frío del modelo (~5-6GB a VRAM) llegó a tardar ~30s en
# pruebas; 120s deja margen para eso más una respuesta larga.
TIMEOUT_SEGUNDOS = 120
# Reintentos ante errores de red transitorios (no para HTTPStatusError).
REINTENTOS_TRANSITORIOS = 2
ESPERA_ENTRE_REINTENTOS = (0.5, 1.0)
# Ollama usa 4096 tokens de contexto por defecto aunque el modelo soporte
# mucho más. Con el prompt de sistema + historial + notas leídas, 8192 da
# margen real sin arriesgar la VRAM disponible.
CONTEXTO_TOKENS = 8192
# Sin esto, Ollama descarga el modelo de la VRAM tras 5 minutos sin uso
# (default del servidor) y el siguiente mensaje paga la recarga completa
# desde disco: ~35 s medidos (el primer mensaje tras 40 min sin uso tardó 38 s).
# 3 horas cubre una sesión larga sin quedarse cargado para siempre; se ajusta
# con OLLAMA_KEEP_ALIVE ("-1" = nunca descargarlo). Además la UI lo precalienta.
KEEP_ALIVE_POR_DEFECTO = "3h"
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
        "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", KEEP_ALIVE_POR_DEFECTO),
        "options": {"num_ctx": CONTEXTO_TOKENS},
    }


def _enviar(endpoint: str, cuerpo: dict) -> dict | RespuestaMotor:
    """POST a Ollama. Devuelve el JSON de respuesta, o un RespuestaMotor de error."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host.rstrip('/')}/api/{endpoint}"
    for intento in range(REINTENTOS_TRANSITORIOS + 1):
        try:
            respuesta = httpx.post(url, json=cuerpo, timeout=TIMEOUT_SEGUNDOS)
            respuesta.raise_for_status()
            break
        except httpx.RequestError as error:
            if intento == REINTENTOS_TRANSITORIOS:
                return RespuestaMotor(exito=False, error=f"No se pudo conectar a Ollama en {url}: {error}")
            time.sleep(ESPERA_ENTRE_REINTENTOS[intento])
        except httpx.HTTPStatusError as error:
            codigo = error.response.status_code
            return RespuestaMotor(exito=False, error=f"Ollama respondió con error {codigo}")
    try:
        return respuesta.json()
    except json.JSONDecodeError as error:
        return RespuestaMotor(exito=False, error=f"Ollama devolvió una respuesta que no es JSON válido: {error}")


def _modelo() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3:8b")


AlTexto = Callable[[str, list[str]], None]  # (fragmento de texto, herramientas usadas hasta ahora)
CARACTERES_PARA_DECIDIR = 12  # cuánto texto esperar antes de saber si es respuesta o una llamada escrita


def _parece_llamada(inicio: str, nombres_validos: set[str]) -> bool:
    """¿El texto que empieza a llegar es una llamada a herramienta escrita como texto (JSON)?"""
    inicio = inicio.lstrip()
    if inicio.startswith(("{", "<", "`", "[")):
        return True
    primera = re.match(r"\w+", inicio)
    return bool(primera and primera.group(0) in nombres_validos)


def _enviar_en_vivo(cuerpo: dict, al_texto: AlTexto, usadas: list[str], nombres_validos: set[str]) -> dict | RespuestaMotor:
    """Como _enviar("chat", ...), pero en streaming: pasa el texto a al_texto conforme se genera.

    Si el texto parece una llamada a herramienta escrita como JSON, no se reenvía (se leería en voz
    alta); conversar_ollama la recupera y ejecuta igual que en modo normal.
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host.rstrip('/')}/api/chat"
    contenido: list[str] = []
    llamadas: list[dict] = []
    colchon = ""
    reenviar: bool | None = None
    for intento in range(REINTENTOS_TRANSITORIOS + 1):
        try:
            with httpx.stream("POST", url, json=cuerpo | {"stream": True}, timeout=TIMEOUT_SEGUNDOS) as respuesta:
                respuesta.raise_for_status()
                for linea in respuesta.iter_lines():
                    if not linea.strip():
                        continue
                    datos = json.loads(linea)
                    mensaje = datos.get("message", {})
                    llamadas.extend(mensaje.get("tool_calls") or [])
                    fragmento = mensaje.get("content", "")
                    if fragmento:
                        contenido.append(fragmento)
                        if reenviar is None:
                            colchon += fragmento
                            if len(colchon.strip()) >= CARACTERES_PARA_DECIDIR:
                                reenviar = not _parece_llamada(colchon, nombres_validos)
                                if reenviar:
                                    al_texto(colchon, usadas)
                        elif reenviar:
                            al_texto(fragmento, usadas)
                    if datos.get("done"):
                        break
            break
        except httpx.RequestError as error:
            if contenido or intento == REINTENTOS_TRANSITORIOS:
                return RespuestaMotor(exito=False, error=f"No se pudo conectar a Ollama en {url}: {error}")
            time.sleep(ESPERA_ENTRE_REINTENTOS[intento])
        except httpx.HTTPStatusError as error:
            return RespuestaMotor(exito=False, error=f"Ollama respondió con error {error.response.status_code}")
        except json.JSONDecodeError as error:
            return RespuestaMotor(exito=False, error=f"Ollama devolvió una respuesta que no es JSON válido: {error}")
    if reenviar is None and colchon.strip() and not llamadas and not _parece_llamada(colchon, nombres_validos):
        al_texto(colchon, usadas)  # respuesta cortísima ("¡Hola!"), más corta que CARACTERES_PARA_DECIDIR
    mensaje = {"role": "assistant", "content": "".join(contenido)}
    if llamadas:
        mensaje["tool_calls"] = llamadas
    return {"message": mensaje}


def precalentar(mensajes: list[dict], herramientas: list[dict] | None = None) -> bool:
    """Carga el modelo en la VRAM y deja procesado (en caché) el prompt de sistema.

    Así el primer mensaje real no paga ni la recarga (~35 s) ni procesar el prompt en frío (~2 s).
    Genera un solo token. Devuelve False si Ollama no respondió.
    """
    cuerpo = _cuerpo_base(_modelo()) | {"messages": mensajes}
    cuerpo["options"] = cuerpo["options"] | {"num_predict": 1}
    if herramientas:
        cuerpo["tools"] = herramientas
    return not isinstance(_enviar("chat", cuerpo), RespuestaMotor)


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


# Marcas que a veces rodean una llamada escrita como texto ("<tool_call>", "```json"...).
_ENVOLTURAS_DE_LLAMADA = {"tool_call", "json", "function"}


def _llamada_escrita_como_texto(contenido: str, nombres_validos: set[str]) -> dict | None:
    """Recupera una llamada a herramienta que el modelo escribió en el texto en vez de ejecutarla.

    Variantes vistas en pruebas reales (se habrían leído en voz alta sin guardar nada):
    - '{"name": "recordar_sobre_usuario", "arguments": {"dato": ...}}'
    - 'recordar_sobre_usuario {"dato": "Su nombre es Josue"}'  (nombre antes, JSON = argumentos)
    """
    inicio, fin = contenido.find("{"), contenido.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        datos = json.loads(contenido[inicio : fin + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(datos, dict):
        return None
    if datos.get("name") in nombres_validos:
        return {"function": {"name": datos["name"], "arguments": datos.get("arguments") or {}}}

    # Solo si antes del JSON no hay nada más que el nombre de la herramienta (y marcas):
    # así un texto normal que mencione una herramienta no se ejecuta por accidente.
    palabras = re.findall(r"\w+", contenido[:inicio])
    if palabras and palabras[-1] in nombres_validos and set(palabras) <= nombres_validos | _ENVOLTURAS_DE_LLAMADA:
        return {"function": {"name": palabras[-1], "arguments": datos}}
    return None


def conversar_ollama(
    mensajes: list[dict],
    herramientas: list[dict] | None = None,
    ejecutar: EjecutorHerramientas | None = None,
    al_texto: AlTexto | None = None,
    al_usar_herramienta: Callable[[str], None] | None = None,
) -> RespuestaMotor:
    """Conversa con Ollama (modo chat) dejando que el modelo use herramientas.

    Si el modelo pide herramientas, se ejecutan con `ejecutar(nombre, argumentos)`,
    se le devuelven los resultados y se le vuelve a preguntar, hasta que
    responda con texto o se alcance MAX_RONDAS_HERRAMIENTAS.

    Con `al_texto`, la respuesta se va entregando mientras se genera (streaming): la voz puede
    empezar a hablar con la primera oración en vez de esperar la respuesta completa.
    """
    mensajes = list(mensajes)
    usadas: list[str] = []
    resultados: list[str] = []
    nombres_validos = {h["function"]["name"] for h in herramientas or []}
    for ronda in range(MAX_RONDAS_HERRAMIENTAS):
        cuerpo = _cuerpo_base(_modelo()) | {"messages": mensajes}
        if herramientas:
            cuerpo["tools"] = herramientas
        if al_texto is not None:
            datos = _enviar_en_vivo(cuerpo, al_texto, usadas, nombres_validos)
        else:
            datos = _enviar("chat", cuerpo)
        if isinstance(datos, RespuestaMotor):
            datos.herramientas_usadas = usadas
            datos.llamadas_modelo = ronda + 1
            return datos

        mensaje = datos.get("message", {})
        llamadas = mensaje.get("tool_calls") or []
        if not llamadas and ejecutar is not None:
            escrita = _llamada_escrita_como_texto(mensaje.get("content", ""), nombres_validos)
            if escrita:
                llamadas = [escrita]
                mensaje = {"role": "assistant", "content": "", "tool_calls": llamadas}
        if not llamadas or ejecutar is None:
            return RespuestaMotor(
                exito=True, texto=mensaje.get("content", ""), herramientas_usadas=usadas,
                resultados_herramientas=resultados, llamadas_modelo=ronda + 1,
            )

        mensajes.append(mensaje)
        for llamada in llamadas:
            funcion = llamada.get("function", {})
            argumentos = funcion.get("arguments") or {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos or "{}")
                except json.JSONDecodeError:
                    argumentos = {}
            if al_usar_herramienta is not None:
                al_usar_herramienta(funcion.get("name", ""))
            resultado = ejecutar(funcion.get("name", ""), argumentos)
            usadas.append(funcion.get("name", ""))
            resultados.append(resultado)
            mensajes.append({"role": "tool", "tool_name": funcion.get("name", ""), "content": resultado})

    return RespuestaMotor(
        exito=False, error="El modelo encadenó demasiadas herramientas sin responder",
        herramientas_usadas=usadas, llamadas_modelo=MAX_RONDAS_HERRAMIENTAS,
    )
