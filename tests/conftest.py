"""Se carga antes de que pytest recolecte ningún test.

onnxruntime (usado por openwakeword y por faster-whisper vía ctranslate2/VAD) debe quedar cargado
en el proceso ANTES que winrt (usado por win11toast, Fase 7): cargarlos en el orden contrario
provoca un access violation nativo de Windows (visto en pruebas reales, con `pytest tests/`
completo — cada uno inicializa COM a su manera, y el segundo choca). Como pytest recolecta los
archivos de test en orden alfabético, "test_avisos.py" se cargaría antes que "test_wakeword.py"
si no se fuerza aquí el orden seguro.
"""

import onnxruntime  # noqa: F401
