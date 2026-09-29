"""Le devuelve el foco a la última ventana externa (que no es de Jarvis) antes de una acción de
pantalla (click o escribir texto), si la ventana activa en ese momento resulta ser la propia UI o
consola de Jarvis.

Sin esto: si le hablas a Jarvis por el micrófono de la UI, o le escribes en el chat, ese clic deja
a la propia ventana de Jarvis como "ventana activa" — y un "escribe X"/"haz click en Y" terminaría
apuntando a la UI en vez de, por ejemplo, el Bloc de notas. Peor: al ser de Flet, la UI no tiene un
árbol de accesibilidad normal, así que pywinauto se queda leyéndola sin límite de tiempo (visto en
pruebas reales: "se queda pensando y no hace nada").

Un hilo de fondo va recordando cuál fue la última ventana activa que no es nuestra, para poder
restaurársela justo antes de actuar.
"""

import os
import threading
import time

import win32api
import win32con
import win32gui
import win32process

INTERVALO_RASTREO_SEGUNDOS = 0.3

_pid_propio = os.getpid()
_ultima_ventana_externa: int | None = None
_bloqueo = threading.Lock()
_rastreo_iniciado = False


def _es_ventana_propia(hwnd: int) -> bool:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:  # noqa: BLE001 - una ventana puede cerrarse justo al consultarla
        return False
    return pid == _pid_propio


def _rastrear() -> None:
    global _ultima_ventana_externa
    while True:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd and not _es_ventana_propia(hwnd):
                with _bloqueo:
                    _ultima_ventana_externa = hwnd
        except Exception:  # noqa: BLE001 - el rastreo nunca debe morirse
            pass
        time.sleep(INTERVALO_RASTREO_SEGUNDOS)


def iniciar_rastreo() -> None:
    """Arranca el hilo que recuerda la última ventana externa. Se llama una vez al iniciar la UI."""
    global _rastreo_iniciado
    with _bloqueo:
        if _rastreo_iniciado:
            return
        _rastreo_iniciado = True
    threading.Thread(target=_rastrear, daemon=True, name="rastreo-ventana-externa").start()


def _traer_al_frente(hwnd: int) -> None:
    """SetForegroundWindow puede fallar si Windows cree que nadie lo pidió; simular una tecla lo
    destraba (mismo truco ya usado en otras partes del proyecto)."""
    win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.15)  # dar tiempo a que el cambio de foco se aplique de verdad


def ventana_objetivo() -> int | None:
    """La ventana a la que debe apuntar una acción de pantalla (click o escribir texto).

    Si la ventana activa ahora mismo es la propia UI/consola de Jarvis, le devuelve el foco a la
    última ventana externa conocida antes de actuar. None si no hay ninguna ventana activa, o si
    Jarvis es la única ventana que se ha visto activa (nunca se detectó ninguna otra).
    """
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    if not _es_ventana_propia(hwnd):
        return hwnd

    with _bloqueo:
        externa = _ultima_ventana_externa
    if not externa or not win32gui.IsWindow(externa):
        return None

    try:
        _traer_al_frente(externa)
    except Exception:  # noqa: BLE001 - si no se pudo destrabar el foco, se sigue con lo que haya
        pass
    return externa
