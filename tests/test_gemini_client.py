import sys
import types
from unittest.mock import MagicMock

from src.engines.gemini_client import preguntar_gemini


def test_sin_api_key_falla_sin_crashear(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resultado = preguntar_gemini("hola")

    assert resultado.exito is False
    assert "GEMINI_API_KEY" in resultado.error


def test_respuesta_exitosa(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = types.SimpleNamespace(text="hola desde gemini")

    modulo_genai = types.ModuleType("google.genai")
    modulo_genai.Client = MagicMock(return_value=cliente_mock)

    modulo_google = types.ModuleType("google")
    modulo_google.genai = modulo_genai

    monkeypatch.setitem(sys.modules, "google", modulo_google)
    monkeypatch.setitem(sys.modules, "google.genai", modulo_genai)

    resultado = preguntar_gemini("hola")

    assert resultado.exito is True
    assert resultado.texto == "hola desde gemini"
