from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.engines.ollama_client import MAX_RONDAS_HERRAMIENTAS, conversar_ollama, preguntar_ollama
from src.obsidian.herramientas import DEFINICIONES


def _respuesta_http(datos):
    respuesta = MagicMock()
    respuesta.json.return_value = datos
    respuesta.raise_for_status.return_value = None
    return respuesta


def _mensaje(contenido="", llamadas=None):
    mensaje = {"role": "assistant", "content": contenido}
    if llamadas:
        mensaje["tool_calls"] = llamadas
    return {"message": mensaje}


def _llamada(nombre, argumentos):
    return {"function": {"name": nombre, "arguments": argumentos}}


@patch("src.engines.ollama_client.httpx.post")
def test_conversar_sin_herramientas_devuelve_el_texto(mock_post):
    mock_post.return_value = _respuesta_http(_mensaje("Hola, soy Crimson."))

    resultado = conversar_ollama([{"role": "user", "content": "hola"}])

    assert resultado.exito and resultado.texto == "Hola, soy Crimson."
    assert mock_post.call_args.args[0].endswith("/api/chat")


@patch("src.engines.ollama_client.httpx.post")
def test_conversar_ejecuta_herramienta_y_devuelve_la_respuesta_final(mock_post):
    mock_post.side_effect = [
        _respuesta_http(_mensaje(llamadas=[_llamada("leer_nota", {"ruta": "02-Tareas/Pendientes.md"})])),
        _respuesta_http(_mensaje("Tienes dos pendientes.")),
    ]
    ejecutadas = []

    def ejecutar(nombre, argumentos):
        ejecutadas.append((nombre, argumentos))
        return "- [ ] Comprar pan\n- [ ] Comprar leche"

    resultado = conversar_ollama([{"role": "user", "content": "¿qué pendientes tengo?"}], DEFINICIONES, ejecutar)

    assert resultado.texto == "Tienes dos pendientes."
    assert ejecutadas == [("leer_nota", {"ruta": "02-Tareas/Pendientes.md"})]
    segunda_llamada = mock_post.call_args_list[1].kwargs["json"]["messages"]
    assert segunda_llamada[-1] == {
        "role": "tool",
        "tool_name": "leer_nota",
        "content": "- [ ] Comprar pan\n- [ ] Comprar leche",
    }


@patch("src.engines.ollama_client.httpx.post")
def test_conversar_acepta_argumentos_como_texto_json(mock_post):
    mock_post.side_effect = [
        _respuesta_http(_mensaje(llamadas=[_llamada("leer_nota", '{"ruta": "a.md"}')])),
        _respuesta_http(_mensaje("ok")),
    ]
    recibidos = []

    conversar_ollama([], DEFINICIONES, lambda nombre, args: recibidos.append(args) or "contenido")

    assert recibidos == [{"ruta": "a.md"}]


@patch("src.engines.ollama_client.httpx.post")
def test_conversar_corta_si_el_modelo_encadena_herramientas_sin_fin(mock_post):
    mock_post.return_value = _respuesta_http(_mensaje(llamadas=[_llamada("listar_notas", {})]))

    resultado = conversar_ollama([], DEFINICIONES, lambda nombre, args: "algo")

    assert resultado.exito is False
    assert mock_post.call_count == MAX_RONDAS_HERRAMIENTAS


@patch("src.engines.ollama_client.httpx.post")
def test_conversar_ejecuta_una_llamada_escrita_como_texto(mock_post):
    """Caso real: el modelo respondió el JSON de la llamada en el texto en vez de usar tool_calls."""
    escrita = ' recordar_sobre_usuario\n{"name": "recordar_sobre_usuario", "arguments": {"dato": "Se llama Luis"}}'
    mock_post.side_effect = [
        _respuesta_http(_mensaje(escrita)),
        _respuesta_http(_mensaje("Mucho gusto, Luis.")),
    ]
    ejecutadas = []

    resultado = conversar_ollama([], DEFINICIONES, lambda nombre, args: ejecutadas.append((nombre, args)) or "ok")

    assert ejecutadas == [("recordar_sobre_usuario", {"dato": "Se llama Luis"})]
    assert resultado.texto == "Mucho gusto, Luis."
    assert resultado.herramientas_usadas == ["recordar_sobre_usuario"]


