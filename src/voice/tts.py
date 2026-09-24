"""Síntesis de voz (TTS) con ElevenLabs."""

import os
import tempfile
from pathlib import Path

import httpx
from playsound3 import playsound

from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

VOZ_POR_DEFECTO = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"; en cuentas gratuitas debe reemplazarse
# por una voz agregada a "My Voices" en tu cuenta (ver ELEVENLABS_VOICE_ID en .env).
MODELO_POR_DEFECTO = "eleven_multilingual_v2"
TIMEOUT_SEGUNDOS = 30

VARIABLE_VOZ_POR_MOTOR = {
    MOTOR_OLLAMA: "ELEVENLABS_VOICE_ID_OLLAMA",
    MOTOR_GEMINI: "ELEVENLABS_VOICE_ID_GEMINI",
}


def _elegir_voz(motor: str | None) -> str:
    """Elige el voice_id según qué motor generó la respuesta.

    Si no hay una voz específica configurada para ese motor, cae a
    ELEVENLABS_VOICE_ID (genérica) y de ahí a la voz por defecto.
    """
    variable_especifica = VARIABLE_VOZ_POR_MOTOR.get(motor)
    if variable_especifica:
        voz_especifica = os.getenv(variable_especifica)
        if voz_especifica:
            return voz_especifica
    return os.getenv("ELEVENLABS_VOICE_ID", VOZ_POR_DEFECTO)


def hablar(texto: str, motor: str | None = None) -> None:
    """Convierte texto a voz con ElevenLabs y lo reproduce.

    Si se indica `motor` ("ollama"/"gemini"), usa la voz configurada para
    ese motor. Si falla (sin API key, sin cuota, sin internet), no crashea:
    avisa por consola y muestra el texto para que la conversación continúe.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print(f"[aviso] Falta ELEVENLABS_API_KEY, no se puede reproducir audio.\n{texto}")
        return

    voz = _elegir_voz(motor)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voz}"
    try:
        respuesta = httpx.post(
            url,
            headers={"xi-api-key": api_key},
            json={"text": texto, "model_id": MODELO_POR_DEFECTO},
            timeout=TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as error:
        print(f"[aviso] ElevenLabs falló ({error}), mostrando texto en su lugar:\n{texto}")
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as archivo_temporal:
        archivo_temporal.write(respuesta.content)
        ruta_temporal = Path(archivo_temporal.name)

    try:
        playsound(str(ruta_temporal))
    finally:
        ruta_temporal.unlink(missing_ok=True)
