from unittest.mock import patch

from src.actions.system_control import ResultadoAccion
from src.engines.modelos import RespuestaMotor
from src.main import INSTRUCCION_BREVEDAD, Respuesta, procesar_comando
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_GEMINI_FALLO, MOTOR_OLLAMA


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
def test_comando_simple_responde_con_ollama(mock_ollama, mock_contexto, mock_guardado):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta ollama")

    resultado = procesar_comando("recuérdame comprar leche")

    assert resultado == Respuesta(texto="respuesta ollama", motor=MOTOR_OLLAMA)
    mock_guardado.assert_called_once_with("recuérdame comprar leche", "respuesta ollama", MOTOR_OLLAMA)
    prompt_enviado = mock_ollama.call_args.args[0]
    assert INSTRUCCION_BREVEDAD in prompt_enviado


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


@patch("src.main.registrar_interaccion")
@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
@patch("src.main.preguntar_gemini")
def test_fallo_de_gemini_se_registra_para_metricas(
    mock_gemini, mock_ollama, mock_contexto, mock_guardado, mock_registrar
):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin facturación")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de respaldo")

    procesar_comando("busca en internet el clima")

    mock_registrar.assert_called_once_with(
        "busca en internet el clima", "[fallo] sin facturación", MOTOR_GEMINI_FALLO
    )


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.construir_contexto_web", return_value="")
@patch("src.main.preguntar_ollama")
@patch("src.main.preguntar_gemini")
def test_motor_forzado_ollama_salta_el_router(mock_gemini, mock_ollama, mock_web, mock_contexto, mock_guardado):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de crimson")

    resultado = procesar_comando("busca en internet el clima", motor_forzado=MOTOR_OLLAMA)

    mock_gemini.assert_not_called()
    assert resultado == Respuesta(texto="respuesta de crimson", motor=MOTOR_OLLAMA)


@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
@patch("src.main.preguntar_gemini")
def test_motor_forzado_gemini_en_comando_simple(mock_gemini, mock_ollama, mock_contexto, mock_guardado):
    mock_gemini.return_value = RespuestaMotor(exito=True, texto="respuesta de clover")

    resultado = procesar_comando("recuérdame comprar leche", motor_forzado=MOTOR_GEMINI)

    mock_ollama.assert_not_called()
    assert resultado == Respuesta(texto="respuesta de clover", motor=MOTOR_GEMINI)


@patch("src.main.evaluar_guardado")
@patch("src.main.abrir_aplicacion")
def test_motor_forzado_no_impide_abrir_apps(mock_abrir, mock_guardado):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo paint...")

    resultado = procesar_comando("abre paint", confirmador=lambda d: True, motor_forzado=MOTOR_GEMINI)

    mock_abrir.assert_called_once_with("paint")
    assert resultado.motor == MOTOR_ACCION


@patch("src.main.construir_contexto_web", return_value="Resultados de una búsqueda real...")
@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
@patch("src.main.preguntar_gemini")
def test_ollama_recibe_contexto_web_cuando_gemini_falla_en_busqueda(
    mock_gemini, mock_ollama, mock_contexto, mock_guardado, mock_contexto_web
):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin facturación")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta con contexto web")

    procesar_comando("busca en internet el clima")

    mock_contexto_web.assert_called_once_with("busca en internet el clima")
    prompt_enviado = mock_ollama.call_args.args[0]
    assert "Resultados de una búsqueda real..." in prompt_enviado


@patch("src.main.construir_contexto_web")
@patch("src.main.evaluar_guardado")
@patch("src.main.construir_contexto", return_value="")
@patch("src.main.preguntar_ollama")
def test_ollama_no_busca_web_en_comandos_simples(mock_ollama, mock_contexto, mock_guardado, mock_contexto_web):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta ollama")

    procesar_comando("recuérdame comprar leche")

    mock_contexto_web.assert_not_called()


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
