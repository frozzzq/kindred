from src.router.intent_router import (
    MOTOR_GEMINI,
    MOTOR_OLLAMA,
    decidir_motor,
    es_busqueda_web,
    extraer_nombre_app,
)


def test_comando_simple_va_a_ollama():
    assert decidir_motor("recuérdame comprar leche") == MOTOR_OLLAMA


def test_comando_complejo_va_a_gemini():
    assert decidir_motor("busca en internet el clima de hoy") == MOTOR_GEMINI


def test_es_insensible_a_mayusculas():
    assert decidir_motor("BUSCA en internet el clima") == MOTOR_GEMINI


def test_extraer_nombre_app_con_prefijo_abre():
    assert extraer_nombre_app("abre la calculadora") == "calculadora"


def test_extraer_nombre_app_con_prefijo_abrir():
    assert extraer_nombre_app("Abrir Chrome") == "chrome"


def test_extraer_nombre_app_sin_prefijo_devuelve_none():
    assert extraer_nombre_app("recuérdame comprar leche") is None


def test_extraer_nombre_app_quita_puntuacion_de_whisper():
    assert extraer_nombre_app("Abre la calculadora.") == "calculadora"
    assert extraer_nombre_app("¡Abre paint!") == "paint"


def test_es_busqueda_web_detecta_palabra_clave():
    assert es_busqueda_web("busca el clima de hoy") is True


def test_es_busqueda_web_sin_palabra_clave():
    assert es_busqueda_web("recuérdame comprar leche") is False
