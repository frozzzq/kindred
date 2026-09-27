import threading
from unittest.mock import MagicMock, patch

from src.main import Respuesta
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA
from src.ui.app import PALETAS, JarvisApp, Orbe


def test_orbe_usa_el_color_del_agente_elegido():
    orbe = Orbe(MOTOR_ACCION)

    orbe.cambiar_agente(MOTOR_GEMINI)

    assert PALETAS[MOTOR_GEMINI].principal in orbe.control.gradient.colors


def test_orbe_brilla_con_el_color_de_quien_habla():
    orbe = Orbe(MOTOR_ACCION)
    brillo_en_reposo = orbe.control.shadow.blur_radius

    orbe.empezar_a_hablar(MOTOR_OLLAMA)

    assert PALETAS[MOTOR_OLLAMA].principal in orbe.control.gradient.colors
    assert orbe.control.shadow.blur_radius > brillo_en_reposo


def test_orbe_vuelve_al_agente_elegido_al_dejar_de_hablar():
    orbe = Orbe(MOTOR_ACCION)
    orbe.empezar_a_hablar(MOTOR_OLLAMA)

    orbe.dejar_de_hablar()

    assert PALETAS[MOTOR_ACCION].principal in orbe.control.gradient.colors


def test_orbe_latido_alterna_la_escala():
    orbe = Orbe(MOTOR_ACCION)

    orbe.latido()
    escala_1 = orbe.control.scale
    orbe.latido()
    escala_2 = orbe.control.scale

    assert escala_1 != escala_2


def test_orbe_anima_mas_rapido_al_hablar():
    orbe = Orbe(MOTOR_ACCION)
    intervalo_reposo = orbe.intervalo

    orbe.empezar_a_hablar(MOTOR_GEMINI)

    assert orbe.intervalo < intervalo_reposo


def test_accion_se_atribuye_al_agente_seleccionado():
    app = JarvisApp(MagicMock())
    app.agente = MOTOR_OLLAMA

    assert app._motor_mostrado(MOTOR_ACCION) == MOTOR_OLLAMA


def test_accion_se_queda_como_jarvis_en_modo_automatico():
    app = JarvisApp(MagicMock())
    app.agente = MOTOR_ACCION

    assert app._motor_mostrado(MOTOR_ACCION) == MOTOR_ACCION


def _app_escuchando(transcripcion):
    app = JarvisApp(MagicMock())
    app._atender_voz = MagicMock()
    patcher = patch("src.ui.app.transcribir", return_value=transcripcion)
    patcher.start()
    return app, patcher


def test_frase_sin_nombre_con_ventana_cerrada_se_ignora():
    app, patcher = _app_escuchando("¿qué hora es?")
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        patcher.stop()

    app._atender_voz.assert_not_called()


def test_llamar_a_crimson_lo_selecciona_y_le_pasa_el_mensaje():
    app, patcher = _app_escuchando("Crimson, ¿qué pendientes tengo?")
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        patcher.stop()

    assert app.agente == MOTOR_OLLAMA
    assert app.selector.selected == [MOTOR_OLLAMA]
    app._atender_voz.assert_called_once_with("¿qué pendientes tengo?")


def test_solo_el_nombre_abre_la_ventana_sin_responder():
    app, patcher = _app_escuchando("Clover")
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        patcher.stop()

    assert app.agente == MOTOR_GEMINI
    assert app.ventana.abierta
    app._atender_voz.assert_not_called()


def test_mientras_hay_un_turno_en_curso_no_atiende_frases():
    app, patcher = _app_escuchando("Crimson, hola")
    app._turno.acquire()  # simula un turno ya en curso
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        app._turno.release()
        patcher.stop()

    app._atender_voz.assert_not_called()


def test_mientras_graba_por_microfono_manual_no_atiende_frases():
    app, patcher = _app_escuchando("Crimson, hola")
    app.grabadora = MagicMock(grabando=True)
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        patcher.stop()

    app._atender_voz.assert_not_called()


def test_respuesta_normal_de_motor_no_se_reasigna():
    app = JarvisApp(MagicMock())
    app.agente = MOTOR_GEMINI

    assert app._motor_mostrado(MOTOR_OLLAMA) == MOTOR_OLLAMA


@patch("src.ui.app.procesar_comando")
def test_procesar_chat_espera_si_hay_un_turno_de_voz_en_curso(mock_procesar):
    app = JarvisApp(MagicMock())
    app._turno.acquire()
    mock_procesar.return_value = Respuesta(texto="ok", motor=MOTOR_ACCION)

    hilo = threading.Thread(target=app._procesar_chat, args=("hola",), daemon=True)
    hilo.start()
    hilo.join(timeout=0.2)

    assert hilo.is_alive()  # sigue esperando el lock
    mock_procesar.assert_not_called()  # aún no llegó a procesar

    app._turno.release()
    hilo.join(timeout=1)

    assert not hilo.is_alive()  # ya terminó
    mock_procesar.assert_called_once()


@patch("src.ui.app.procesar_comando")
def test_procesar_chat_marca_ocupado_mientras_responde(mock_procesar):
    app = JarvisApp(MagicMock())
    estados = []

    def capturar(*a, **k):
        estados.append(app.ocupado)
        return Respuesta(texto="ok", motor=MOTOR_ACCION)

    mock_procesar.side_effect = capturar

    app._procesar_chat("hola")

    assert estados == [True]
    assert app.ocupado is False
