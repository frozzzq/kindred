from src.obsidian.vault_writer import agregar_pendiente, escribir_nota, registrar_interaccion


def test_escribir_nota_crea_carpetas_y_archivo(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    escribir_nota("03-Proyectos/Jarvis.md", "primer contenido", sobrescribir=True)

    ruta = tmp_path / "03-Proyectos" / "Jarvis.md"
    assert ruta.read_text(encoding="utf-8") == "primer contenido"


def test_escribir_nota_agrega_sin_sobrescribir(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    ruta = tmp_path / "nota.md"
    ruta.write_text("linea 1", encoding="utf-8")

    escribir_nota("nota.md", "linea 2")

    assert ruta.read_text(encoding="utf-8") == "linea 1\nlinea 2"


def test_agregar_pendiente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    agregar_pendiente("comprar leche")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "comprar leche" in contenido
    assert contenido.startswith("- [ ]")


def test_registrar_interaccion(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    registrar_interaccion("hola", "hola, como estas", "ollama")

    contenido = (tmp_path / "00-Sistema" / "Logs-Interacciones.md").read_text(encoding="utf-8")
    assert "hola, como estas" in contenido
    assert "(ollama)" in contenido
