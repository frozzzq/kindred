import os

import pytest

from src.obsidian.grafo import construir_grafo, firma_boveda


@pytest.fixture
def boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    def escribir(ruta: str, contenido: str = "") -> None:
        archivo = tmp_path / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")

    return escribir


def _enlaces(grafo):
    return {frozenset((a.origen, a.destino)) for a in grafo.aristas if a.es_enlace}


def _carpetas(grafo):
    return {frozenset((a.origen, a.destino)) for a in grafo.aristas if not a.es_enlace}


def test_cada_nota_y_carpeta_es_un_nodo(boveda):
    boveda("01-Perfil/Yo.md")
    boveda("Suelta.md")

    nodos = {n.id: n for n in construir_grafo().nodos}

    assert set(nodos) == {"01-Perfil/Yo.md", "01-Perfil", "Suelta.md"}
    assert nodos["01-Perfil"].es_carpeta
    assert nodos["01-Perfil/Yo.md"].nombre == "Yo"


def test_las_notas_se_unen_a_su_carpeta_y_las_subcarpetas_a_su_padre(boveda):
    boveda("00-Sistema/Configuracion.md")
    boveda("00-Sistema/Respaldos/Viejo.md")
    boveda("Suelta.md")

    assert _carpetas(construir_grafo()) == {
        frozenset(("00-Sistema", "00-Sistema/Configuracion.md")),
        frozenset(("00-Sistema/Respaldos", "00-Sistema/Respaldos/Viejo.md")),
        frozenset(("00-Sistema", "00-Sistema/Respaldos")),
    }


def test_resuelve_enlaces_como_obsidian(boveda):
    boveda("01-Perfil/Yo.md")
    boveda("01-Perfil/Contactos.md")
    boveda("02-Tareas/Pendientes.md")
    boveda(
        "Diario.md",
        "Hablé con [[contactos|mis amigos]] sobre [[01-Perfil/Yo#Gustos]].\n"
        "![[Pendientes]] y [otra](02-Tareas/Pendientes.md)",
    )

    assert _enlaces(construir_grafo()) == {
        frozenset(("Diario.md", "01-Perfil/Contactos.md")),
        frozenset(("Diario.md", "01-Perfil/Yo.md")),
        frozenset(("Diario.md", "02-Tareas/Pendientes.md")),
    }


def test_ignora_adjuntos_notas_inexistentes_y_enlaces_a_si_misma(boveda):
    boveda("Nota.md", "![[Pasted image 2026.png|300]] [[No existe todavía]] [[Nota]]")

    assert _enlaces(construir_grafo()) == set()


def test_un_enlace_real_reemplaza_la_conexion_por_carpeta(boveda):
    boveda("01-Perfil/Yo.md")
    boveda("01-Perfil/Patrones.md", "Ver [[Yo]] y otra vez [[Yo]]")

    grafo = construir_grafo()
    entre_notas = [a for a in grafo.aristas if {a.origen, a.destino} == {"01-Perfil/Yo.md", "01-Perfil/Patrones.md"}]

    assert len(entre_notas) == 1 and entre_notas[0].es_enlace


def test_la_firma_cambia_al_crear_editar_o_borrar_notas(boveda, tmp_path):
    boveda("Nota.md", "hola")
    inicial = firma_boveda()

    boveda("Otra.md")
    tras_crear = firma_boveda()
    archivo = tmp_path / "Nota.md"
    os.utime(archivo, ns=(archivo.stat().st_atime_ns, archivo.stat().st_mtime_ns + 1_000_000))
    tras_editar = firma_boveda()
    (tmp_path / "Otra.md").unlink()
    tras_borrar = firma_boveda()

    assert len({inicial, tras_crear, tras_editar, tras_borrar}) == 4
    assert firma_boveda() == tras_borrar  # sin cambios, misma firma: no se rehace el grafo
