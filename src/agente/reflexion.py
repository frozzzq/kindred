"""Reflexión periódica: aprende del historial y actualiza Yo.md y Patrones.md.

Cada CADA_N_INTERACCIONES nuevas en el log, el modelo las revisa y extrae
datos duraderos del usuario y patrones de uso. Corre en segundo plano para
no sumar latencia a la conversación.

La primera vez solo marca el punto de partida (no procesa el historial
previo), porque el log viejo está lleno de pruebas y transcripciones
erróneas de las que no conviene "aprender".
"""

import json
import re
import threading

from src.engines.ollama_client import preguntar_ollama
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import (
    RUTA_LOG,
    RUTA_PATRONES,
    RUTA_PERFIL,
    anotar_patron,
    escribir_nota,
    normalizar,
    recordar_sobre_usuario,
)
from src.router.intent_router import MOTOR_GEMINI_FALLO

RUTA_CONFIG = "00-Sistema/Configuracion.md"
CLAVE_ULTIMA_REFLEXION = "ultima_reflexion"
CADA_N_INTERACCIONES = 10
MAX_INTERACCIONES_POR_REFLEXION = 30

_en_curso = threading.Lock()

PROMPT_REFLEXION = """Analiza estas interacciones recientes entre un usuario y su asistente personal.

Perfil actual del usuario (no repitas nada de aquí):
{perfil}

Patrones ya anotados (no repitas nada de aquí):
{patrones}

Interacciones:
{interacciones}

Extrae SOLO:
- "datos_usuario": hechos duraderos que el usuario haya dicho explícitamente sobre sí mismo (gustos, datos personales, rutinas, metas, personas cercanas).
- "patrones": hábitos o tendencias que aparezcan en al menos 3 interacciones distintas (horarios, tipo de peticiones frecuentes, temas recurrentes). Si algo pasó una o dos veces, NO es un patrón.

Ignora pruebas del sistema, preguntas de cultura general, frases sin sentido o mal transcritas, y cualquier cosa que el asistente haya dicho pero el usuario no. Si no hay nada nuevo y seguro, devuelve listas vacías. Cada elemento es una oración corta en español.

Responde solo con JSON: {{"datos_usuario": [...], "patrones": [...]}}"""


def _leer_config() -> dict[str, str]:
    contenido = leer_nota(RUTA_CONFIG) or ""
    config = {}
    for linea in contenido.splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            config[clave.strip()] = valor.strip()
    return config


def _guardar_config(clave: str, valor: str) -> None:
    config = _leer_config() | {clave: valor}
    escribir_nota(RUTA_CONFIG, "\n".join(f"{k}: {v}" for k, v in config.items()) + "\n", sobrescribir=True)


def _entradas_log() -> list[str]:
    """Entradas del log (cada una empieza con '### fecha (motor)')."""
    contenido = leer_nota(RUTA_LOG) or ""
    return [e.strip() for e in re.split(r"^(?=### )", contenido, flags=re.MULTILINE) if e.strip()]


def _nuevos(candidatos: list, existente: str) -> list[str]:
    """Filtra lo que ya está anotado (el modelo repite datos aunque se le pida no hacerlo)."""
    ya_anotado = normalizar(existente)
    nuevos: list[str] = []
    for candidato in candidatos:
        if not isinstance(candidato, str) or not candidato.strip():
            continue
        clave = normalizar(candidato.strip().rstrip("."))
        if clave in ya_anotado or any(clave in normalizar(n) for n in nuevos):
            continue
        nuevos.append(candidato.strip())
    return nuevos


def debe_reflexionar() -> bool:
    total = len(_entradas_log())
    config = _leer_config()
    if CLAVE_ULTIMA_REFLEXION not in config:
        _guardar_config(CLAVE_ULTIMA_REFLEXION, str(total))
        return False
    return total - int(config[CLAVE_ULTIMA_REFLEXION]) >= CADA_N_INTERACCIONES


def reflexionar() -> list[str]:
    """Revisa las interacciones nuevas y anota lo aprendido. Devuelve lo anotado."""
    entradas = _entradas_log()
    ultima = int(_leer_config().get(CLAVE_ULTIMA_REFLEXION, len(entradas)))
    nuevas = [e for e in entradas[ultima:] if f"({MOTOR_GEMINI_FALLO})" not in e.splitlines()[0]]
    nuevas = nuevas[-MAX_INTERACCIONES_POR_REFLEXION:]

    anotado: list[str] = []
    if nuevas:
        perfil = (leer_nota(RUTA_PERFIL) or "").strip()
        patrones = (leer_nota(RUTA_PATRONES) or "").strip()
        prompt = PROMPT_REFLEXION.format(
            perfil=perfil or "(vacío)",
            patrones=patrones or "(vacío)",
            interacciones="\n\n".join(nuevas),
        )
        respuesta = preguntar_ollama(prompt, formato="json")
        if respuesta.exito:
            try:
                datos = json.loads(respuesta.texto)
            except json.JSONDecodeError:
                datos = {}
            if not isinstance(datos, dict):
                datos = {}
            for dato in _nuevos(datos.get("datos_usuario", []), perfil):
                anotado.append(recordar_sobre_usuario(dato))
            for patron in _nuevos(datos.get("patrones", []), patrones):
                anotado.append(anotar_patron(patron))

    _guardar_config(CLAVE_ULTIMA_REFLEXION, str(len(entradas)))
    return anotado


def reflexionar_si_toca() -> None:
    """Lanza la reflexión en segundo plano si ya se acumularon suficientes interacciones."""

    def trabajo() -> None:
        if not _en_curso.acquire(blocking=False):
            return
        try:
            if debe_reflexionar():
                reflexionar()
        except (RuntimeError, ValueError, OSError):
            pass  # la reflexión es un extra; si falla, la conversación sigue igual
        finally:
            _en_curso.release()

    threading.Thread(target=trabajo, daemon=True).start()
