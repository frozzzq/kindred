import sys
import types
from unittest.mock import MagicMock

from src.engines.gemini_client import preguntar_gemini


def _mockear_google_genai(monkeypatch, cliente_mock):
    """Inserta un stub de google.genai (y google.genai.types) en sys.modules."""
    modulo_types = types.ModuleType("google.genai.types")
    modulo_types.GenerateContentConfig = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.Tool = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.GoogleSearch = MagicMock(return_value="google-search-tool")

    modulo_genai = types.ModuleType("google.genai")
    modulo_genai.Client = MagicMock(return_value=cliente_mock)
    modulo_genai.types = modulo_types

    modulo_google = types.ModuleType("google")
    modulo_google.genai = modulo_genai

    monkeypatch.setitem(sys.modules, "google", modulo_google)
    monkeypatch.setitem(sys.modules, "google.genai", modulo_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", modulo_types)

    return modulo_types


def test_sin_api_key_falla_sin_crashear(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resultado = preguntar_gemini("hola")

    assert resultado.exito is False
    assert "GEMINI_API_KEY" in resultado.error


def test_respuesta_exitosa(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = types.SimpleNamespace(text="hola desde gemini")
    _mockear_google_genai(monkeypatch, cliente_mock)

    resultado = preguntar_gemini("hola")

    assert resultado.exito is True
    assert resultado.texto == "hola desde gemini"


def test_usar_busqueda_web_pasa_config_con_tool_de_google_search(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = types.SimpleNamespace(text="respuesta con busqueda")
    modulo_types = _mockear_google_genai(monkeypatch, cliente_mock)

    resultado = preguntar_gemini("busca el clima de hoy", usar_busqueda_web=True)

    assert resultado.exito is True
    _args, kwargs = cliente_mock.models.generate_content.call_args
    assert kwargs["config"] is not None
    modulo_types.GoogleSearch.assert_called_once()


def test_sin_busqueda_web_config_es_none(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = types.SimpleNamespace(text="respuesta normal")
    _mockear_google_genai(monkeypatch, cliente_mock)

    preguntar_gemini("hola")

    _args, kwargs = cliente_mock.models.generate_content.call_args
    assert kwargs["config"] is None
