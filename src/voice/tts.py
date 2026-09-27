"""Síntesis de voz (TTS): edge-tts primero (gratis, sin límite conocido), ElevenLabs como respaldo.

edge-tts reutiliza el servicio de voz de Microsoft Edge (no es una API oficial
para desarrolladores, así que puede fallar si Microsoft cambia algo) — por
eso, si falla, se cae a ElevenLabs igual que antes.

El audio se reproduce con sounddevice (no como archivo) para poder medir su
volumen mientras suena: la UI lo usa para iluminar al agente al ritmo de su voz.
"""

import asyncio
import io
import os
import re
import threading

import edge_tts
import httpx
import numpy as np
import sounddevice as sd
from faster_whisper.audio import decode_audio

from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

# --- edge-tts ---
VOZ_EDGE_POR_DEFECTO = "es-MX-JorgeNeural"
VARIABLE_VOZ_EDGE_POR_MOTOR = {
    MOTOR_OLLAMA: "EDGE_TTS_VOICE_OLLAMA",
    MOTOR_GEMINI: "EDGE_TTS_VOICE_GEMINI",
}
EDGE_TTS_CONNECT_TIMEOUT = 10
EDGE_TTS_RECEIVE_TIMEOUT = 30

# --- ElevenLabs (respaldo) ---
VOZ_POR_DEFECTO = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"; en cuentas gratuitas debe reemplazarse
# por una voz agregada a "My Voices" en tu cuenta (ver ELEVENLABS_VOICE_ID en .env).
MODELO_POR_DEFECTO = "eleven_multilingual_v2"
TIMEOUT_SEGUNDOS = 30
VARIABLE_VOZ_ELEVENLABS_POR_MOTOR = {
    MOTOR_OLLAMA: "ELEVENLABS_VOICE_ID_OLLAMA",
    MOTOR_GEMINI: "ELEVENLABS_VOICE_ID_GEMINI",
}

TASA_REPRODUCCION = 44100  # la de los MP3 que devuelven ambos servicios
RMS_VOZ_FUERTE = 0.2  # volumen RMS que se considera "al máximo" para el medidor


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


def _elegir_voz(motor: str | None, variables_por_motor: dict[str, str], variable_generica: str, por_defecto: str) -> str:
    """Elige la voz según qué motor generó la respuesta.

    Si no hay una voz específica configurada para ese motor, cae a la
    variable genérica y de ahí a la voz por defecto.
    """
    variable_especifica = variables_por_motor.get(motor)
    if variable_especifica:
        voz_especifica = os.getenv(variable_especifica)
        if voz_especifica:
            return voz_especifica
    return os.getenv(variable_generica, por_defecto)


class MedidorDeVolumen:
    """Volumen (0 a 1) de lo que el agente está diciendo en este instante."""

    def __init__(self) -> None:
        self.nivel = 0.0


def hablar(texto: str, motor: str | None = None, medidor: MedidorDeVolumen | None = None) -> None:
    """Convierte texto a voz y lo reproduce: primero edge-tts (gratis), y si falla, ElevenLabs.

    Si se indica `motor` ("ollama"/"gemini"), usa la voz configurada para ese
    motor en cada servicio. Si ambos fallan (sin internet, sin API key de
    respaldo, etc.), no crashea: avisa por consola y muestra el texto para
    que la conversación continúe. Con `medidor`, va publicando ahí el volumen
    de lo que suena.
    """
    texto = limpiar_para_voz(texto)
    if not texto:
        return

    audio = _sintetizar_edge_tts(texto, motor)
    if audio is None:
        audio = _sintetizar_elevenlabs(texto, motor)
    if audio is None:
        print(f"[aviso] No se pudo sintetizar voz (edge-tts y ElevenLabs fallaron), mostrando texto en su lugar:\n{texto}")
        return

    _reproducir(audio, medidor)


async def _pedir_audio_edge_tts(texto: str, voz: str) -> np.ndarray:
    comunicador = edge_tts.Communicate(
        texto, voz, connect_timeout=EDGE_TTS_CONNECT_TIMEOUT, receive_timeout=EDGE_TTS_RECEIVE_TIMEOUT
    )
    audio = bytearray()
    async for fragmento in comunicador.stream():
        if fragmento["type"] == "audio":
            audio.extend(fragmento["data"])
    if not audio:
        raise edge_tts.exceptions.NoAudioReceived("edge-tts no devolvió audio")
    return decode_audio(io.BytesIO(bytes(audio)), sampling_rate=TASA_REPRODUCCION)


def _sintetizar_edge_tts(texto: str, motor: str | None) -> np.ndarray | None:
    """Intenta sintetizar con edge-tts. None si falla (no es una API oficial: puede cambiar sin aviso)."""
    voz = _elegir_voz(motor, VARIABLE_VOZ_EDGE_POR_MOTOR, "EDGE_TTS_VOICE", VOZ_EDGE_POR_DEFECTO)
    try:
        return asyncio.run(_pedir_audio_edge_tts(texto, voz))
    except Exception as error:  # noqa: BLE001 - respaldo best-effort: cualquier fallo cae a ElevenLabs
        print(f"[aviso] edge-tts falló ({error}), probando ElevenLabs...")
        return None


def _sintetizar_elevenlabs(texto: str, motor: str | None) -> np.ndarray | None:
    """Respaldo de pago si edge-tts falló. None si tampoco se pudo (sin API key, sin cuota, sin internet)."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[aviso] Falta ELEVENLABS_API_KEY, no hay respaldo disponible.")
        return None

    voz = _elegir_voz(motor, VARIABLE_VOZ_ELEVENLABS_POR_MOTOR, "ELEVENLABS_VOICE_ID", VOZ_POR_DEFECTO)
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
        print(f"[aviso] ElevenLabs también falló ({error}).")
        return None

    return decode_audio(io.BytesIO(respuesta.content), sampling_rate=TASA_REPRODUCCION)


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
