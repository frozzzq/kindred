import os
import time
from datetime import date, datetime
from unittest.mock import patch

import numpy as np
import pytest

from src.agente.contexto_turno import construir_contexto
from src.engines import embeddings
from src.engines.modelos import RespuestaMotor
from src.nucleo import diario, jardinero
from tests.test_notas import _vector


@pytest.fixture
def boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(embeddings, "embeber", lambda textos: np.array([_vector(t) for t in textos]))
    monkeypatch.setattr(embeddings, "embeber_consulta", _vector)

    def escribir(ruta, contenido, hace_minutos=60):
        archivo = tmp_path / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")
        momento = time.time() - hace_minutos * 60
        os.utime(archivo, (momento, momento))

    return escribir


def _leer(tmp_path, ruta):
    return (tmp_path / ruta).read_text(encoding="utf-8")


def test_el_jardinero_conecta_notas_escritas_a_mano(boveda, tmp_path):
    boveda("04-Conocimiento/Programación/Node.js.md", "Node es javascript en el servidor con npm.")
    boveda("04-Conocimiento/Programación/Express.md", "Express: framework de node para una api backend.")

    hecho = jardinero.cuidar()

    enlazada = "[[Express]]" in _leer(tmp_path, "04-Conocimiento/Programación/Node.js.md") or "[[Node.js]]" in _leer(
        tmp_path, "04-Conocimiento/Programación/Express.md"
    )
    assert enlazada
    assert any("conecté" in linea for linea in hecho)
    assert "[[Node.js]]" in _leer(tmp_path, "04-Conocimiento/Programación/Programación.md")


def test_el_jardinero_no_toca_una_nota_que_se_esta_editando(boveda, tmp_path):
    boveda("04-Conocimiento/Node.js.md", "Node es javascript en el servidor con npm.")
    boveda("04-Conocimiento/Express.md", "Express: framework de node para una api backend.", hace_minutos=1)

    jardinero.cuidar()

    assert "## Relacionado" not in _leer(tmp_path, "04-Conocimiento/Express.md")


def test_el_jardinero_no_revisa_dos_veces_lo_que_no_cambio(boveda):
    boveda("04-Conocimiento/Node.js.md", "Node es javascript en el servidor con npm.")
    jardinero.cuidar()

    with patch("src.nucleo.jardinero.notas.auto_conectar") as mock_conectar:
        jardinero.cuidar()

    mock_conectar.assert_not_called()


@patch("src.nucleo.diario.preguntar_ollama")
def test_el_diario_resume_el_dia(mock_ollama, boveda, tmp_path):
    hoy = date(2026, 9, 29)
    boveda(
        "00-Sistema/Logs/2026-09.md",
        "### 2026-09-28 10:00 (ollama)\n**Usuario:** ayer\n**Respuesta:** ok\n"
        "### 2026-09-29 10:00 (ollama)\n**Usuario:** estudié normalización\n**Respuesta:** ¡Eso!\n",
    )
    boveda("02-Tareas/Completadas.md", "- [x] Entregar el reporte (agregado x) (completado 2026-09-29 12:00)\n")
    boveda("00-Sistema/Registro-Acciones.md", "- 2026-09-29 11:00 · voz · `crear_nota` {} → Nota creada: 04-Conocimiento/SQL.md.\n")
    mock_ollama.return_value = RespuestaMotor(exito=True, texto="Hoy estudiaste normalización.")

    ruta = diario.escribir_diario(hoy)

    contenido = _leer(tmp_path, ruta)
    assert ruta == "06-Diario/2026-09-29.md"
    assert "Hoy estudiaste normalización." in contenido
    assert "- Entregar el reporte" in contenido
    assert "Nota creada: 04-Conocimiento/SQL" in contenido
    assert "estudié normalización" in mock_ollama.call_args.args[0] and "ayer" not in mock_ollama.call_args.args[0]


@patch("src.nucleo.diario.preguntar_ollama")
def test_el_diario_respeta_lo_que_escribio_el_usuario(mock_ollama, boveda, tmp_path):
    boveda("06-Diario/2026-09-29.md", "Hoy fue un buen día.\n")
    boveda("02-Tareas/Completadas.md", "- [x] Correr (completado 2026-09-29 07:00)\n")

    diario.escribir_diario(date(2026, 9, 29))
    diario.escribir_diario(date(2026, 9, 29))

    contenido = _leer(tmp_path, "06-Diario/2026-09-29.md")
    assert contenido.startswith("Hoy fue un buen día.")
    assert contenido.count(diario.SECCION) == 1


def test_sin_nada_que_anotar_no_crea_diario(boveda, tmp_path):
    assert diario.escribir_diario(date(2026, 9, 29)) is None
    assert not (tmp_path / "06-Diario").exists()


def test_preguntar_por_ayer_trae_el_diario(boveda):
    boveda("06-Diario/2026-09-28.md", "## Lo que pasó\nTerminaste la guía del padel.\n")

    contexto = construir_contexto("¿qué hice ayer?", ahora=datetime(2026, 9, 29, 10, 0))

    assert "guía del padel" in contexto
