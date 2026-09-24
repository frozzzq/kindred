"""Acciones sobre el sistema: abrir aplicaciones conocidas.

Fase 4: solo abrir aplicaciones por ahora. Clicks/escritura automática
quedan para una iteración futura de esta fase.
"""

import os
from dataclasses import dataclass

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
