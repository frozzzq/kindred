from unittest.mock import patch

import pytest

from src.actions.system_control import ResultadoAccion
from src.agente.conversacion import Conversacion
from src.engines.modelos import RespuestaMotor
from src.herramientas.catalogo import REGISTRO
from src.main import Respuesta, procesar_comando
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_GEMINI_FALLO, MOTOR_OLLAMA


@pytest.fixture(autouse=True)
def sin_efectos_externos():
    """Evita tocar la bóveda real y arma un prompt de sistema falso predecible."""
    with patch("src.main.evaluar_guardado") as guardado, patch(
        "src.main.construir_prompt_sistema", side_effect=lambda motor, con_herramientas: f"sistema-{motor}"
    ), patch("src.main.registrar_interaccion"), patch("src.main.construir_contexto_web", return_value=""), patch(
        "src.main.aprender_si_quedo_sin_guardar"
    ), patch("src.herramientas.auditoria.escribir_nota"), patch("src.main.reconoce_aplicacion", return_value=True):
        yield guardado
    REGISTRO.modo_seguro = False


@patch("src.main.conversar_ollama")
def test_comando_simple_responde_crimson_con_personalidad_y_herramientas(mock_ollama, sin_efectos_externos):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Tienes tres pendientes.")

    resultado = procesar_comando("¿qué pendientes tengo?")

    assert resultado == Respuesta(texto="Tienes tres pendientes.", motor=MOTOR_OLLAMA)
    mensajes = mock_ollama.call_args.args[0]
    assert mensajes[0] == {"role": "system", "content": "sistema-ollama"}
    assert mensajes[-1] == {"role": "user", "content": "¿qué pendientes tengo?"}
    nombres = {h["function"]["name"] for h in mock_ollama.call_args.kwargs["herramientas"]}
    assert "leer_nota" in nombres
    assert "abrir_aplicacion" not in nombres  # con ellas qwen3:8b dejaba de leer la bóveda
    sin_efectos_externos.assert_called_once_with("¿qué pendientes tengo?", "Tienes tres pendientes.", MOTOR_OLLAMA)


@patch("src.main.conversar_ollama")
def test_crimson_recibe_herramientas_de_sistema_si_pide_abrir_algo(mock_ollama):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Listo.")

    procesar_comando("abre spotify y dime mis pendientes")

    nombres = {h["function"]["name"] for h in mock_ollama.call_args.kwargs["herramientas"]}
    assert {"leer_nota", "abrir_aplicacion"} <= nombres


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


def _no_debe_confirmar(descripcion):
    raise AssertionError(f"no debía pedir confirmación: {descripcion}")


@patch("src.herramientas.catalogo.abrir_aplicacion")
def test_abrir_app_no_pide_confirmacion(mock_abrir):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo Calculator...")

    resultado = procesar_comando("abre la calculadora", confirmador=_no_debe_confirmar)

    mock_abrir.assert_called_once_with("calculadora")
    assert resultado == Respuesta(texto="Abriendo Calculator...", motor=MOTOR_ACCION)


@patch("src.herramientas.catalogo.abrir_aplicacion")
def test_motor_forzado_no_impide_abrir_apps(mock_abrir):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo Paint...")

    resultado = procesar_comando("abre paint", confirmador=_no_debe_confirmar, motor_forzado=MOTOR_GEMINI)

    mock_abrir.assert_called_once_with("paint")
    assert resultado.motor == MOTOR_ACCION


@patch("src.herramientas.catalogo.abrir_carpeta")
def test_abrir_la_carpeta_usa_la_herramienta_de_carpetas(mock_carpeta):
    mock_carpeta.return_value = ResultadoAccion(exito=True, mensaje="Abriendo la carpeta Downloads...")

    procesar_comando("abre la carpeta descargas", confirmador=_no_debe_confirmar)

    mock_carpeta.assert_called_once_with("descargas")


@patch("src.herramientas.catalogo.abrir_url")
def test_abrir_un_dominio_abre_la_pagina(mock_url):
    mock_url.return_value = ResultadoAccion(exito=True, mensaje="Abriendo youtube.com...")

    procesar_comando("abre youtube.com", confirmador=_no_debe_confirmar)

    mock_url.assert_called_once_with("youtube.com")


def test_cerrar_confirmado_marca_la_respuesta_para_cerrar():
    resultado = procesar_comando("ciérrate", confirmador=lambda descripcion: True)

    assert resultado.cerrar is True
    assert resultado.motor == MOTOR_ACCION


def test_cerrar_sin_confirmar_no_marca_nada():
    resultado = procesar_comando("ciérrate", confirmador=lambda descripcion: False)

    assert resultado.cerrar is False
    assert "ancel" in resultado.texto.lower()


@patch("src.main.conversar_ollama")
def test_cerrar_no_llega_a_preguntarle_a_ningun_motor(mock_ollama):
    procesar_comando("cierra la aplicación", confirmador=lambda descripcion: True)

    mock_ollama.assert_not_called()


@patch("src.herramientas.catalogo.escribir_texto")
def test_escribir_no_pide_confirmacion(mock_escribir):
    mock_escribir.return_value = ResultadoAccion(exito=True, mensaje="Listo, ya lo escribí.")

    resultado = procesar_comando("escribe hola mundo", confirmador=_no_debe_confirmar)

    mock_escribir.assert_called_once_with("hola mundo")
    assert resultado == Respuesta(texto="Listo, ya lo escribí.", motor=MOTOR_ACCION)


