from datetime import datetime

import pytest

from src import ajustes
from src.agente.personalidad import construir_prompt_sistema, es_muletilla, nombre_usuario, quitar_muletilla_final
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("He agregado el pendiente. ¿Necesitas algo más?", "He agregado el pendiente."),
        ("Completé la tarea. ¿Hay algo más que necesites hacer?", "Completé la tarea."),
        ("Tienes tres pendientes. ¿Necesitas ayuda con alguno en específico?", "Tienes tres pendientes."),
        ("Soy Crimson. ¿En qué puedo ayudarte?", "Soy Crimson. ¿En qué puedo ayudarte?"),
        ("¿Qué tarea quieres agregar?", "¿Qué tarea quieres agregar?"),
        ("¿Necesitas algo más?", "¿Necesitas algo más?"),  # no deja la respuesta vacía
        ("El inner join cruza ambas tablas. ¿Quieres que te lo explique mejor?", "El inner join cruza ambas tablas."),
        ("Tienes dos pendientes. ¿Te gustaría saber más de alguno?", "Tienes dos pendientes."),
        # una pregunta con contenido real se respeta
        ("No lo tienes anotado. ¿Quieres que lo agregue a tus pendientes?", "No lo tienes anotado. ¿Quieres que lo agregue a tus pendientes?"),
    ],
)
def test_quitar_muletilla_final(texto, esperado):
    assert quitar_muletilla_final(texto) == esperado


def _boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text(
        "- Se llama Josue (2026-09-24)\n- Le gusta el café (2026-09-28)", encoding="utf-8"
    )
    (tmp_path / "01-Perfil" / "Contactos.md").write_text("- **Camila**: su novia", encoding="utf-8")
    (tmp_path / "02-Tareas").mkdir()
    (tmp_path / "02-Tareas" / "Pendientes.md").write_text("- [ ] Comprar pan", encoding="utf-8")
    (tmp_path / "04-Conocimiento" / "Programación").mkdir(parents=True)
    (tmp_path / "04-Conocimiento" / "Programación" / "Node.js.md").write_text("node", encoding="utf-8")
    (tmp_path / "03-Proyectos").mkdir()
    (tmp_path / "03-Proyectos" / "Jarvis.md").write_text("jarvis", encoding="utf-8")


def test_crimson_se_presenta_con_su_nombre_y_personalidad(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)

    assert prompt.startswith("Eres Crimson, la asistente personal de Josue.")
    assert "alegre" in prompt and "mexicana" in prompt and "Clover" in prompt
    assert "Hablas de ti en femenino" in prompt


def test_clover_tiene_otra_personalidad(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False)

    assert prompt.startswith("Eres Clover, el asistente personal de Josue.")
    assert "humor seco" in prompt and "Hablas de ti en masculino" in prompt


def test_el_genero_sigue_a_la_voz_elegida(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)
    ajustes.guardar({"voz_gemini": "en-US-AvaMultilingualNeural"})

    assert construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=True).startswith("Eres Clover, la asistente")


def test_incluye_perfil_contactos_y_estructura_sin_fechas(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)

    assert "Le gusta el café" in prompt and "(2026-09-28)" not in prompt
    assert "Camila" in prompt
    assert "Áreas de conocimiento que ya existen: Programación." in prompt
    assert "Proyectos: Jarvis." in prompt


def test_el_prompt_es_estable_entre_turnos(tmp_path, monkeypatch):
    """Sin hora ni pendientes: así Ollama reutiliza de caché el prompt y el historial (1.7 s → 0.06 s)."""
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)

    assert "Comprar pan" not in prompt
    assert datetime.now().strftime("%H:%M") not in prompt
    assert prompt == construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)


def test_funciona_sin_boveda_configurada(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)

    assert prompt.startswith("Eres Crimson, la asistente personal del usuario.")


def test_nombre_usuario_del_perfil(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    assert nombre_usuario() == "Josue"


@pytest.mark.parametrize("oracion, esperado", [("¿Necesitas algo más?", True), ("¿Quieres que lo agregue?", False)])
def test_es_muletilla(oracion, esperado):
    assert es_muletilla(oracion) is esperado
