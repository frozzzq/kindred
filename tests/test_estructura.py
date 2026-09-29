from src.obsidian.estructura import asegurar_estructura_boveda


def test_crea_carpetas_y_notas_base(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    asegurar_estructura_boveda()

    assert (tmp_path / "02-Tareas" / "Pendientes.md").exists()
    assert (tmp_path / "00-Sistema" / "Logs").is_dir()
    assert (tmp_path / "00-Sistema" / "Plantillas" / "Proyecto.md").exists()
    for carpeta in ("03-Proyectos", "04-Conocimiento", "05-Decisiones", "06-Diario", "07-Archivo"):
        assert (tmp_path / carpeta).is_dir()
    assert "# Inicio" in (tmp_path / "Inicio.md").read_text(encoding="utf-8")


def test_no_sobrescribe_notas_existentes(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text("info importante", encoding="utf-8")

    asegurar_estructura_boveda()

    assert (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8") == "info importante"


def test_categorias_de_notas():
    from src.obsidian.estructura import es_buscable, es_conocimiento, es_de_sistema, es_indice, ruta_indice

    assert es_de_sistema("00-Sistema/Registro-Acciones.md") and not es_buscable("00-Sistema/Logs/2026-09.md")
    assert es_buscable("02-Tareas/Pendientes.md") and not es_conocimiento("02-Tareas/Pendientes.md")
    assert es_conocimiento("04-Conocimiento/Programación/Node.js.md")
    assert es_indice("04-Conocimiento/Programación/Programación.md") and es_indice("Inicio.md")
    assert not es_conocimiento("04-Conocimiento/Programación/Programación.md")
    assert ruta_indice("04-Conocimiento/Programación") == "04-Conocimiento/Programación/Programación.md"
