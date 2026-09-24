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
def test_error_de_conexion_no_crashea(mock_post):
    mock_post.side_effect = httpx.ConnectError("no se pudo conectar")

    resultado = preguntar_ollama("hola")

    assert resultado.exito is False
    assert resultado.error
