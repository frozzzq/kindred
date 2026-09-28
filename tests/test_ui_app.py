import asyncio
import threading
from unittest.mock import MagicMock, patch

from src.main import Respuesta
from src.obsidian.grafo import Grafo, Nodo
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA
from src.ui.app import AGENTES, JarvisApp


def test_ya_no_existe_el_modo_automatico_de_jarvis():
    assert MOTOR_ACCION not in AGENTES
    assert set(AGENTES) == {MOTOR_OLLAMA, MOTOR_GEMINI}


def test_accion_se_atribuye_al_agente_seleccionado():
    app = JarvisApp(MagicMock())
    app.agente = MOTOR_OLLAMA

    assert app._motor_mostrado(MOTOR_ACCION) == MOTOR_OLLAMA


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


def test_es_su_propio_eco_cuando_no_esta_hablando():
    app = JarvisApp(MagicMock())

    assert app._es_su_propio_eco("cualquier cosa") is False


def test_es_su_propio_eco_con_texto_identico():
    app = JarvisApp(MagicMock())
    app._texto_hablando = "Tienes tres pendientes para hoy."

    assert app._es_su_propio_eco("tienes tres pendientes para hoy") is True


def test_es_su_propio_eco_con_texto_no_relacionado():
    app = JarvisApp(MagicMock())
    app._texto_hablando = "Tienes tres pendientes para hoy."

    assert app._es_su_propio_eco("abre la calculadora") is False


def test_es_su_propio_eco_con_una_sola_oracion_de_una_respuesta_larga():
    """Caso real: el micrófono capta solo una oración suelta de una respuesta con varias.

    Con un ratio() normal esto daba una similitud de 0.3-0.4 (por la diferencia de longitud
    entre la oración oída y la respuesta completa) y no se detectaba como eco.
    """
    app = JarvisApp(MagicMock())
    app._texto_hablando = (
        "Tienes tres pendientes para hoy. Llamar al dentista para agendar tu limpieza. "
        "Entregar el reporte de física antes de las cinco. Y comprar croquetas para el perro."
    )

    assert app._es_su_propio_eco("Tienes tres pendientes para hoy.") is True
    assert app._es_su_propio_eco("Llamar al dentista para agendar tu limpieza.") is True
    assert app._es_su_propio_eco("y comprar croquetas para el perro.") is True
    # con un error de transcripción ("cinto" en vez de "cinco") sigue reconociéndose
    assert app._es_su_propio_eco("Entregar el reporte de física antes de la cinto.") is True


def test_interrupcion_real_no_se_confunde_con_eco_de_respuesta_larga():
    app = JarvisApp(MagicMock())
    app._texto_hablando = (
        "Tienes tres pendientes para hoy. Llamar al dentista para agendar tu limpieza. "
        "Entregar el reporte de física antes de las cinco. Y comprar croquetas para el perro."
    )

    assert app._es_su_propio_eco("no espera, mejor dime el clima") is False
    assert app._es_su_propio_eco("olvida eso, mejor dime la hora") is False


def test_frase_parecida_a_lo_que_dice_se_ignora_como_eco():
    """Sin cancelación de eco de hardware: si se parece a lo que está diciendo, se asume su propio eco."""
    app, patcher = _app_escuchando("tienes tres pendientes para hoy")
    app._texto_hablando = "Tienes tres pendientes para hoy."
    app._turno.acquire()  # simula un turno ya en curso
    try:
        app._al_escuchar_frase(audio=None)
    finally:
        app._turno.release()
        patcher.stop()

    app._atender_voz.assert_not_called()
    assert not app._interrumpir.is_set()


