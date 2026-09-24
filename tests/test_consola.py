import io

from src.consola import forzar_utf8


def test_forzar_utf8_no_crashea_sin_reconfigure(monkeypatch):
    """Si stdout/stderr no tienen reconfigure() (ej. en algunos entornos de test), no debe fallar."""
    flujo_sin_reconfigure = object()
    monkeypatch.setattr("sys.stdout", flujo_sin_reconfigure)
    monkeypatch.setattr("sys.stderr", flujo_sin_reconfigure)

    forzar_utf8()  # no debe lanzar excepción


def test_forzar_utf8_reconfigura_a_utf8(monkeypatch):
    flujo = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr("sys.stdout", flujo)
    monkeypatch.setattr("sys.stderr", flujo)

    forzar_utf8()

    assert flujo.encoding.lower() == "utf-8"
