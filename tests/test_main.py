from unittest.mock import patch

import pytest

from src.actions.system_control import ResultadoAccion
from src.agente.conversacion import Conversacion
from src.engines.modelos import RespuestaMotor
from src.main import Respuesta, procesar_comando
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_GEMINI_FALLO, MOTOR_OLLAMA


@pytest.fixture(autouse=True)
def sin_efectos_externos():
    """Evita tocar la bóveda real y arma un prompt de sistema falso predecible."""
    with patch("src.main.evaluar_guardado") as guardado, patch(
        "src.main.construir_prompt_sistema", side_effect=lambda motor, con_herramientas: f"sistema-{motor}"
    ), patch("src.main.registrar_interaccion"), patch("src.main.construir_contexto_web", return_value=""), patch(
        "src.main.aprender_si_quedo_sin_guardar"
    ):
        yield guardado


@patch("src.main.conversar_ollama")
def test_comando_simple_responde_crimson_con_personalidad_y_herramientas(mock_ollama, sin_efectos_externos):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Tienes tres pendientes.")

    resultado = procesar_comando("¿qué pendientes tengo?")

    assert resultado == Respuesta(texto="Tienes tres pendientes.", motor=MOTOR_OLLAMA)
    mensajes = mock_ollama.call_args.args[0]
    assert mensajes[0] == {"role": "system", "content": "sistema-ollama"}
    assert mensajes[-1] == {"role": "user", "content": "¿qué pendientes tengo?"}
    assert mock_ollama.call_args.kwargs["herramientas"]  # tiene herramientas de la bóveda
    sin_efectos_externos.assert_called_once_with("¿qué pendientes tengo?", "Tienes tres pendientes.", MOTOR_OLLAMA)


@patch("src.main.conversar_ollama")
def test_recuerda_turnos_anteriores_de_la_conversacion(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="¿Cuál pendiente?")
    conversacion = Conversacion()
    procesar_comando("agrega un pendiente", conversacion=conversacion)
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Listo.", herramientas_usadas=["agregar_pendiente"])

    procesar_comando("comprar leche", conversacion=conversacion)

    mensajes = mock_ollama.call_args.args[0]
    assert {"role": "user", "content": "agrega un pendiente"} in mensajes
    assert {"role": "assistant", "content": "¿Cuál pendiente?"} in mensajes


@patch("src.main.conversar_ollama")
def test_si_dice_que_guardo_algo_sin_herramienta_se_le_pide_hacerlo(mock_ollama):
    """Caso real: dijo 'He marcado como completada la tarea' sin llamar ninguna herramienta."""
    mock_ollama.side_effect = [
        RespuestaMotor(exito=True, texto="He marcado como completada la tarea de comprar pan."),
        RespuestaMotor(exito=True, texto="Listo, comprar pan quedó completado.", herramientas_usadas=["completar_pendiente"]),
    ]

    resultado = procesar_comando("ya compré el pan")

    assert mock_ollama.call_count == 2
    assert "Verificación del sistema" in mock_ollama.call_args.args[0][-1]["content"]
    assert resultado.texto == "Listo, comprar pan quedó completado."


@patch("src.main.conversar_ollama")
def test_si_insiste_sin_hacerlo_admite_que_no_pudo(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="He guardado tu nombre.")

    resultado = procesar_comando("me llamo Luis")

    assert "No logré" in resultado.texto


@patch("src.main.conversar_ollama")
def test_respuesta_normal_no_dispara_la_verificacion(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="La capital de Francia es París.")

    procesar_comando("capital de Francia")

    assert mock_ollama.call_count == 1


@patch("src.main.preguntar_gemini")
def test_comando_complejo_responde_clover_con_su_personalidad(mock_gemini):
    mock_gemini.return_value = RespuestaMotor(exito=True, texto="respuesta de clover")

    resultado = procesar_comando("busca en internet el clima")

    assert resultado == Respuesta(texto="respuesta de clover", motor=MOTOR_GEMINI)
    assert mock_gemini.call_args.kwargs["instruccion_sistema"] == "sistema-gemini"


