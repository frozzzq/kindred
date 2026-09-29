"""Se carga antes de que pytest recolecte ningún test.

onnxruntime (usado por openwakeword y por faster-whisper vía ctranslate2/VAD) debe quedar cargado
en el proceso ANTES que winrt (usado por win11toast, Fase 7): cargarlos en el orden contrario
provoca un access violation nativo de Windows (visto en pruebas reales, con `pytest tests/`
completo — cada uno inicializa COM a su manera, y el segundo choca). Como pytest recolecta los
archivos de test en orden alfabético, "test_avisos.py" se cargaría antes que "test_wakeword.py"
si no se fuerza aquí el orden seguro.
"""

import onnxruntime  # noqa: F401
import pytest


@pytest.fixture(autouse=True)
def _aislar_de_la_maquina(tmp_path_factory, monkeypatch):
    """Cada test con su propia carpeta local (estado.db, índice, ajustes) y sin llamar a Ollama.

    Sin esto los tests escribían en el %LOCALAPPDATA%\\kindred real y los embeddings iban al
    servidor de Ollama de verdad (lento y no determinista). Los tests que prueban búsqueda
    semántica ponen su propio embeddings falso (ver tests/test_indice.py).
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path_factory.mktemp("localappdata")))
    from src.engines import embeddings
    from src.obsidian import indice

    monkeypatch.setattr(embeddings, "embeber", lambda textos: None)
    monkeypatch.setattr(embeddings, "embeber_consulta", lambda consulta: None)
    monkeypatch.setattr(indice, "_cache", indice._Cache())
