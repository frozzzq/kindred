"""Síntesis de voz (TTS): edge-tts primero (gratis, sin límite conocido), ElevenLabs como respaldo.

edge-tts reutiliza el servicio de voz de Microsoft Edge (no es una API oficial
para desarrolladores, así que puede fallar si Microsoft cambia algo) — por
eso, si falla, se cae a ElevenLabs igual que antes.

El texto se sintetiza y reproduce oración por oración: la primera empieza a
sonar en cuanto está lista (sin esperar a que termine de sintetizarse toda la
respuesta) mientras las siguientes se preparan en segundo plano, para que la
voz y el texto en pantalla se sientan pegados incluso en respuestas largas.

El audio se reproduce con sounddevice (no como archivo) para poder medir su
volumen mientras suena: la UI lo usa para iluminar al agente al ritmo de su voz.
"""

import asyncio
import io
import os
import queue
import re
import threading

import edge_tts
import httpx
import numpy as np
import sounddevice as sd
from faster_whisper.audio import decode_audio

from src import ajustes
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA

# --- edge-tts ---
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
_LIMITE_ORACION = re.compile(r"(?<=[.!?])\s+")


def limpiar_para_voz(texto: str) -> str:
    """Quita markdown, viñetas y emojis: la voz los leía en voz alta, símbolo por símbolo."""
    texto = _ENLACES.sub(r"\1", texto)
    texto = _MARCAS_INICIO_LINEA.sub("", texto)
    texto = _SIMBOLOS_MARKDOWN.sub("", texto)
    texto = _EMOJIS.sub("", texto)
    return re.sub(r"\s+", " ", texto).strip()


# Las voces en español leen los términos técnicos en inglés letra por letra o con fonética española
# ("Node.js" salía como "Nelga J.as", comprobado transcribiendo el audio con Whisper). Se les escribe
# como suenan. Las voces multilingües los pronuncian bien solas, así que a ellas no se les aplica.
_PRONUNCIACION_ES = (
    (re.compile(r"\bnode\.?js\b", re.IGNORECASE), "noud yei es"),
    (re.compile(r"\bjavascript\b", re.IGNORECASE), "yava script"),
    (re.compile(r"\btypescript\b", re.IGNORECASE), "taip script"),
    (re.compile(r"\bgithub\b", re.IGNORECASE), "guit jab"),
    (re.compile(r"\bgit\b", re.IGNORECASE), "guit"),
    (re.compile(r"\bnpm\b", re.IGNORECASE), "en pe eme"),
    (re.compile(r"\bjson\b", re.IGNORECASE), "yéison"),
    (re.compile(r"\bpython\b", re.IGNORECASE), "páiton"),
    (re.compile(r"\byoutube\b", re.IGNORECASE), "yutub"),
    (re.compile(r"\bwhatsapp\b", re.IGNORECASE), "guatsap"),
    (re.compile(r"\bspotify\b", re.IGNORECASE), "espotifái"),
    (re.compile(r"\bjarvis\b", re.IGNORECASE), "yarvis"),
    (re.compile(r"\bfrontend\b", re.IGNORECASE), "front end"),
    (re.compile(r"\bbackend\b", re.IGNORECASE), "bak end"),
)


def pronunciable(texto: str, voz: str) -> str:
    if "Multilingual" in voz:
        return texto
    for patron, como_suena in _PRONUNCIACION_ES:
        texto = patron.sub(como_suena, texto)
    return texto


def _partir_en_oraciones(texto: str) -> list[str]:
    """Divide en oraciones: la primera puede empezar a sonar sin esperar el resto de la respuesta."""
    partes = [p for p in _LIMITE_ORACION.split(texto) if p.strip()]
    return partes or [texto]


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


# Centinela: marca en la cola que ya no queda más audio por reproducir.
_FIN_DE_AUDIO = object()


_FIN_DE_ORACIONES = object()


class VozEnVivo:
    """Habla oraciones conforme van llegando: mientras suena una, se sintetiza la siguiente.

    Uso: decir() cada oración (aunque el modelo siga generando), terminar() cuando no vienen más,
    y esperar() hasta que acabe de sonar. `detener` corta todo casi de inmediato (interrupción).
    """

    def __init__(
        self,
        motor: str | None = None,
        medidor: MedidorDeVolumen | None = None,
        detener: threading.Event | None = None,
    ) -> None:
        self._motor = motor
        self._detener = detener
        self._oraciones: queue.Queue = queue.Queue()
        self._audio: queue.Queue = queue.Queue()
        self._dicho: list[str] = []
        self._sintetizador = threading.Thread(target=self._sintetizar, daemon=True)
        self._reproductor = threading.Thread(target=_reproducir_secuencia, args=(self._audio, medidor, detener), daemon=True)
        self._sintetizador.start()
        self._reproductor.start()

    def decir(self, texto: str) -> None:
        for oracion in _partir_en_oraciones(limpiar_para_voz(texto)):
            if oracion.strip():
                self._oraciones.put(oracion)

    def terminar(self) -> None:
        self._oraciones.put(_FIN_DE_ORACIONES)

    def esperar(self) -> None:
        self._reproductor.join()

    def _sintetizar(self) -> None:
        hubo_audio = False
        while True:
            oracion = self._oraciones.get()
            if oracion is _FIN_DE_ORACIONES:
                break
            if self._detener is not None and self._detener.is_set():
                continue  # lo interrumpieron: se descarta lo que ya no se va a decir
            self._dicho.append(oracion)
            audio = _sintetizar_edge_tts(oracion, self._motor)
            if audio is None:
                audio = _sintetizar_elevenlabs(oracion, self._motor)
            if audio is not None:
                self._audio.put(audio)
                hubo_audio = True
        if self._dicho and not hubo_audio:
            print(f"[aviso] No se pudo sintetizar voz (edge-tts y ElevenLabs fallaron):\n{' '.join(self._dicho)}")
        self._audio.put(_FIN_DE_AUDIO)


