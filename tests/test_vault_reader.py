import pytest

from src.obsidian.vault_reader import buscar_en_boveda, leer_nota, listar_notas, resolver_ruta


def test_listar_notas_encuentra_md_e_ignora_config_obsidian(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text("hola", encoding="utf-8")
    (tmp_path / "otro.txt").write_text("no es nota", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.md").write_text("interno", encoding="utf-8")

    notas = listar_notas()

    assert len(notas) == 1
    assert notas[0].name == "Yo.md"


def test_leer_nota_existente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "nota.md").write_text("contenido de prueba", encoding="utf-8")

    assert leer_nota("nota.md") == "contenido de prueba"


def test_leer_nota_inexistente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    assert leer_nota("no-existe.md") is None


def test_buscar_en_boveda_encuentra_coincidencias(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "02-Tareas").mkdir()
    (tmp_path / "02-Tareas" / "Pendientes.md").write_text(
        "Comprar leche y pan para el desayuno", encoding="utf-8"
    )
    (tmp_path / "04-Conocimiento").mkdir()
    (tmp_path / "04-Conocimiento" / "Notas.md").write_text(
        "Apuntes sobre programacion en python", encoding="utf-8"
    )

    resultados = buscar_en_boveda("necesito comprar leche")

    assert len(resultados) == 1
    assert resultados[0].ruta_relativa.endswith("Pendientes.md")


def test_buscar_en_boveda_sin_bovedas_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "no-existe"))

    assert buscar_en_boveda("cualquier cosa") == []


def test_buscar_en_boveda_ignora_el_log_de_conversaciones(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "00-Sistema").mkdir()
    (tmp_path / "00-Sistema" / "Logs-Interacciones.md").write_text("comprar leche comprar leche", encoding="utf-8")

    assert buscar_en_boveda("comprar leche") == []


def test_resolver_ruta_rechaza_rutas_fuera_de_la_boveda(tmp_path, monkeypatch):
    boveda = tmp_path / "boveda"
    boveda.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(boveda))

    with pytest.raises(ValueError):
        resolver_ruta("../secreto.txt")


def test_leer_nota_rechaza_rutas_fuera_de_la_boveda(tmp_path, monkeypatch):
    boveda = tmp_path / "boveda"
    boveda.mkdir()
    (tmp_path / "secreto.md").write_text("no deberías leer esto", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(boveda))

    with pytest.raises(ValueError):
        leer_nota("../secreto.md")
