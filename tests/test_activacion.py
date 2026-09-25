import pytest

from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA
from src.voice.activacion import VentanaConversacion, detectar_nombre


@pytest.mark.parametrize(
    "texto, motor, resto",
    [
        ("Crimson, ¿qué pendientes tengo?", MOTOR_OLLAMA, "¿qué pendientes tengo?"),
        ("Oye Crimson, abre la calculadora", MOTOR_OLLAMA, "abre la calculadora"),
        ("¿Qué hora es, Crimson?", MOTOR_OLLAMA, "¿Qué hora es?"),
        ("Crimson.", MOTOR_OLLAMA, ""),
        ("Hey Crimson", MOTOR_OLLAMA, ""),
        ("Hola Crimson", MOTOR_OLLAMA, "Hola"),
        ("Clover, resume esto", MOTOR_GEMINI, "resume esto"),
        ("Hola Yervis, ¿cómo estás?", MOTOR_ACCION, "Hola, ¿cómo estás?"),  # así lo transcribió Whisper
        ("Grimson, ¿estás ahí?", MOTOR_OLLAMA, "¿estás ahí?"),  # error típico de transcripción
    ],
)
def test_detecta_el_nombre_y_limpia_el_mensaje(texto, motor, resto):
    assert detectar_nombre(texto) == (motor, resto)


@pytest.mark.parametrize("texto", ["¿Qué hora es?", "El crimen no paga", "Mañana compro pan"])
def test_sin_nombre_no_activa(texto):
    assert detectar_nombre(texto)[0] is None


class RelojFalso:
    def __init__(self):
        self.ahora = 1000.0

    def __call__(self):
        return self.ahora


def test_sin_llamarlo_por_su_nombre_se_ignora():
    ventana = VentanaConversacion(reloj=RelojFalso())

    assert ventana.procesar("¿qué pendientes tengo?") == (None, None)


def test_llamarlo_abre_la_ventana_y_ya_no_hace_falta_el_nombre():
    reloj = RelojFalso()
    ventana = VentanaConversacion(duracion=60, reloj=reloj)

    assert ventana.procesar("Crimson") == (MOTOR_OLLAMA, "")
    reloj.ahora += 30
    assert ventana.procesar("¿qué pendientes tengo?") == (MOTOR_OLLAMA, "¿qué pendientes tengo?")


def test_cada_frase_reinicia_el_minuto():
    reloj = RelojFalso()
    ventana = VentanaConversacion(duracion=60, reloj=reloj)
    ventana.procesar("Crimson, hola")

    reloj.ahora += 50
    ventana.procesar("sigo hablando")
    reloj.ahora += 50  # 100 s desde que lo llamó, pero solo 50 desde la última frase

    assert ventana.procesar("¿me escuchas?") == (MOTOR_OLLAMA, "¿me escuchas?")


def test_tras_un_minuto_de_silencio_hay_que_volver_a_llamarlo():
    reloj = RelojFalso()
    ventana = VentanaConversacion(duracion=60, reloj=reloj)
    ventana.procesar("Crimson, hola")

    reloj.ahora += 61

    assert ventana.abierta is False
    assert ventana.procesar("¿qué pendientes tengo?") == (None, None)


def test_decir_otro_nombre_le_pasa_la_palabra():
    ventana = VentanaConversacion(reloj=RelojFalso())
    ventana.procesar("Crimson, hola")

    assert ventana.procesar("Clover, ¿qué opinas?") == (MOTOR_GEMINI, "¿qué opinas?")
    assert ventana.procesar("y luego qué") == (MOTOR_GEMINI, "y luego qué")
