from src.obsidian.contexto import construir_contexto, evaluar_guardado


def test_construir_contexto_vacio_sin_vault_configurada(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    assert construir_contexto("cualquier cosa") == ""


def test_construir_contexto_con_resultados(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "nota.md").write_text("informacion sobre el proyecto kindred", encoding="utf-8")

    contexto = construir_contexto("cuentame sobre el proyecto kindred")

    assert "nota.md" in contexto


def test_evaluar_guardado_registra_log_y_pendiente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    evaluar_guardado("recuérdame comprar leche", "listo, anotado", "ollama")

    log = (tmp_path / "00-Sistema" / "Logs-Interacciones.md").read_text(encoding="utf-8")
    pendientes = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "listo, anotado" in log
    assert "comprar leche" in pendientes


def test_evaluar_guardado_no_crashea_sin_vault(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    evaluar_guardado("hola", "hola", "ollama")
