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


def test_extraer_nombre_app_con_forma_reflexiva():
    assert extraer_nombre_app("ábreme el bloc de notas") == "bloc de notas"
    assert extraer_nombre_app("abreme discord") == "discord"


def test_extraer_nombre_app_no_confunde_palabras_que_contienen_abre():
    """Caso real: ninguna palabra que solo contenga "abre" debe disparar el atajo."""
    assert extraer_nombre_app("recabré todos los datos del proyecto") is None


def test_es_busqueda_web_detecta_palabra_clave():
    assert es_busqueda_web("busca el clima de hoy") is True


def test_es_busqueda_web_sin_palabra_clave():
    assert es_busqueda_web("recuérdame comprar leche") is False


def test_nombre_motor_ollama_es_crimson():
    assert nombre_motor(MOTOR_OLLAMA) == "Crimson"


def test_nombre_motor_gemini_es_clover():
    assert nombre_motor(MOTOR_GEMINI) == "Clover"


def test_nombre_motor_accion_es_crimson():
    """No hay un tercer agente "Jarvis": una acción directa se atribuye a Crimson, el default."""
    assert nombre_motor(MOTOR_ACCION) == "Crimson"


def test_nombre_motor_desconocido_cae_a_crimson():
    assert nombre_motor("algo_raro") == "Crimson"


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


def test_extraer_texto_click_con_dale_click_a():
    assert extraer_texto_click("dale click a enviar") == "enviar"
    assert extraer_texto_click("dale clic a guardar") == "guardar"


def test_extraer_texto_a_escribir_conserva_mayusculas():
    assert extraer_texto_a_escribir("escribe Hola Mundo") == "Hola Mundo"
    assert extraer_texto_a_escribir("teclea mi correo es test@test.com") == "mi correo es test@test.com"


def test_extraer_texto_a_escribir_sin_frase_devuelve_none():
    assert extraer_texto_a_escribir("recuérdame comprar leche") is None


def test_extraer_texto_a_escribir_no_confunde_describe_con_escribe():
    """Caso real: "describe" contiene "escribe" y tecleaba la frase completa en la ventana activa."""
    assert extraer_texto_a_escribir("describe mi proyecto de física") is None
    assert extraer_texto_a_escribir("inscribe a mi hermana al curso") is None


def test_es_click_riesgoso_detecta_palabras_de_riesgo():
    assert es_click_riesgoso("Eliminar") is True
    assert es_click_riesgoso("Confirmar compra") is True
    assert es_click_riesgoso("Enviar") is True


def test_es_click_riesgoso_con_boton_neutro():
    assert es_click_riesgoso("Guardar") is False
    assert es_click_riesgoso("Aceptar") is False


def test_decidir_motor_no_confunde_enviar_con_envia():
    """Caso real: "enviar" contiene "envia" y mandaba comandos simples a Gemini sin razón."""
    assert decidir_motor("dale click a enviar") == MOTOR_OLLAMA


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
