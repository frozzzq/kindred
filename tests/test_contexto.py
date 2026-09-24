from unittest.mock import patch

from src.obsidian.contexto import evaluar_guardado


@patch("src.obsidian.contexto.reflexionar_si_toca")
def test_evaluar_guardado_registra_la_interaccion_en_el_log(mock_reflexion, tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    evaluar_guardado("hola", "hola, ¿en qué te ayudo?", "ollama")

    log = (tmp_path / "00-Sistema" / "Logs-Interacciones.md").read_text(encoding="utf-8")
    assert "hola, ¿en qué te ayudo?" in log
    mock_reflexion.assert_called_once()


@patch("src.obsidian.contexto.reflexionar_si_toca")
def test_evaluar_guardado_ya_no_crea_pendientes_por_palabras_clave(mock_reflexion, tmp_path, monkeypatch):
    """Antes cualquier mensaje con 'pendiente' se guardaba como tarea, incluidas preguntas."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    evaluar_guardado("busca la nota de pendientes y dime que hay escrito", "Tienes 3 pendientes.", "ollama")

    assert not (tmp_path / "02-Tareas" / "Pendientes.md").exists()


@patch("src.obsidian.contexto.reflexionar_si_toca")
def test_evaluar_guardado_no_crashea_sin_vault(mock_reflexion, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    evaluar_guardado("hola", "hola", "ollama")

    mock_reflexion.assert_not_called()
