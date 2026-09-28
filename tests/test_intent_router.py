from src.router.intent_router import (
    MOTOR_ACCION,
    MOTOR_GEMINI,
    MOTOR_OLLAMA,
    cambio_de_modo_seguro,
    decidir_motor,
    es_busqueda_web,
    es_cierre,
    es_click_riesgoso,
    extraer_nombre_app,
    extraer_texto_a_escribir,
    extraer_texto_click,
    nombre_motor,
    parece_varias_instrucciones,
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


def test_extraer_nombre_app_con_saludo_antes():
    assert extraer_nombre_app("Hey Crimson, abre calculadora.") == "calculadora"
    assert extraer_nombre_app("Oye Clover, podrías abrir spotify") == "spotify"


def test_es_busqueda_web_detecta_palabra_clave():
    assert es_busqueda_web("busca el clima de hoy") is True


def test_es_busqueda_web_sin_palabra_clave():
    assert es_busqueda_web("recuérdame comprar leche") is False


def test_nombre_motor_ollama_es_crimson():
    assert nombre_motor(MOTOR_OLLAMA) == "Crimson"


def test_nombre_motor_gemini_es_clover():
    assert nombre_motor(MOTOR_GEMINI) == "Clover"


def test_nombre_motor_accion_es_jarvis():
    assert nombre_motor(MOTOR_ACCION) == "Jarvis"


def test_nombre_motor_desconocido_cae_a_jarvis():
    assert nombre_motor("algo_raro") == "Jarvis"


def test_es_cierre_detecta_frases_para_cerrar():
    assert es_cierre("ciérrate") is True
    assert es_cierre("Cierra la aplicación, por favor") is True
    assert es_cierre("apágate") is True


def test_es_cierre_sin_frase_de_cierre():
    assert es_cierre("recuérdame comprar leche") is False
    assert es_cierre("no cierres nada") is False


def test_extraer_texto_click_con_varias_frases():
    assert extraer_texto_click("haz click en Guardar") == "guardar"
    assert extraer_texto_click("Clic en Aceptar") == "aceptar"
    assert extraer_texto_click("presiona el botón Enviar.") == "enviar"


def test_extraer_texto_click_sin_frase_devuelve_none():
    assert extraer_texto_click("recuérdame comprar leche") is None


def test_extraer_texto_a_escribir_conserva_mayusculas():
    assert extraer_texto_a_escribir("escribe Hola Mundo") == "Hola Mundo"
    assert extraer_texto_a_escribir("teclea mi correo es test@test.com") == "mi correo es test@test.com"


def test_extraer_texto_a_escribir_sin_frase_devuelve_none():
    assert extraer_texto_a_escribir("recuérdame comprar leche") is None


def test_es_click_riesgoso_detecta_palabras_de_riesgo():
    assert es_click_riesgoso("Eliminar") is True
    assert es_click_riesgoso("Confirmar compra") is True
    assert es_click_riesgoso("Enviar") is True


def test_es_click_riesgoso_con_boton_neutro():
    assert es_click_riesgoso("Guardar") is False
    assert es_click_riesgoso("Aceptar") is False


def test_cambio_de_modo_seguro():
    assert cambio_de_modo_seguro("Jarvis, modo seguro") is True
    assert cambio_de_modo_seguro("activa el modo seguro") is True
    assert cambio_de_modo_seguro("sal del modo seguro") is False
    assert cambio_de_modo_seguro("desactiva el modo seguro, por favor") is False
    assert cambio_de_modo_seguro("abre spotify") is None


def test_parece_varias_instrucciones():
    assert parece_varias_instrucciones("spotify y pon mi playlist") is True
    assert parece_varias_instrucciones("chrome, luego busca vuelos") is True
    assert parece_varias_instrucciones("visual studio code") is False
    assert parece_varias_instrucciones("paint") is False
