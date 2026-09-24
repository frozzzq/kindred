from src.agente.conversacion import Conversacion


def test_guarda_los_turnos_en_orden():
    conversacion = Conversacion()

    conversacion.agregar_turno("hola", "hola, ¿qué tal?")

    assert conversacion.mensajes() == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "hola, ¿qué tal?"},
    ]


def test_solo_conserva_los_ultimos_mensajes():
    conversacion = Conversacion(max_mensajes=4)

    for i in range(5):
        conversacion.agregar_turno(f"pregunta {i}", f"respuesta {i}")

    mensajes = conversacion.mensajes()
    assert len(mensajes) == 4
    assert mensajes[0]["content"] == "pregunta 3"


def test_transcripcion_para_motores_sin_historial():
    conversacion = Conversacion()
    conversacion.agregar_turno("¿cuántos pendientes tengo?", "Tienes tres.")

    assert conversacion.como_transcripcion() == "Usuario: ¿cuántos pendientes tengo?\nTú: Tienes tres."
