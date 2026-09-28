"""Avisos del núcleo: notificación de Windows + voz.

Nunca debe tumbar el heartbeat: si falla un canal (o los dos), se avisa por consola y se sigue.

⚠️ win11toast usa winrt, que si se carga en el mismo proceso ANTES que onnxruntime (openwakeword,
o el VAD/STT de faster-whisper) provoca un access violation nativo de Windows (visto en pruebas
reales, ver tests/conftest.py). Por eso el núcleo (src/nucleo/servicio.py) corre en su propio
proceso, separado de la voz/UI: nunca importar este módulo desde algo que también use
src.voice.wakeword/vad/stt en el mismo proceso sin probarlo primero.
"""

from win11toast import toast

from src.router.intent_router import MOTOR_OLLAMA
from src.voice.tts import hablar

# No hay un tercer agente "Jarvis": el núcleo avisa proactivamente sin que haya un turno de
# conversación con un agente en particular, así que se le atribuye a Crimson (el agente por
# defecto), con su voz incluida.
APP_ID = "Crimson"


def avisar(titulo: str, mensaje: str, con_voz: bool = True) -> None:
    """Notifica por Windows y, si con_voz, también lo dice en voz alta (con la voz de Crimson)."""
    try:
        toast(titulo, mensaje, app_id=APP_ID)
    except Exception as error:  # noqa: BLE001 - un aviso fallido no debe tumbar el heartbeat
        print(f"[núcleo] no se pudo mostrar la notificación de Windows: {error}")
    if con_voz:
        try:
            hablar(mensaje, motor=MOTOR_OLLAMA)
        except Exception as error:  # noqa: BLE001
            print(f"[núcleo] no se pudo avisar por voz: {error}")
