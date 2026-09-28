import pytest

from src.herramientas.catalogo import REGISTRO
from src.herramientas.registro import ContextoEjecucion
from src.obsidian.herramientas import HERRAMIENTAS_DE_ESCRITURA, afirma_cambio_sin_hacerlo


def ejecutar_herramienta(nombre, argumentos):
    return REGISTRO.ejecutar(nombre, argumentos, ContextoEjecucion(confirmador=lambda descripcion: True))


@pytest.mark.parametrize(
    "texto",
    [
        "He agregado el pendiente.",
        "Listo, lo anoté.",
        "Marqué como completada la tarea.",
        "He guardado que te llamas Luis.",
        "Añadí la tarea.",
        "Mucho gusto, Josué, lo tendré presente.",  # caso real: lo dijo sin guardar nada
        "Perfecto, lo tendré en cuenta.",
        "Listo, anotado.",
        "Ya quedó guardado tu contacto.",
        "Pendiente agregado: comprar leche.",
        "Lo he añadido a tus pendientes.",
    ],
)
def test_detecta_cuando_dice_que_cambio_algo_sin_herramienta(texto):
    assert afirma_cambio_sin_hacerlo(texto, []) is True
    assert afirma_cambio_sin_hacerlo(texto, ["leer_nota"]) is True


def test_no_marca_si_si_uso_una_herramienta_de_escritura():
    assert afirma_cambio_sin_hacerlo("He agregado el pendiente.", ["agregar_pendiente"]) is False


@pytest.mark.parametrize(
    "texto",
    [
        "¿Quieres que lo agregue?",
        "Tienes tres pendientes.",
        "¿Cuál pendiente?",
        # caso real: leía la fecha de la nota ("(agregado 2026-09-27 20:07)") y se tomaba como un cambio
        "Tienes un pendiente agregado el 27 de septiembre: revisar la tarea de física.",
        "Tu pendiente es marcar como completada la inscripción.",
    ],
)
def test_no_marca_respuestas_que_no_afirman_cambios(texto):
    assert afirma_cambio_sin_hacerlo(texto, []) is False


def test_las_herramientas_de_escritura_estan_registradas():
    """La red de seguridad afirma_cambio_sin_hacerlo depende de estos nombres: si uno cambia, deja de funcionar."""
    assert HERRAMIENTAS_DE_ESCRITURA <= REGISTRO.nombres()


def test_leer_nota_devuelve_contenido_completo(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "02-Tareas").mkdir()
    lineas = "\n".join(f"- [ ] tarea {i}" for i in range(11))
    (tmp_path / "02-Tareas" / "Pendientes.md").write_text(lineas, encoding="utf-8")

    resultado = ejecutar_herramienta("leer_nota", {"ruta": "02-Tareas/Pendientes.md"})

    # El problema original: solo le llegaba un fragmento de ~160 caracteres.
    assert "tarea 0" in resultado and "tarea 10" in resultado


def test_leer_nota_inexistente_explica_en_vez_de_fallar(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    assert "no existe" in ejecutar_herramienta("leer_nota", {"ruta": "nada.md"})


def test_leer_nota_fuera_de_la_boveda_devuelve_error(tmp_path, monkeypatch):
    boveda = tmp_path / "boveda"
    boveda.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(boveda))

    assert ejecutar_herramienta("leer_nota", {"ruta": "../../Windows/win.ini"}).startswith("Error")


def test_listar_notas(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "01-Perfil").mkdir()
    (tmp_path / "01-Perfil" / "Yo.md").write_text("", encoding="utf-8")

    assert ejecutar_herramienta("listar_notas", {}) == "01-Perfil/Yo.md"


def test_agregar_pendiente_por_herramienta(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    ejecutar_herramienta("agregar_pendiente", {"tarea": "Comprar leche"})

    assert "Comprar leche" in (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")


def test_herramienta_desconocida():
    assert "no existe" in ejecutar_herramienta("borrar_todo", {})


def test_argumentos_equivocados_no_crashean():
    assert ejecutar_herramienta("leer_nota", {"archivo": "x.md"}).startswith("Error")
