from unittest.mock import MagicMock, patch

from src.actions.busqueda_web import buscar_en_internet, construir_contexto_web


@patch("src.actions.busqueda_web.DDGS")
def test_buscar_en_internet_devuelve_resultados(mock_ddgs_cls):
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "Clima hoy", "body": "Soleado, 22°C", "href": "https://ejemplo.com/clima"},
    ]
    mock_ddgs_cls.return_value.__enter__.return_value = mock_ddgs

    resultados = buscar_en_internet("clima de hoy")

    assert len(resultados) == 1
    assert resultados[0].titulo == "Clima hoy"
    assert resultados[0].fragmento == "Soleado, 22°C"
    assert resultados[0].url == "https://ejemplo.com/clima"


@patch("src.actions.busqueda_web.DDGS")
def test_buscar_en_internet_falla_sin_crashear(mock_ddgs_cls):
    mock_ddgs_cls.side_effect = Exception("sin conexión")

    resultados = buscar_en_internet("clima de hoy")

    assert resultados == []


@patch("src.actions.busqueda_web.buscar_en_internet")
def test_construir_contexto_web_con_resultados(mock_buscar):
    from src.actions.busqueda_web import ResultadoBusquedaWeb

    mock_buscar.return_value = [
        ResultadoBusquedaWeb(titulo="Clima hoy", fragmento="Soleado", url="https://ejemplo.com"),
    ]

    contexto = construir_contexto_web("clima de hoy")

    assert "Clima hoy" in contexto
    assert "Soleado" in contexto


@patch("src.actions.busqueda_web.buscar_en_internet", return_value=[])
def test_construir_contexto_web_vacio_sin_resultados(mock_buscar):
    assert construir_contexto_web("algo muy raro") == ""