@pytest.mark.parametrize(
    "escrita",
    [
        ' recordar_sobre_usuario\n{"dato": "Su nombre es Josue"}',  # caso real de la UI
        '<tool_call>recordar_sobre_usuario {"dato": "Su nombre es Josue"}</tool_call>',
    ],
)
@patch("src.engines.ollama_client.httpx.post")
def test_conversar_ejecuta_nombre_seguido_de_argumentos(mock_post, escrita):
    mock_post.side_effect = [
        _respuesta_http(_mensaje(escrita)),
        _respuesta_http(_mensaje("Mucho gusto, Josué.")),
    ]
    ejecutadas = []

    resultado = conversar_ollama([], DEFINICIONES, lambda nombre, args: ejecutadas.append((nombre, args)) or "ok")

    assert ejecutadas == [("recordar_sobre_usuario", {"dato": "Su nombre es Josue"})]
    assert resultado.texto == "Mucho gusto, Josué."


@patch("src.engines.ollama_client.httpx.post")
def test_texto_normal_que_menciona_una_herramienta_no_se_ejecuta(mock_post):
    mock_post.return_value = _respuesta_http(_mensaje('Puedo usar leer_nota con {"ruta": "a.md"} si quieres'))

    resultado = conversar_ollama([], DEFINICIONES, lambda nombre, args: "ok")

    assert resultado.herramientas_usadas == []


@patch("src.engines.ollama_client.httpx.post")
def test_json_que_no_es_una_herramienta_se_deja_como_texto(mock_post):
    mock_post.return_value = _respuesta_http(_mensaje('Tu config es {"name": "Luis"}'))

    resultado = conversar_ollama([], DEFINICIONES, lambda nombre, args: "ok")

    assert resultado.texto == 'Tu config es {"name": "Luis"}'


@patch("src.engines.ollama_client.httpx.post")
def test_preguntar_con_formato_json(mock_post):
    mock_post.return_value = _respuesta_http({"response": "{}"})

    preguntar_ollama("analiza", formato="json")

    assert mock_post.call_args.kwargs["json"]["format"] == "json"


@patch("src.engines.ollama_client.httpx.post")
def test_respuesta_exitosa(mock_post, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://pc-gpu:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral:7b")

    mock_respuesta = MagicMock()
    mock_respuesta.json.return_value = {"response": "hola"}
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    resultado = preguntar_ollama("hola")

    assert resultado.exito is True
    assert resultado.texto == "hola"


@patch("src.engines.ollama_client.httpx.post")
def test_envia_num_ctx_mayor_al_default_de_ollama(mock_post):
    mock_respuesta = MagicMock()
    mock_respuesta.json.return_value = {"response": "hola"}
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    preguntar_ollama("hola")

    _args, kwargs = mock_post.call_args
    assert kwargs["json"]["options"]["num_ctx"] == 8192


@patch("src.engines.ollama_client.httpx.post")
def test_desactiva_el_modo_de_pensamiento(mock_post):
    mock_respuesta = MagicMock()
    mock_respuesta.json.return_value = {"response": "hola"}
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    preguntar_ollama("hola")

    _args, kwargs = mock_post.call_args
    assert kwargs["json"]["think"] is False


@patch("src.engines.ollama_client.httpx.post")
def test_manda_keep_alive_para_no_descargar_el_modelo(mock_post):
    mock_respuesta = MagicMock()
    mock_respuesta.json.return_value = {"response": "hola"}
    mock_respuesta.raise_for_status.return_value = None
    mock_post.return_value = mock_respuesta

    preguntar_ollama("hola")

    _args, kwargs = mock_post.call_args
    assert kwargs["json"]["keep_alive"] == "30m"


@patch("src.engines.ollama_client.httpx.post")
def test_error_de_conexion_no_crashea(mock_post):
    mock_post.side_effect = httpx.ConnectError("no se pudo conectar")

    resultado = preguntar_ollama("hola")

    assert resultado.exito is False
    assert resultado.error
