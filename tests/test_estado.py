import pytest

from src.nucleo.estado import briefing_de_hoy, marcar_avisado, marcar_briefing, ruta_estado, ya_avisado


@pytest.fixture(autouse=True)
def local_appdata_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_ya_avisado_falso_si_nunca_se_marco():
    assert ya_avisado("pendiente:comprar leche:2026-09-30 18:00") is False


def test_marcar_avisado_lo_deja_avisado():
    marcar_avisado("clave-1", "2026-09-28 10:00")

    assert ya_avisado("clave-1") is True
    assert ya_avisado("clave-2") is False


def test_marcar_avisado_es_idempotente():
    marcar_avisado("clave-1", "2026-09-28 10:00")
    marcar_avisado("clave-1", "2026-09-28 10:00")  # una segunda vuelta del heartbeat no debe fallar

    assert ya_avisado("clave-1") is True


def test_briefing_de_hoy_ninguno_todavia():
    assert briefing_de_hoy("matutino") is None


def test_marcar_briefing_y_leerlo():
    marcar_briefing("matutino", "2026-09-28")

    assert briefing_de_hoy("matutino") == "2026-09-28"
    assert briefing_de_hoy("cierre") is None  # tipos distintos, no se mezclan


def test_marcar_briefing_actualiza_la_fecha():
    marcar_briefing("matutino", "2026-09-28")
    marcar_briefing("matutino", "2026-09-29")

    assert briefing_de_hoy("matutino") == "2026-09-29"


def test_el_estado_persiste_entre_conexiones(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    marcar_avisado("clave-1", "2026-09-28 10:00")

    assert ruta_estado().exists()
    assert ya_avisado("clave-1") is True  # nueva conexión (cada llamada abre y cierra la suya)


def test_varios_hilos_abriendo_una_base_nueva_a_la_vez_no_chocan(tmp_path, monkeypatch):
    """Pasar a WAL una base recién creada exige acceso exclusivo: con 4 hilos a la vez salía
    "database is locked" (5 de 30 intentos). Visto al correr la evaluación en una carpeta nueva."""
    import threading

    from src import local
    from src.nucleo import estado

    errores = []
    for ronda in range(8):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / f"ronda{ronda}"))
        barrera = threading.Barrier(4)

        def escribir(i):
            barrera.wait()
            try:
                for j in range(10):
                    estado.guardar_valor(f"k{i}", str(j))
                    estado.leer_valor(f"k{i}")
            except Exception as error:  # noqa: BLE001
                errores.append(repr(error))

        hilos = [threading.Thread(target=escribir, args=(i,)) for i in range(4)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

    assert errores == []
    assert local._preparadas  # cada base se preparó una sola vez
