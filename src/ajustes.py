"""Ajustes que el usuario cambia desde la UI: voces, velocidad del habla y comportamiento.

Se guardan en %LOCALAPPDATA%\\kindred\\ajustes.json. Prioridad: ajustes.json > .env > valor por
defecto, así lo que se elige en la UI manda, pero sin la UI todo sigue como dice el .env.
"""

import json
import os

from src.local import carpeta_local
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

# Voces de edge-tts probadas en español (sintetizando y transcribiendo el audio con Whisper):
# - Las de México leen el español nativo ("¡Órale, Josué!") y sintetizan el doble de rápido; los
#   términos en inglés se arreglan con el diccionario de src/voice/tts.py. Son las predeterminadas.
# - Las "Multilingual" (las de Copilot) son más expresivas y leen bien "Node.js", pero deciden el
#   idioma al empezar: frases cortas como "¡Órale, Josué!" salían en inglés ("Orala, Hostway").
VOCES = {
    "es-MX-DaliaNeural": ("Dalia · México", "f"),
    "es-MX-JorgeNeural": ("Jorge · México", "m"),
    "en-US-AvaMultilingualNeural": ("Ava · multilingüe, muy expresiva (experimental)", "f"),
    "en-US-EmmaMultilingualNeural": ("Emma · multilingüe, alegre (experimental)", "f"),
    "en-US-AndrewMultilingualNeural": ("Andrew · multilingüe, cálido (experimental)", "m"),
    "en-US-BrianMultilingualNeural": ("Brian · multilingüe, casual (experimental)", "m"),
    "es-US-PalomaNeural": ("Paloma · español de EE. UU.", "f"),
    "es-US-AlonsoNeural": ("Alonso · español de EE. UU.", "m"),
    "es-CO-SalomeNeural": ("Salomé · Colombia", "f"),
    "es-ES-XimenaNeural": ("Ximena · España", "f"),
}

POR_DEFECTO = {
    "voz_ollama": "es-MX-DaliaNeural",
    "voz_gemini": "es-MX-JorgeNeural",
    "velocidad_ollama": 5,  # % sobre la velocidad normal de la voz
    "velocidad_gemini": 0,
    "activar_por_nombre": True,
    "saludo_al_abrir": True,
    "iniciar_nucleo": True,
}

_VARIABLE_VOZ = {MOTOR_OLLAMA: "EDGE_TTS_VOICE_OLLAMA", MOTOR_GEMINI: "EDGE_TTS_VOICE_GEMINI"}
_SUFIJO = {MOTOR_OLLAMA: "ollama", MOTOR_GEMINI: "gemini"}


def _ruta():
    return carpeta_local() / "ajustes.json"


def cargar() -> dict:
    try:
        return json.loads(_ruta().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar(cambios: dict) -> None:
    datos = cargar() | cambios
    _ruta().write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def obtener(clave: str):
    return cargar().get(clave, POR_DEFECTO.get(clave))


def voz_de(motor: str) -> str:
    sufijo = _SUFIJO.get(motor, "ollama")
    elegida = cargar().get(f"voz_{sufijo}")
    if elegida:
        return elegida
    return os.getenv(_VARIABLE_VOZ.get(motor, ""), "") or os.getenv("EDGE_TTS_VOICE", "") or POR_DEFECTO[f"voz_{sufijo}"]


def genero_de(motor: str) -> str:
    """ "f" o "m": cómo habla el agente de sí mismo, según la voz que tiene."""
    voz = voz_de(motor)
    if voz in VOCES:
        return VOCES[voz][1]
    return "m" if motor == MOTOR_GEMINI else "f"


def velocidad_de(motor: str) -> int:
    return int(obtener(f"velocidad_{_SUFIJO.get(motor, 'ollama')}") or 0)
