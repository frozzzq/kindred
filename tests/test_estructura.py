from src.obsidian.estructura import asegurar_estructura_boveda


def test_crea_carpetas_y_notas_base(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    asegurar_estructura_boveda()

    assert (tmp_path / "00-Sistema" / "Configuracion.md").exists()
    assert (tmp_path / "02-Tareas" / "Pendientes.md").exists()
    assert (tmp_path / "03-Proyectos").is_dir()
    assert (tmp_path / "04-Conocimiento").is_dir()
    assert (tmp_path / "05-Decisiones").is_dir()


def test_no_sobrescribe_notas_existentes(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text("info importante", encoding="utf-8")

    asegurar_estructura_boveda()

    assert (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8") == "info importante"