@patch("src.main.conversar_ollama")
@patch("src.main.preguntar_gemini")
def test_fallback_a_ollama_si_gemini_falla(mock_gemini, mock_ollama):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin cuota")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de respaldo")

    resultado = procesar_comando("busca en internet el clima")

    assert resultado == Respuesta(texto="respuesta de respaldo", motor=MOTOR_OLLAMA)


@patch("src.main.registrar_interaccion")
@patch("src.main.conversar_ollama")
@patch("src.main.preguntar_gemini")
def test_fallo_de_gemini_se_registra_para_metricas(mock_gemini, mock_ollama, mock_registrar):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin facturación")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de respaldo")

    procesar_comando("busca en internet el clima")

    mock_registrar.assert_called_once_with("busca en internet el clima", "[fallo] sin facturación", MOTOR_GEMINI_FALLO)


@patch("src.main.conversar_ollama")
@patch("src.main.preguntar_gemini")
def test_motor_forzado_ollama_salta_el_router(mock_gemini, mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de crimson")

    resultado = procesar_comando("busca en internet el clima", motor_forzado=MOTOR_OLLAMA)

    mock_gemini.assert_not_called()
    assert resultado == Respuesta(texto="respuesta de crimson", motor=MOTOR_OLLAMA)


@patch("src.main.conversar_ollama")
@patch("src.main.preguntar_gemini")
def test_motor_forzado_gemini_en_comando_simple(mock_gemini, mock_ollama):
    mock_gemini.return_value = RespuestaMotor(exito=True, texto="respuesta de clover")

    resultado = procesar_comando("recuérdame comprar leche", motor_forzado=MOTOR_GEMINI)

    mock_ollama.assert_not_called()
    assert resultado == Respuesta(texto="respuesta de clover", motor=MOTOR_GEMINI)


@patch("src.main.construir_contexto_web", return_value="Resultados de una búsqueda real...")
@patch("src.main.conversar_ollama")
@patch("src.main.preguntar_gemini")
def test_ollama_recibe_contexto_web_cuando_gemini_falla_en_busqueda(mock_gemini, mock_ollama, mock_web):
    mock_gemini.return_value = RespuestaMotor(exito=False, error="sin facturación")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta con contexto web")

    procesar_comando("busca en internet el clima")

    mock_web.assert_called_once_with("busca en internet el clima")
    assert "Resultados de una búsqueda real..." in mock_ollama.call_args.args[0][-1]["content"]


@patch("src.main.construir_contexto_web")
@patch("src.main.conversar_ollama")
def test_ollama_no_busca_web_en_comandos_simples(mock_ollama, mock_web):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta")

    procesar_comando("recuérdame comprar leche")

    mock_web.assert_not_called()


@patch("src.main.abrir_aplicacion")
def test_abrir_app_confirmada_ejecuta_la_accion(mock_abrir):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo calculadora...")

    resultado = procesar_comando("abre la calculadora", confirmador=lambda descripcion: True)

    mock_abrir.assert_called_once_with("calculadora")
    assert resultado == Respuesta(texto="Abriendo calculadora...", motor=MOTOR_ACCION)


@patch("src.main.abrir_aplicacion")
def test_abrir_app_sin_confirmar_no_ejecuta_nada(mock_abrir):
    resultado = procesar_comando("abre la calculadora", confirmador=lambda descripcion: False)

    mock_abrir.assert_not_called()
    assert resultado.motor == MOTOR_ACCION
    assert "ancel" in resultado.texto.lower()


@patch("src.main.abrir_aplicacion")
def test_motor_forzado_no_impide_abrir_apps(mock_abrir):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo paint...")

    resultado = procesar_comando("abre paint", confirmador=lambda d: True, motor_forzado=MOTOR_GEMINI)

    mock_abrir.assert_called_once_with("paint")
    assert resultado.motor == MOTOR_ACCION
