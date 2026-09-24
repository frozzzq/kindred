import numpy as np

from src.voice.audio import amplificar, ganancia_microfono


def test_ganancia_microfono_lee_del_entorno(monkeypatch):
    monkeypatch.setenv("GANANCIA_MICROFONO", "5.0")

    assert ganancia_microfono() == 5.0


def test_ganancia_microfono_valor_por_defecto(monkeypatch):
    monkeypatch.delenv("GANANCIA_MICROFONO", raising=False)

    assert ganancia_microfono() == 3.0


def test_ganancia_microfono_invalida_cae_a_default(monkeypatch):
    monkeypatch.setenv("GANANCIA_MICROFONO", "no-es-un-numero")

    assert ganancia_microfono() == 3.0


def test_amplificar_multiplica_la_senal(monkeypatch):
    monkeypatch.setenv("GANANCIA_MICROFONO", "2.0")
    bloque = np.array([0.1, -0.1, 0.05], dtype="float32")

    resultado = amplificar(bloque)

    assert np.allclose(resultado, [0.2, -0.2, 0.1])


def test_amplificar_no_satura_mas_de_1(monkeypatch):
    monkeypatch.setenv("GANANCIA_MICROFONO", "10.0")
    bloque = np.array([0.5, -0.5], dtype="float32")

    resultado = amplificar(bloque)

    assert resultado.max() <= 1.0
    assert resultado.min() >= -1.0


def test_amplificar_con_ganancia_1_no_cambia_nada(monkeypatch):
    monkeypatch.setenv("GANANCIA_MICROFONO", "1.0")
    bloque = np.array([0.1, -0.1], dtype="float32")

    resultado = amplificar(bloque)

    assert np.array_equal(resultado, bloque)
