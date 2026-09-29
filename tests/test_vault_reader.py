import pytest

from src.obsidian.vault_reader import leer_nota, limpiar_nombre, listar_notas, resolver_nota, resolver_ruta


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


def _nota(tmp_path, ruta, contenido=""):
    archivo = tmp_path / ruta
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(contenido, encoding="utf-8")


@pytest.mark.parametrize(
    "nombre",
    ["03-Proyectos/Jarvis.md", "03-Proyectos/Jarvis", "Jarvis", "jarvis", "[[Jarvis]]", "[[Jarvis|mi proyecto]]", "Jarvis.md"],
)
def test_resolver_nota_acepta_nombre_o_ruta(tmp_path, monkeypatch, nombre):
    """El modelo a veces da solo el nombre ("Jarvis") en vez de la ruta completa: igual debe encontrarla."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _nota(tmp_path, "03-Proyectos/Jarvis.md")

    assert resolver_nota(nombre) == "03-Proyectos/Jarvis.md"


def test_resolver_nota_ignora_acentos_y_tolera_nombres_casi_iguales(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _nota(tmp_path, "04-Conocimiento/Programación/Node.js.md")
    _nota(tmp_path, "04-Conocimiento/Programación.md")

    assert resolver_nota("programacion") == "04-Conocimiento/Programación.md"
    assert resolver_nota("Nodejs") == "04-Conocimiento/Programación/Node.js.md"


def test_resolver_nota_no_inventa_si_no_hay_parecida(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _nota(tmp_path, "03-Proyectos/Jarvis.md")

    assert resolver_nota("Cosa inventada que no existe") is None


def test_limpiar_nombre():
    assert limpiar_nombre("[[Nota#Encabezado|alias]]") == "Nota"
    assert limpiar_nombre(" carpeta/Nota.md ") == "carpeta/Nota"
