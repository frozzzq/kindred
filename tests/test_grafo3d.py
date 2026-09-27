import numpy as np

from src.obsidian.grafo import Arista, Grafo, Nodo
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA
from src.ui.grafo3d import GrafoAgente, proyectar
from src.ui.paletas import PALETAS

CUADRO = 1 / 30

GRAFO = Grafo(
    nodos=(Nodo("01-Perfil", "01-Perfil", True), Nodo("01-Perfil/Yo.md", "Yo", False), Nodo("01-Perfil/Contactos.md", "Contactos", False)),
    aristas=(
        Arista("01-Perfil", "01-Perfil/Yo.md", False),
        Arista("01-Perfil", "01-Perfil/Contactos.md", False),
        Arista("01-Perfil/Yo.md", "01-Perfil/Contactos.md", True),
    ),
)


def _agente(motor=MOTOR_ACCION):
    agente = GrafoAgente(motor)
    agente.mostrar_grafo(GRAFO)
    return agente


def _color_de_halo(agente):
    return agente._halos[0].paint.gradient.colors[0].lower()


def _radio_de_halo_con_voz(nivel_voz):
    agente = _agente()
    agente.empezar_a_hablar(MOTOR_ACCION)
    for _ in range(30):
        agente.avanzar(CUADRO, nivel_voz)
    return agente._halos[0].radius


def test_dibuja_una_linea_por_conexion_y_un_nodo_por_nota():
    agente = _agente()

    assert len(agente._lineas) == 3
    assert len(agente._nucleos) == 3
    assert [e.value for e in agente._etiquetas] == ["01-Perfil", "Yo", "Contactos"]


def test_toma_el_color_del_agente_elegido():
    agente = _agente(MOTOR_ACCION)

    agente.cambiar_agente(MOTOR_GEMINI)
    agente.avanzar(2.0, 0.0)  # la transición de color ya terminó

    assert _color_de_halo(agente).startswith(PALETAS[MOTOR_GEMINI].principal.lower())


def test_al_hablar_toma_el_color_de_quien_habla_y_luego_vuelve():
    agente = _agente(MOTOR_ACCION)

    agente.empezar_a_hablar(MOTOR_OLLAMA)
    agente.avanzar(2.0, 0.0)
    color_hablando = _color_de_halo(agente)
    agente.dejar_de_hablar()
    agente.avanzar(2.0, 0.0)

    assert color_hablando.startswith(PALETAS[MOTOR_OLLAMA].principal.lower())
    assert _color_de_halo(agente).startswith(PALETAS[MOTOR_ACCION].principal.lower())


def test_el_brillo_sigue_el_volumen_de_la_voz():
    """No es un parpadeo de encendido/apagado: más volumen, más luz."""
    silencio, suave, fuerte = (_radio_de_halo_con_voz(v) for v in (0.0, 0.3, 0.9))

    assert silencio < suave < fuerte


def test_el_brillo_baja_suave_cuando_la_voz_se_calla():
    agente = _agente()
    for _ in range(30):
        agente.avanzar(CUADRO, 1.0)
    nivel_hablando = agente.nivel

    agente.avanzar(CUADRO, 0.0)

    assert nivel_hablando * 0.5 < agente.nivel < nivel_hablando


def test_gira_con_el_tiempo():
    agente = _agente()
    antes = (agente._nucleos[1].x, agente._nucleos[1].y)

    for _ in range(60):
        agente.avanzar(CUADRO, 0.0)

    assert (agente._nucleos[1].x, agente._nucleos[1].y) != antes


def test_una_nota_nueva_no_mueve_de_golpe_a_las_que_ya_estaban():
    agente = _agente()
    posiciones = dict(zip(agente.disposicion.ids, agente.disposicion.pos.copy()))

    nueva = Nodo("01-Perfil/Patrones.md", "Patrones", False)
    agente.mostrar_grafo(Grafo(GRAFO.nodos + (nueva,), GRAFO.aristas + (Arista("01-Perfil", nueva.id, False),)))

    for id_, pos in posiciones.items():
        assert np.allclose(agente.disposicion.pos[agente.disposicion.ids.index(id_)], pos)
    assert len(agente._nucleos) == 4


def test_boveda_vacia_no_falla():
    agente = GrafoAgente(MOTOR_ACCION)
    agente.mostrar_grafo(Grafo((), ()))

    agente.avanzar(CUADRO, 0.5)

    assert agente.control.shapes == [agente._aura]


def test_proyectar_lo_cercano_se_ve_mas_grande():
    puntos = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 0.0, 1.0]])

    x, y, perspectiva, profundidad = proyectar(puntos, angulo=0.0)

    assert (x[0], y[0]) == (0.0, 0.0)
    assert perspectiva[1] > perspectiva[0] > perspectiva[2]
    assert profundidad[1] < profundidad[2]