def test_cualquier_frase_distinta_con_turno_en_curso_lo_interrumpe():
    """Ya no hace falta decir su nombre para interrumpirlo: basta con que no suene a su propio eco."""
    app, patcher = _app_escuchando("olvida eso, mejor dime la hora")
    app._texto_hablando = "Tienes tres pendientes para hoy."
    app.ventana.agente = MOTOR_OLLAMA
    app.ventana.extender()  # simula que la ventana de conversación ya estaba abierta
    app._turno.acquire()  # simula un turno ya en curso (el agente está "hablando")
    try:
        hilo = threading.Thread(target=app._al_escuchar_frase, args=(None,), daemon=True)
        hilo.start()
        hilo.join(timeout=0.2)

        assert hilo.is_alive()  # sigue esperando a que se libere el turno interrumpido
        assert app._interrumpir.is_set()  # pero ya marcó la interrupción de inmediato
        app._atender_voz.assert_not_called()  # todavía no: falta que se libere el turno

        app._turno.release()
        hilo.join(timeout=1)

        assert not hilo.is_alive()
    finally:
        patcher.stop()

    app._atender_voz.assert_called_once_with("olvida eso, mejor dime la hora")


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


def test_elegir_agente_cambia_el_color_del_grafo():
    app = JarvisApp(MagicMock())

    app._seleccionar_agente(MOTOR_GEMINI)

    assert app.grafo.motor == MOTOR_GEMINI


@patch("src.ui.app.construir_grafo")
@patch("src.ui.app.firma_boveda")
def test_el_grafo_se_rehace_solo_cuando_cambia_la_boveda(mock_firma, mock_construir):
    app = JarvisApp(MagicMock())
    mock_construir.return_value = Grafo(nodos=(Nodo("Nota.md", "Nota", False),), aristas=())

    mock_firma.return_value = (("Nota.md", 1),)
    asyncio.run(app._revisar_boveda())
    asyncio.run(app._revisar_boveda())  # sin cambios
    mock_firma.return_value = (("Nota.md", 2),)  # se editó la nota
    asyncio.run(app._revisar_boveda())

    assert mock_construir.call_count == 2
    assert [e.value for e in app.grafo._etiquetas] == ["Nota"]


@patch("src.ui.app.firma_boveda", side_effect=RuntimeError("OBSIDIAN_VAULT_PATH no está configurada"))
def test_sin_boveda_configurada_el_grafo_queda_vacio_sin_fallar(_mock_firma):
    app = JarvisApp(MagicMock())

    asyncio.run(app._revisar_boveda())

    assert app.grafo._nucleos == []


# --- interrupción ---


def test_tocar_microfono_mientras_ocupado_interrumpe_y_empieza_a_grabar():
    app = JarvisApp(MagicMock())
    app.grabadora = MagicMock(grabando=False)
    app.escucha = MagicMock()
    app.ocupado = True

    app.tocar_microfono(None)

    assert app._interrumpir.is_set()
    app.escucha.pausar.assert_called_once()
    app.grabadora.iniciar.assert_called_once()


def test_tocar_microfono_sin_estar_ocupado_no_marca_interrupcion():
    app = JarvisApp(MagicMock())
    app.grabadora = MagicMock(grabando=False)
    app.escucha = MagicMock()

    app.tocar_microfono(None)

    assert not app._interrumpir.is_set()
    app.grabadora.iniciar.assert_called_once()


# --- cerrar la aplicación ---


@patch("src.ui.app.hablar")
@patch("src.ui.app.procesar_comando")
def test_atender_voz_cierra_la_ventana_si_la_respuesta_lo_pide(mock_procesar, _mock_hablar):
    app = JarvisApp(MagicMock())
    mock_procesar.return_value = Respuesta(texto="Hasta luego.", motor=MOTOR_ACCION, cerrar=True)

    app._atender_voz("ciérrate")

    app.page.run_task.assert_called_once_with(app.page.window.close)


@patch("src.ui.app.procesar_comando")
def test_atender_voz_no_cierra_la_ventana_si_no_se_lo_piden(mock_procesar):
    app = JarvisApp(MagicMock())
    mock_procesar.return_value = Respuesta(texto="ok", motor=MOTOR_OLLAMA, cerrar=False)

    with patch("src.ui.app.hablar"):
        app._atender_voz("hola")

    app.page.run_task.assert_not_called()


@patch("src.ui.app.procesar_comando")
def test_procesar_chat_cierra_la_ventana_si_la_respuesta_lo_pide(mock_procesar):
    app = JarvisApp(MagicMock())
    mock_procesar.return_value = Respuesta(texto="Hasta luego.", motor=MOTOR_ACCION, cerrar=True)

    app._procesar_chat("ciérrate")

    app.page.run_task.assert_called_once_with(app.page.window.close)
