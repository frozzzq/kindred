import numpy as np
import pytest

from src.engines import embeddings
from src.obsidian import indice
from tests.test_notas import _vector


@pytest.fixture
def boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    def escribir(ruta, contenido):
        archivo = tmp_path / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")

    return escribir


@pytest.fixture
def semantico(monkeypatch):
    llamadas = []

    def embeber(textos):
        llamadas.append(list(textos))
        return np.array([_vector(t) for t in textos])

    monkeypatch.setattr(embeddings, "embeber", embeber)
    monkeypatch.setattr(embeddings, "embeber_consulta", _vector)
    return llamadas


def test_fragmentar_por_encabezado_sin_propiedades_ni_relacionado():
    contenido = "---\ncreado: 2026-09-29\n---\nIntro.\n\n## Event loop\nNo bloquea.\n\n## Relacionado\n- [[Express]]\n"

    fragmentos = indice.fragmentar(contenido)

    assert [(f.encabezado, f.texto) for f in fragmentos] == [("", "Intro."), ("Event loop", "No bloquea.")]


def test_fragmentar_parte_textos_largos():
    parrafo = "Una oración bastante larga sobre node. " * 60

    fragmentos = indice.fragmentar(parrafo)

    assert len(fragmentos) > 1
    assert all(len(f.texto) <= indice.MAX_CARACTERES_FRAGMENTO for f in fragmentos)


def test_actualizar_es_incremental_y_ve_cambios_y_borrados(boveda, tmp_path):
    boveda("04-Conocimiento/Node.js.md", "Node es javascript en el servidor.")
    boveda("00-Sistema/Registro-Acciones.md", "node node node")

    primera = indice.actualizar()
    segunda = indice.actualizar()
    boveda("04-Conocimiento/Node.js.md", "Node cambió.")
    (tmp_path / "04-Conocimiento" / "Node.js.md").touch()
    boveda("04-Conocimiento/Express.md", "Express.")
    tercera = indice.actualizar()
    (tmp_path / "04-Conocimiento" / "Express.md").unlink()
    cuarta = indice.actualizar()

    assert primera.procesadas == 1  # 00-Sistema no se indexa
    assert segunda.procesadas == 0
    assert tercera.procesadas == 2
    assert cuarta.borradas == 1
    assert indice.estado().notas == 1


def test_buscar_por_palabras_sin_embeddings(boveda):
    boveda("02-Tareas/Pendientes.md", "- [ ] Comprar leche y pan para el desayuno")
    boveda("04-Conocimiento/Python.md", "Apuntes sobre programación en python")
    boveda("00-Sistema/Logs/2026-09.md", "comprar leche comprar leche")
    indice.actualizar()

    resultados = indice.buscar("necesito comprar leche")

    assert [r.ruta for r in resultados] == ["02-Tareas/Pendientes.md"]
    assert resultados[0].similitud is None and resultados[0].palabras_en_comun == 2


def test_sin_embeddings_una_sola_palabra_en_comun_no_es_contexto_relevante(boveda):
    """Caso real: palabras comunes ("sobre", "historia") conectaban notas sin relación."""
    boveda("PRUEBAS.md", "Prueba: crea una nota sobre la historia de algo y verifica.")
    indice.actualizar()

    assert indice.contexto_relevante("cuéntame la historia de one piece") == []


def test_buscar_por_significado(boveda, semantico):
    boveda("04-Conocimiento/Node.js.md", "Entorno de ejecución de javascript con npm.")
    boveda("04-Conocimiento/One Piece.md", "Luffy es un pirata del manga.")
    indice.actualizar()

    resultados = indice.contexto_relevante("¿cómo hago una api en el backend?")

    assert [r.ruta for r in resultados] == ["04-Conocimiento/Node.js.md"]
    assert resultados[0].similitud > indice.UMBRAL_CONTEXTO


def test_contexto_relevante_excluye_lo_pedido(boveda, semantico):
    boveda("01-Perfil/Yo.md", "Le gusta node y javascript.")
    boveda("04-Conocimiento/Node.js.md", "Node y javascript con npm.")
    indice.actualizar()

    rutas = [r.ruta for r in indice.contexto_relevante("node javascript", excluir={"01-Perfil/Yo.md"})]

    assert rutas == ["04-Conocimiento/Node.js.md"]


def test_los_vectores_se_completan_cuando_vuelven_los_embeddings(boveda, monkeypatch):
    boveda("04-Conocimiento/Node.js.md", "Node y javascript.")
    indice.actualizar()  # sin embeddings (conftest): queda sin vector
    assert indice.estado().sin_vector == 1

    monkeypatch.setattr(embeddings, "embeber", lambda textos: np.array([_vector(t) for t in textos]))
    indice.actualizar()

    assert indice.estado().sin_vector == 0 and indice.estado().semantico


def test_si_cambia_el_modelo_se_recalculan_los_vectores(boveda, semantico, monkeypatch):
    boveda("04-Conocimiento/Node.js.md", "Node y javascript.")
    indice.actualizar()
    antes = len(semantico)

    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "otro-modelo")
    indice.actualizar()

    assert len(semantico) == antes + 1


def test_notas_similares_solo_entre_notas_de_conocimiento(boveda, semantico):
    boveda("04-Conocimiento/Node.js.md", "Node y javascript con npm.")
    boveda("04-Conocimiento/Express.md", "Express, api de node.")
    boveda("02-Tareas/Pendientes.md", "- [ ] estudiar node javascript npm")
    indice.actualizar()

    similares = indice.notas_similares("04-Conocimiento/Node.js.md")

    assert [ruta for ruta, _ in similares] == ["04-Conocimiento/Express.md"]


def test_cada_boveda_tiene_su_propio_indice(tmp_path, monkeypatch):
    for nombre, texto in (("real", "comprar leche fresca"), ("pruebas", "estudiar node")):
        carpeta = tmp_path / nombre
        carpeta.mkdir()
        (carpeta / "Nota.md").write_text(texto, encoding="utf-8")
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(carpeta))
        indice.actualizar()

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path / "real"))
    assert indice.buscar("comprar leche fresca")
    assert not indice.buscar("estudiar node")
