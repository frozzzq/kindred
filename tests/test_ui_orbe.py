from unittest.mock import MagicMock

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


def test_respuesta_normal_de_motor_no_se_reasigna():
    app = JarvisApp(MagicMock())
    app.agente = MOTOR_GEMINI

    assert app._motor_mostrado(MOTOR_OLLAMA) == MOTOR_OLLAMA