def hablar(
    texto: str,
    motor: str | None = None,
    medidor: MedidorDeVolumen | None = None,
    detener: threading.Event | None = None,
) -> None:
    """Convierte texto a voz y lo reproduce, oración por oración.

    Si se indica `motor` ("ollama"/"gemini"), usa la voz de ese agente (ver src/ajustes.py):
    edge-tts, con ElevenLabs como respaldo por oración. Si ambos fallan, no crashea: avisa por
    consola. Con `medidor`, va publicando ahí el volumen de lo que suena. `detener` interrumpe a
    medio hablar.
    """
    if not limpiar_para_voz(texto):
        return
    voz = VozEnVivo(motor, medidor, detener)
    voz.decir(texto)
    voz.terminar()
    voz.esperar()


def probar_voz(voz: str, texto: str, velocidad: int = 0, medidor: MedidorDeVolumen | None = None) -> bool:
    """Reproduce una frase con una voz concreta (para elegir voz en los ajustes). False si falló."""
    try:
        audio = asyncio.run(_pedir_audio_edge_tts(pronunciable(limpiar_para_voz(texto), voz), voz, f"{velocidad:+d}%"))
    except Exception as error:  # noqa: BLE001 - una prueba fallida solo se informa
        print(f"[aviso] No se pudo probar la voz {voz}: {error}")
        return False
    fragmentos: queue.Queue = queue.Queue()
    fragmentos.put(audio)
    fragmentos.put(_FIN_DE_AUDIO)
    _reproducir_secuencia(fragmentos, medidor)
    return True


def _velocidad(motor: str | None) -> str:
    porcentaje = ajustes.velocidad_de(motor) if motor in (MOTOR_OLLAMA, MOTOR_GEMINI) else 0
    return f"{porcentaje:+d}%"


async def _pedir_audio_edge_tts(texto: str, voz: str, velocidad: str = "+0%") -> np.ndarray:
    comunicador = edge_tts.Communicate(
        texto, voz, rate=velocidad, connect_timeout=EDGE_TTS_CONNECT_TIMEOUT, receive_timeout=EDGE_TTS_RECEIVE_TIMEOUT
    )
    audio = bytearray()
    async for fragmento in comunicador.stream():
        if fragmento["type"] == "audio":
            audio.extend(fragmento["data"])
    if not audio:
        raise edge_tts.exceptions.NoAudioReceived("edge-tts no devolvió audio")
    return decode_audio(io.BytesIO(bytes(audio)), sampling_rate=TASA_REPRODUCCION)


def _sintetizar_edge_tts(texto: str, motor: str | None, voz: str | None = None) -> np.ndarray | None:
    """Intenta sintetizar con edge-tts. None si falla (no es una API oficial: puede cambiar sin aviso)."""
    voz = voz or ajustes.voz_de(motor or MOTOR_OLLAMA)
    try:
        return asyncio.run(_pedir_audio_edge_tts(pronunciable(texto, voz), voz, _velocidad(motor)))
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


def _reproducir_secuencia(
    fragmentos: queue.Queue, medidor: MedidorDeVolumen | None, detener: threading.Event | None = None
) -> None:
    """Reproduce fragmentos de audio uno tras otro según van llegando, sin cortes entre ellos.

    Si la siguiente oración todavía se está sintetizando cuando termina la
    anterior, rellena con silencio en vez de cortar la reproducción — un
    respiro breve es preferible a que la voz se corte a medias. Si se
    activa `detener`, corta la reproducción de inmediato (interrupción).
    """
    terminado = threading.Event()
    restante = np.zeros(0, dtype="float32")
    agotado = False

    def callback(salida, frames, tiempo, estado):
        nonlocal restante, agotado
        if detener is not None and detener.is_set():
            agotado = True
        llenado = 0
        while llenado < frames and not agotado:
            if restante.size == 0:
                try:
                    fragmento = fragmentos.get_nowait()
                except queue.Empty:
                    break  # la siguiente oración aún no está lista
                if fragmento is _FIN_DE_AUDIO:
                    agotado = True
                    break
                restante = fragmento
            tomar = min(frames - llenado, restante.size)
            salida[llenado : llenado + tomar, 0] = restante[:tomar]
            restante = restante[tomar:]
            llenado += tomar
        salida[llenado:, 0] = 0
        if medidor is not None:
            medidor.nivel = min(1.0, float(np.sqrt(np.mean(salida[:llenado, 0] ** 2))) / RMS_VOZ_FUERTE) if llenado else 0.0
        if agotado and llenado == 0:
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
