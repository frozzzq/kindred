from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA, decidir_motor


def test_comando_simple_va_a_ollama():
    assert decidir_motor("recuérdame comprar leche") == MOTOR_OLLAMA


def test_comando_complejo_va_a_gemini():
    assert decidir_motor("busca en internet el clima de hoy") == MOTOR_GEMINI


def test_es_insensible_a_mayusculas():
    assert decidir_motor("ABRE la calculadora") == MOTOR_GEMINI
