from src.obsidian.vault_writer import (
    agregar_pendiente,
    completar_pendiente,
    escribir_nota,
    guardar_contacto,
    recordar_sobre_usuario,
    registrar_interaccion,
)


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
    # La fecha es de cuándo se agregó; sin la etiqueta el modelo la leía como vencimiento.
    assert "(agregado " in contenido


def _pendientes(tmp_path, *lineas):
    carpeta = tmp_path / "02-Tareas"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "Pendientes.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def test_completar_pendiente_lo_mueve_a_completadas(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)", "- [ ] Comprar leche (agregado x)")

    resultado = completar_pendiente("LECHE")

    pendientes = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    completadas = (tmp_path / "02-Tareas" / "Completadas.md").read_text(encoding="utf-8")
    assert "leche" not in pendientes.lower()
    assert "Comprar pan" in pendientes
    assert completadas.startswith("- [x] Comprar leche")
    assert "completado" in resultado.lower()


def test_completar_pendiente_ignora_acentos(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Llamar al médico (agregado x)")

    resultado = completar_pendiente("medico")

    assert "completado" in resultado.lower()


def test_completar_pendiente_ambiguo_no_toca_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)", "- [ ] Comprar leche (agregado x)")

    resultado = completar_pendiente("comprar")

    pendientes = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "Comprar pan" in pendientes and "Comprar leche" in pendientes
    assert "varios" in resultado
    assert not (tmp_path / "02-Tareas" / "Completadas.md").exists()


def test_completar_pendiente_inexistente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)")

    assert "No encontré" in completar_pendiente("gasolina")


def test_recordar_sobre_usuario_escribe_en_el_perfil(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    recordar_sobre_usuario("Le gusta el café sin azúcar")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert perfil.startswith("- Le gusta el café sin azúcar")


def test_recordar_sobre_usuario_no_duplica_con_otras_palabras(tmp_path, monkeypatch):
    """Caso real: 'mi nombre es Josue' y 'Su nombre es Josue' quedaron como dos líneas."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    recordar_sobre_usuario("mi nombre es Josue")

    resultado = recordar_sobre_usuario("Su nombre es Josué")
    recordar_sobre_usuario("Se llama Josue")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert perfil.count("\n") == 0  # sigue siendo una sola línea
    assert resultado.startswith("Ya estaba")


def test_recordar_sobre_usuario_si_anota_datos_distintos(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    recordar_sobre_usuario("Se llama Josué")

    recordar_sobre_usuario("Le gusta programar en Python por las noches")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert "Python" in perfil and "Josué" in perfil


def test_guardar_contacto(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    guardar_contacto("Ana", "hermana del usuario, vive en Monterrey")

    contactos = (tmp_path / "01-Perfil" / "Contactos.md").read_text(encoding="utf-8")
    assert "**Ana**: hermana del usuario, vive en Monterrey" in contactos


def test_registrar_interaccion(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    registrar_interaccion("hola", "hola, como estas", "ollama")

    contenido = (tmp_path / "00-Sistema" / "Logs-Interacciones.md").read_text(encoding="utf-8")
    assert "hola, como estas" in contenido
    assert "(ollama)" in contenido
