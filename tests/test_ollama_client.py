from unittest.mock import MagicMock, patch

import httpx

from src.engines.ollama_client import preguntar_ollama


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
