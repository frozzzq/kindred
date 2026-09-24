from unittest.mock import patch

from src.actions.system_control import ResultadoAccion
from src.engines.modelos import RespuestaMotor
from src.main import Respuesta, procesar_comando
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
def test_comando_simple_responde_con_ollama(mock_ollama, mock_contexto, mock_guardado):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta ollama")

    resultado = procesar_comando("recuérdame comprar leche")

    assert resultado == Respuesta(texto="respuesta ollama", motor=MOTOR_OLLAMA)
    mock_guardado.assert_called_once_with("recuérdame comprar leche", "respuesta ollama", MOTOR_OLLAMA)


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_gemini")
def test_comando_complejo_responde_con_gemini(mock_gemini, mock_contexto, mock_guardado):
    mock_gemini.return_value = RespuestaMotor(exito=True, texto="respuesta gemini")

    resultado = procesar_comando("busca en internet el clima")

    assert resultado == Respuesta(texto="respuesta gemini", motor=MOTOR_GEMINI)


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
@patch("src.main.preguntar_gemini")
def test_fallback_a_ollama_si_gemini_falla(mock_gemini, mock_ollama, mock_contexto, mock_guardado):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin cuota")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de respaldo")

    resultado = procesar_comando("busca en internet el clima")

    assert resultado == Respuesta(texto="respuesta de respaldo", motor=MOTOR_OLLAMA)


@patch("src.main.evaluar_guardado")
@patch("src.main.abrir_aplicacion")
def test_abrir_app_confirmada_ejecuta_la_accion(mock_abrir, mock_guardado):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo calculadora...")
    confirmador_siempre_si = lambda descripcion: True

    resultado = procesar_comando("abre la calculadora", confirmador=confirmador_siempre_si)

    mock_abrir.assert_called_once_with("calculadora")
    assert resultado == Respuesta(texto="Abriendo calculadora...", motor=MOTOR_ACCION)


@patch("src.main.evaluar_guardado")
@patch("src.main.abrir_aplicacion")
def test_abrir_app_sin_confirmar_no_ejecuta_nada(mock_abrir, mock_guardado):
    confirmador_siempre_no = lambda descripcion: False

    resultado = procesar_comando("abre la calculadora", confirmador=confirmador_siempre_no)

    mock_abrir.assert_not_called()
    assert resultado.motor == MOTOR_ACCION
    assert "ancel" in resultado.texto.lower()
