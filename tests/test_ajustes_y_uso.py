from datetime import datetime

from src import ajustes
from src.agente import metricas
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA


def test_la_voz_elegida_en_la_ui_gana_al_env(monkeypatch):
    monkeypatch.setenv("EDGE_TTS_VOICE_OLLAMA", "es-MX-DaliaNeural")
    assert ajustes.voz_de(MOTOR_OLLAMA) == "es-MX-DaliaNeural"

    ajustes.guardar({"voz_ollama": "en-US-EmmaMultilingualNeural"})

    assert ajustes.voz_de(MOTOR_OLLAMA) == "en-US-EmmaMultilingualNeural"
    assert ajustes.genero_de(MOTOR_OLLAMA) == "f"


def test_sin_nada_configurado_usa_las_voces_de_mexico(monkeypatch):
    monkeypatch.delenv("EDGE_TTS_VOICE_GEMINI", raising=False)
    monkeypatch.delenv("EDGE_TTS_VOICE", raising=False)

    assert ajustes.voz_de(MOTOR_GEMINI) == "es-MX-JorgeNeural"
    assert ajustes.genero_de(MOTOR_GEMINI) == "m"
    assert ajustes.velocidad_de(MOTOR_OLLAMA) == 5


def test_resumen_de_uso_por_agente_dia_y_cuota():
    metricas.registrar_turno("ollama", "voz", 1200, ["leer_nota"], 2, True)
    metricas.registrar_turno("ollama", "chat", 800, [], 1, True)
    metricas.registrar_turno("gemini", "chat", 1500, ["crear_nota", "leer_nota"], 3, True)
    metricas.registrar_turno("gemini", "chat", 50, [], 1, False)

    uso = metricas.resumen(datetime.now())

    assert uso.hoy_por_agente == {"ollama": 2, "gemini": 2}
    assert uso.promedio_ms == {"ollama": 1000, "gemini": 1500}
    assert uso.llamadas_gemini_hoy == 4
    assert uso.herramientas_top[0] == ("leer_nota", 2)
    assert uso.fallos_semana == 1
    assert len(uso.por_dia) == 7 and uso.por_dia[-1][1] == {"ollama": 2, "gemini": 2}


def test_diccionario_de_pronunciacion_solo_para_voces_en_espanol():
    from src.voice.tts import pronunciable

    assert pronunciable("Tu nota de Node.js en GitHub", "es-MX-DaliaNeural") == "Tu nota de noud yei es en guit jab"
    assert pronunciable("Tu nota de Node.js", "en-US-AvaMultilingualNeural") == "Tu nota de Node.js"
    assert pronunciable("digital", "es-MX-DaliaNeural") == "digital"  # "git" solo como palabra completa
