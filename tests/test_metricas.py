from unittest.mock import patch

from src.obsidian.metricas import Metricas, calcular_metricas
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_GEMINI_FALLO, MOTOR_OLLAMA

LOG_DE_EJEMPLO = """\
### 2026-09-24 01:00 (ollama)
**Usuario:** hola
**Respuesta:** hola

### 2026-09-24 01:05 (gemini)
**Usuario:** busca algo
**Respuesta:** resultado

### 2026-09-24 01:10 (gemini_fallo)
**Usuario:** busca otra cosa
**Respuesta:** [fallo] sin facturación

### 2026-09-24 01:12 (ollama)
**Usuario:** busca otra cosa
**Respuesta:** resultado de respaldo

### 2026-09-24 01:15 (accion)
**Usuario:** abre paint
**Respuesta:** Abriendo paint...
"""


@patch("src.obsidian.metricas.leer_nota", return_value=LOG_DE_EJEMPLO)
def test_calcular_metricas_cuenta_por_motor(mock_leer):
    metricas = calcular_metricas()

    assert metricas.conteo_por_motor == {
        MOTOR_OLLAMA: 2,
        MOTOR_GEMINI: 1,
        MOTOR_GEMINI_FALLO: 1,
        MOTOR_ACCION: 1,
    }


@patch("src.obsidian.metricas.leer_nota", return_value=LOG_DE_EJEMPLO)
def test_total_resueltas_no_cuenta_fallos_de_gemini(mock_leer):
    metricas = calcular_metricas()

    assert metricas.total_resueltas == 4


@patch("src.obsidian.metricas.leer_nota", return_value=LOG_DE_EJEMPLO)
def test_porcentaje_por_motor(mock_leer):
    metricas = calcular_metricas()

    assert metricas.porcentaje(MOTOR_OLLAMA) == 50.0
    assert metricas.porcentaje(MOTOR_GEMINI) == 25.0
    assert metricas.porcentaje(MOTOR_ACCION) == 25.0


@patch("src.obsidian.metricas.leer_nota", return_value=LOG_DE_EJEMPLO)
def test_tasa_exito_gemini(mock_leer):
    metricas = calcular_metricas()

    assert metricas.tasa_exito_gemini() == 50.0


def test_tasa_exito_gemini_none_sin_intentos():
    assert Metricas().tasa_exito_gemini() is None


@patch("src.obsidian.metricas.leer_nota", return_value=None)
def test_calcular_metricas_sin_log(mock_leer):
    metricas = calcular_metricas()

    assert metricas.total_resueltas == 0
    assert metricas.conteo_por_motor == {}
