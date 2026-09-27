"""Síntesis de voz (TTS) con ElevenLabs.

El audio se reproduce con sounddevice (no como archivo) para poder medir su
volumen mientras suena: la UI lo usa para iluminar al agente al ritmo de su voz.
"""

import io
import os
import re
import threading

import httpx
import numpy as np
import sounddevice as sd
from faster_whisper.audio import decode_audio

from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

VOZ_POR_DEFECTO = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"; en cuentas gratuitas debe reemplazarse
# por una voz agregada a "My Voices" en tu cuenta (ver ELEVENLABS_VOICE_ID en .env).
MODELO_POR_DEFECTO = "eleven_multilingual_v2"
TIMEOUT_SEGUNDOS = 30
TASA_REPRODUCCION = 44100  # la del MP3 que devuelve ElevenLabs por defecto
RMS_VOZ_FUERTE = 0.2  # volumen RMS que se considera "al máximo" para el medidor

VARIABLE_VOZ_POR_MOTOR = {
    MOTOR_OLLAMA: "ELEVENLABS_VOICE_ID_OLLAMA",
    MOTOR_GEMINI: "ELEVENLABS_VOICE_ID_GEMINI",
}


_EMOJIS = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF️‍]")
_ENLACES = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARCAS_INICIO_LINEA = re.compile(r"^\s*(?:- \[[ x]\]\s*|#+\s*|[-*•]\s+|\d+[.)]\s+)", re.MULTILINE)
_SIMBOLOS_MARKDOWN = re.compile(r"[*_`#>|]")


def limpiar_para_voz(texto: str) -> str:
    """Quita markdown, viñetas y emojis: la voz los leía en voz alta, símbolo por símbolo."""
    texto = _ENLACES.sub(r"\1", texto)
    texto = _MARCAS_INICIO_LINEA.sub("", texto)
    texto = _SIMBOLOS_MARKDOWN.sub("", texto)
    texto = _EMOJIS.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip()


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


class MedidorDeVolumen:
    """Volumen (0 a 1) de lo que el agente está diciendo en este instante."""

    def __init__(self) -> None:
        self.nivel = 0.0


def hablar(texto: str, motor: str | None = None, medidor: MedidorDeVolumen | None = None) -> None:
    """Convierte texto a voz con ElevenLabs y lo reproduce.

    Si se indica `motor` ("ollama"/"gemini"), usa la voz configurada para
    ese motor. Si falla (sin API key, sin cuota, sin internet), no crashea:
    avisa por consola y muestra el texto para que la conversación continúe.
    Con `medidor`, va publicando ahí el volumen de lo que suena.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print(f"[aviso] Falta ELEVENLABS_API_KEY, no se puede reproducir audio.\n{texto}")
        return

    texto = limpiar_para_voz(texto)
    if not texto:
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

    audio = decode_audio(io.BytesIO(respuesta.content), sampling_rate=TASA_REPRODUCCION)
    _reproducir(audio, medidor)


def _reproducir(audio: np.ndarray, medidor: MedidorDeVolumen | None) -> None:
    posicion = 0
    terminado = threading.Event()

    def callback(salida, frames, tiempo, estado):
        nonlocal posicion
        bloque = audio[posicion : posicion + frames]
        posicion += len(bloque)
        salida[: len(bloque), 0] = bloque
        salida[len(bloque) :, 0] = 0
        if medidor is not None and len(bloque):
            medidor.nivel = min(1.0, float(np.sqrt(np.mean(bloque**2))) / RMS_VOZ_FUERTE)
        if len(bloque) < frames:
            raise sd.CallbackStop

    try:
        with sd.OutputStream(
            samplerate=TASA_REPRODUCCION,
            channels=1,
            dtype="float32",
            callback=callback,
            finished_callback=terminado.set,
        ):
            terminado.wait()
    finally:
        if medidor is not None:
            medidor.nivel = 0.0
