import sys
import types
from unittest.mock import MagicMock

from src.engines.gemini_client import MAX_RONDAS_HERRAMIENTAS, conversar_gemini, preguntar_gemini


def _mockear_google_genai(monkeypatch, cliente_mock):
    """Inserta un stub de google.genai (y google.genai.types) en sys.modules."""
    modulo_types = types.ModuleType("google.genai.types")
    modulo_types.GenerateContentConfig = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.Tool = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.GoogleSearch = MagicMock(return_value="google-search-tool")
    modulo_types.HttpOptions = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.HttpRetryOptions = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.FunctionDeclaration = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.AutomaticFunctionCallingConfig = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.Content = MagicMock(side_effect=lambda **kwargs: kwargs)
    modulo_types.Part = MagicMock()
    modulo_types.Part.from_text = MagicMock(side_effect=lambda text: {"texto": text})
    modulo_types.Part.from_function_response = MagicMock(side_effect=lambda name, response: {"funcion": name, **response})

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


def test_pasa_timeout_y_reintentos_al_cliente(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = types.SimpleNamespace(text="ok")
    modulo_types = _mockear_google_genai(monkeypatch, cliente_mock)

    preguntar_gemini("hola")

    # Verificar que genai.Client fue llamado con http_options
    _args, kwargs = modulo_types.HttpOptions.call_args
    assert kwargs["timeout"] == 120_000
    assert "retry_options" in kwargs
    retry_args, retry_kwargs = modulo_types.HttpRetryOptions.call_args
    assert retry_kwargs["http_status_codes"] == (500, 502, 503, 504)
    assert retry_kwargs["attempts"] == 3  # REINTENTOS_TRANSITORIOS + 1


# --- conversar_gemini (function calling) ---

HERRAMIENTAS = [{"name": "abrir_aplicacion", "description": "Abre una app.", "parameters_json_schema": {}}]


def _pide_funcion(nombre, argumentos):
    return types.SimpleNamespace(
        function_calls=[types.SimpleNamespace(name=nombre, args=argumentos)],
        candidates=[types.SimpleNamespace(content={"rol": "model", "llamada": nombre})],
        text=None,
    )


def _responde(texto):
    return types.SimpleNamespace(function_calls=None, text=texto)


def test_conversar_ejecuta_la_herramienta_pedida_y_devuelve_la_respuesta_final(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.side_effect = [
        _pide_funcion("abrir_aplicacion", {"nombre": "spotify"}),
        _responde("Listo, abrí Spotify."),
    ]
    modulo_types = _mockear_google_genai(monkeypatch, cliente_mock)
    ejecutadas = []

    resultado = conversar_gemini("abre spotify", HERRAMIENTAS, lambda n, a: ejecutadas.append((n, a)) or "Abriendo Spotify...")

    assert resultado.exito is True
    assert resultado.texto == "Listo, abrí Spotify."
    assert resultado.herramientas_usadas == ["abrir_aplicacion"]
    assert resultado.resultados_herramientas == ["Abriendo Spotify..."]
    assert ejecutadas == [("abrir_aplicacion", {"nombre": "spotify"})]
    # la segunda vuelta lleva el resultado de la herramienta
    contenidos = cliente_mock.models.generate_content.call_args.kwargs["contents"]
    assert contenidos[-1]["parts"] == [{"funcion": "abrir_aplicacion", "resultado": "Abriendo Spotify..."}]
    # la ejecución automática de la librería va apagada: todo pasa por los permisos propios
    modulo_types.AutomaticFunctionCallingConfig.assert_called_once_with(disable=True)


def test_conversar_corta_si_encadena_herramientas_sin_fin(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.return_value = _pide_funcion("abrir_aplicacion", {"nombre": "x"})
    _mockear_google_genai(monkeypatch, cliente_mock)

    resultado = conversar_gemini("abre x", HERRAMIENTAS, lambda n, a: "ok")

    assert resultado.exito is False
    assert cliente_mock.models.generate_content.call_count == MAX_RONDAS_HERRAMIENTAS
    assert len(resultado.herramientas_usadas) == MAX_RONDAS_HERRAMIENTAS


def test_conversar_si_falla_a_la_mitad_reporta_lo_que_ya_hizo(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    cliente_mock = MagicMock()
    cliente_mock.models.generate_content.side_effect = [
        _pide_funcion("abrir_aplicacion", {"nombre": "spotify"}),
        RuntimeError("se cortó la conexión"),
    ]
    _mockear_google_genai(monkeypatch, cliente_mock)

    resultado = conversar_gemini("abre spotify", HERRAMIENTAS, lambda n, a: "ok")

    assert resultado.exito is False
    assert resultado.herramientas_usadas == ["abrir_aplicacion"]


def test_conversar_sin_api_key_falla_sin_crashear(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resultado = conversar_gemini("hola", HERRAMIENTAS, lambda n, a: "ok")

    assert resultado.exito is False
