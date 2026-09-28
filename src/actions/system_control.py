"""Acciones sobre el sistema: abrir aplicaciones, hacer click y escribir texto.

Fase 4: los clicks buscan el control por su texto visible en la ventana
activa (API de accesibilidad de Windows, vía pywinauto) — no por
coordenadas de píxel, para que no dependa de la resolución ni de dónde
esté la ventana en pantalla. Funciona bien en apps nativas de Windows
(Explorador, Notepad, la mayoría de programas de escritorio); en apps con
widgets dibujados a mano (ej. Tkinter) o algunas apps web, los controles
pueden no tener nombre accesible y no encontrarse — se avisa en vez de
fallar en silencio.
"""

import os
import time
from dataclasses import dataclass

import win32clipboard
import win32gui
from pywinauto import Desktop

# Alias en español -> comando real para abrir la app en Windows (via
# os.startfile, que resuelve nombres registrados en "App Paths").
# Se puede ampliar sin tocar el resto del sistema.
APLICACIONES_CONOCIDAS = {
    "calculadora": "calc.exe",
    "bloc de notas": "notepad.exe",
    "block de notas": "notepad.exe",  # transcripción común de "bloc" via STT
    "notas": "notepad.exe",
    "explorador": "explorer.exe",
    "explorador de archivos": "explorer.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "navegador": "chrome.exe",
    "spotify": "spotify.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "paint": "mspaint.exe",
    "terminal": "wt.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
}

SIGNOS_A_QUITAR = " .,;:!¡?¿'\""


@dataclass
class ResultadoAccion:
    exito: bool
    mensaje: str


def abrir_aplicacion(nombre: str) -> ResultadoAccion:
    """Abre una aplicación conocida por su nombre en español.

    Solo abre aplicaciones de una lista blanca fija (APLICACIONES_CONOCIDAS);
    cualquier otra cosa se rechaza en vez de intentar ejecutar algo arbitrario.
    Quita signos de puntuación sueltos (Whisper suele agregarlos al transcribir).
    """
    clave = nombre.strip(SIGNOS_A_QUITAR).lower()
    comando = APLICACIONES_CONOCIDAS.get(clave)
    if not comando:
        return ResultadoAccion(exito=False, mensaje=f"No conozco ninguna aplicación llamada '{nombre}'.")

    try:
        os.startfile(comando)
    except OSError as error:
        return ResultadoAccion(exito=False, mensaje=f"No se pudo abrir {nombre}: {error}")

    return ResultadoAccion(exito=True, mensaje=f"Abriendo {nombre}...")


def _ventana_activa():
    """La ventana con la que el usuario está interactuando en este instante, o None si no hay ninguna."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    return Desktop(backend="uia").window(handle=hwnd)


def hacer_click(texto_boton: str) -> ResultadoAccion:
    """Busca un control (botón, casilla, pestaña...) con ese texto en la ventana activa y le hace click.

    Recorre el árbol de accesibilidad de la ventana en primer plano
    buscando una coincidencia exacta (o, si no hay, parcial) con el texto
    visible del control. No usa coordenadas de píxel, así que no depende
    de la resolución ni de dónde esté la ventana.
    """
    objetivo = texto_boton.strip(SIGNOS_A_QUITAR).lower()
    if not objetivo:
        return ResultadoAccion(exito=False, mensaje="No entendí en qué quieres que haga click.")

    try:
        ventana = _ventana_activa()
        if ventana is None:
            return ResultadoAccion(exito=False, mensaje="No detecté ninguna ventana activa.")
        candidatos = ventana.descendants()
    except Exception as error:  # noqa: BLE001 - la ventana activa puede ser cualquier app; nunca debe crashear
        return ResultadoAccion(exito=False, mensaje=f"No pude leer la ventana activa: {error}")

    coincidencia = None
    for control in candidatos:
        try:
            texto_control = control.window_text().strip().lower()
        except Exception:  # noqa: BLE001
            continue
        if not texto_control:
            continue
        if texto_control == objetivo:
            coincidencia = control
            break
        if coincidencia is None and objetivo in texto_control:
            coincidencia = control  # coincidencia parcial; se sigue buscando una exacta

    if coincidencia is None:
        return ResultadoAccion(exito=False, mensaje=f"No encontré nada llamado '{texto_boton}' en la ventana activa.")

    try:
        coincidencia.click_input()
    except Exception as error:  # noqa: BLE001
        return ResultadoAccion(exito=False, mensaje=f"Encontré '{texto_boton}' pero no pude hacerle click: {error}")

    return ResultadoAccion(exito=True, mensaje=f"Hice click en '{texto_boton}'.")


def _leer_portapapeles() -> str | None:
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    except TypeError:
        return None  # el portapapeles tenía algo que no es texto (ej. una imagen copiada)
    finally:
        win32clipboard.CloseClipboard()


def _escribir_portapapeles(texto: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(texto, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def escribir_texto(texto: str) -> ResultadoAccion:
    """Escribe el texto donde esté el foco en este momento, en la ventana activa.

    Lo hace pegando desde el portapapeles (copiar y pegar) en vez de
    simular cada tecla, para no tener que escapar los caracteres que
    pywinauto interpreta de forma especial (+^%~(){}) si aparecen en el
    texto dictado. Restaura el contenido anterior del portapapeles al terminar.
    """
    if not texto.strip():
        return ResultadoAccion(exito=False, mensaje="No entendí qué quieres que escriba.")

    ventana = _ventana_activa()
    if ventana is None:
        return ResultadoAccion(exito=False, mensaje="No detecté ninguna ventana activa.")

    anterior = _leer_portapapeles()
    try:
        _escribir_portapapeles(texto)
        ventana.type_keys("^v")
        time.sleep(0.1)
    except Exception as error:  # noqa: BLE001 - nunca debe crashear la respuesta del agente
        return ResultadoAccion(exito=False, mensaje=f"No pude escribir el texto: {error}")
    finally:
        if anterior is not None:
            try:
                _escribir_portapapeles(anterior)
            except Exception:  # noqa: BLE001 - restaurar el portapapeles es cortesía, no crítico
                pass

    return ResultadoAccion(exito=True, mensaje="Listo, ya lo escribí.")