@patch("src.herramientas.catalogo.hacer_click")
def test_click_en_boton_neutro_no_pide_confirmacion(mock_click):
    mock_click.return_value = ResultadoAccion(exito=True, mensaje="Hice click en 'Guardar'.")

    resultado = procesar_comando("haz click en Guardar", confirmador=_no_debe_confirmar)

    mock_click.assert_called_once_with("guardar")
    assert resultado.texto == "Hice click en 'Guardar'."


@patch("src.herramientas.catalogo.hacer_click")
def test_click_en_boton_riesgoso_confirmado_ejecuta(mock_click):
    mock_click.return_value = ResultadoAccion(exito=True, mensaje="Hice click en 'Eliminar'.")
    preguntas = []

    resultado = procesar_comando("haz click en Eliminar", confirmador=lambda d: preguntas.append(d) or True)

    assert preguntas == ["¿Confirmas que haga click en 'eliminar'?"]
    mock_click.assert_called_once_with("eliminar")
    assert resultado.texto == "Hice click en 'Eliminar'."


@patch("src.herramientas.catalogo.hacer_click")
def test_click_en_boton_riesgoso_sin_confirmar_no_ejecuta(mock_click):
    resultado = procesar_comando("haz click en Eliminar", confirmador=lambda d: False)

    mock_click.assert_not_called()
    assert "ancel" in resultado.texto.lower()


# --- modo seguro ---


@patch("src.herramientas.catalogo.abrir_aplicacion")
def test_modo_seguro_bloquea_acciones_hasta_salir(mock_abrir):
    mock_abrir.return_value = ResultadoAccion(exito=True, mensaje="Abriendo Paint...")

    procesar_comando("Jarvis, modo seguro")
    bloqueada = procesar_comando("abre paint", confirmador=_no_debe_confirmar)
    procesar_comando("sal del modo seguro")
    permitida = procesar_comando("abre paint", confirmador=_no_debe_confirmar)

    assert "modo seguro" in bloqueada.texto.lower()
    assert permitida.texto == "Abriendo Paint..."
    mock_abrir.assert_called_once_with("paint")


@patch("src.main.conversar_ollama")
def test_modo_seguro_no_le_quita_la_lectura_al_agente(mock_ollama):
    """Las herramientas de lectura siguen llegándole al modelo: solo se bloquean al ejecutar acciones."""
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Tienes dos pendientes.")
    procesar_comando("modo seguro")

    procesar_comando("¿qué pendientes tengo?")

    ejecutar = mock_ollama.call_args.kwargs["ejecutar"]
    assert "modo seguro" in ejecutar("agregar_pendiente", {"tarea": "algo"}).lower()


# --- Clover con herramientas ---


@patch("src.main.conversar_ollama")
@patch("src.main.conversar_gemini")
def test_clover_usa_herramientas_en_comandos_normales(mock_conversar_gemini, mock_ollama):
    mock_conversar_gemini.return_value = RespuestaMotor(
        exito=True, texto="Listo, abrí Spotify.", herramientas_usadas=["abrir_aplicacion"]
    )

    resultado = procesar_comando("pon música en spotify", motor_forzado=MOTOR_GEMINI)

    mock_ollama.assert_not_called()
    nombres = {h["name"] for h in mock_conversar_gemini.call_args.kwargs["herramientas"]}
    assert {"abrir_aplicacion", "leer_nota"} <= nombres
    assert resultado == Respuesta(texto="Listo, abrí Spotify.", motor=MOTOR_GEMINI)


@patch("src.main.conversar_ollama")
@patch("src.main.conversar_gemini")
def test_si_clover_falla_despues_de_actuar_no_se_repite_con_ollama(mock_conversar_gemini, mock_ollama):
    mock_conversar_gemini.return_value = RespuestaMotor(
        exito=False, error="se cortó la conexión", herramientas_usadas=["abrir_aplicacion"]
    )

    resultado = procesar_comando("pon mi playlist favorita en spotify", motor_forzado=MOTOR_GEMINI)

    mock_ollama.assert_not_called()
    assert "abrir_aplicacion" in resultado.texto


@patch("src.main.conversar_ollama")
@patch("src.main.conversar_gemini")
def test_si_clover_falla_sin_actuar_cae_a_ollama(mock_conversar_gemini, mock_ollama):
    mock_conversar_gemini.return_value = RespuestaMotor(exito=False, error="sin cuota")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="respuesta de crimson")

    resultado = procesar_comando("recuérdame comprar leche", motor_forzado=MOTOR_GEMINI)

    assert resultado.motor == MOTOR_OLLAMA


@patch("src.herramientas.catalogo.abrir_aplicacion")
@patch("src.main.conversar_ollama")
def test_abrir_con_varias_instrucciones_lo_resuelve_el_agente(mock_ollama, mock_abrir):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Listo.")

    procesar_comando("abre spotify y pon mi playlist")

    mock_abrir.assert_not_called()  # no la trató como una app llamada "spotify y pon mi playlist"
    mock_ollama.assert_called_once()


@patch("src.herramientas.catalogo.abrir_aplicacion")
@patch("src.main.conversar_ollama")
def test_abrir_algo_que_no_es_una_app_lo_resuelve_el_agente(mock_ollama, mock_abrir):
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Tienes dos pendientes.")

    with patch("src.main.reconoce_aplicacion", return_value=False):
        resultado = procesar_comando("abre mis pendientes")

    mock_abrir.assert_not_called()
    assert resultado.texto == "Tienes dos pendientes."
