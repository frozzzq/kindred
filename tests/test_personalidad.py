from datetime import datetime

import pytest

from src.agente.personalidad import construir_prompt_sistema, quitar_muletilla_final


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("He agregado el pendiente. ¿Necesitas algo más?", "He agregado el pendiente."),
        ("Completé la tarea. ¿Hay algo más que necesites hacer?", "Completé la tarea."),
        ("Tienes tres pendientes. ¿Necesitas ayuda con alguno en específico?", "Tienes tres pendientes."),
        ("Soy Crimson. ¿En qué puedo ayudarte?", "Soy Crimson. ¿En qué puedo ayudarte?"),
        ("¿Qué tarea quieres agregar?", "¿Qué tarea quieres agregar?"),
        ("¿Necesitas algo más?", "¿Necesitas algo más?"),  # no deja la respuesta vacía
    ],
)
def test_quitar_muletilla_final(texto, esperado):
    assert quitar_muletilla_final(texto) == esperado
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

FECHA = datetime(2026, 9, 24, 12, 30)


def _boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text("- Le gusta el café", encoding="utf-8")
    (tmp_path / "02-Tareas").mkdir()
    (tmp_path / "02-Tareas" / "Pendientes.md").write_text("- [ ] Comprar pan", encoding="utf-8")


def test_crimson_se_presenta_con_su_nombre_y_personalidad(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True, ahora=FECHA)

    assert prompt.startswith("Eres Crimson.")
    assert "alegre" in prompt and "diplomacia" in prompt


def test_clover_tiene_otra_personalidad(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False, ahora=FECHA)

    assert prompt.startswith("Eres Clover.")
    assert "orden y la transparencia" in prompt


def test_incluye_perfil_mapa_de_la_boveda_y_fecha(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True, ahora=FECHA)

    assert "Le gusta el café" in prompt
    assert "- 02-Tareas/Pendientes.md" in prompt
    assert "jueves 2026-09-24 12:30" in prompt


def test_con_herramientas_no_mete_los_pendientes_en_el_prompt(tmp_path, monkeypatch):
    _boveda(tmp_path, monkeypatch)

    con = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True, ahora=FECHA)
    sin = construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False, ahora=FECHA)

    assert "Comprar pan" not in con  # los lee con la herramienta cuando los necesita
    assert "Comprar pan" in sin  # sin herramientas no tendría forma de verlos


def test_funciona_sin_boveda_configurada(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    prompt = construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True, ahora=FECHA)

    assert prompt.startswith("Eres Crimson.")
