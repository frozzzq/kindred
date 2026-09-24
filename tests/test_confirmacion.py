from unittest.mock import patch

from src.actions.confirmacion import confirmar_por_texto, es_afirmativo


def test_es_afirmativo_con_palabras_positivas():
    assert es_afirmativo("si") is True
    assert es_afirmativo("Sí, dale") is True
    assert es_afirmativo("ok") is True


def test_es_afirmativo_con_negativas():
    assert es_afirmativo("no") is False
    assert es_afirmativo("no, mejor no") is False
    assert es_afirmativo("así no, cancela") is False


def test_es_afirmativo_con_texto_vacio():
    assert es_afirmativo("") is False


@patch("builtins.input", return_value="si")
def test_confirmar_por_texto_afirmativo(mock_input):
    assert confirmar_por_texto("¿Confirmas?") is True


@patch("builtins.input", return_value="no")
def test_confirmar_por_texto_negativo(mock_input):
    assert confirmar_por_texto("¿Confirmas?") is False
