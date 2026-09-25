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
    recordar_sobre_usuario,
    ya_esta_anotado,
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

Ignora pruebas del sistema, preguntas de cultura general, frases sin sentido o mal transcritas, y cualquier cosa que el asistente haya dicho pero el usuario no. Si no hay nada nuevo y seguro, devuelve listas vacías. Cada elemento es una oración corta en español y en tercera persona (por ejemplo "Se llama Josué", "Le gusta el café"), nunca en primera persona.

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
    nuevos: list[str] = []
    for candidato in candidatos:
        if not isinstance(candidato, str) or not candidato.strip():
            continue
        if ya_esta_anotado(candidato, existente + "\n" + "\n".join(nuevos)):
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


def _extraer_y_anotar(interacciones: list[str], incluir_patrones: bool) -> list[str]:
    """Le pide al modelo lo aprendido de estas interacciones y anota lo que sea nuevo."""
    perfil = (leer_nota(RUTA_PERFIL) or "").strip()
    patrones = (leer_nota(RUTA_PATRONES) or "").strip()
    prompt = PROMPT_REFLEXION.format(
        perfil=perfil or "(vacío)",
        patrones=patrones or "(vacío)",
        interacciones="\n\n".join(interacciones),
    )
    respuesta = preguntar_ollama(prompt, formato="json")
    if not respuesta.exito:
        return []
    try:
        datos = json.loads(respuesta.texto)
    except json.JSONDecodeError:
        return []
    if not isinstance(datos, dict):
        return []

    resultados = [recordar_sobre_usuario(dato) for dato in _nuevos(datos.get("datos_usuario", []), perfil)]
    if incluir_patrones:
        resultados += [anotar_patron(patron) for patron in _nuevos(datos.get("patrones", []), patrones)]
    # Otro hilo (el agente o una extracción) pudo haberlo anotado mientras tanto.
    return [r for r in resultados if not r.startswith("Ya estaba")]


def reflexionar() -> list[str]:
    """Revisa las interacciones nuevas y anota lo aprendido. Devuelve lo anotado."""
    entradas = _entradas_log()
    ultima = int(_leer_config().get(CLAVE_ULTIMA_REFLEXION, len(entradas)))
    nuevas = [e for e in entradas[ultima:] if f"({MOTOR_GEMINI_FALLO})" not in e.splitlines()[0]]
    nuevas = nuevas[-MAX_INTERACCIONES_POR_REFLEXION:]

    anotado = _extraer_y_anotar(nuevas, incluir_patrones=True) if nuevas else []
    _guardar_config(CLAVE_ULTIMA_REFLEXION, str(len(entradas)))
    return anotado


# "me llamo", "mi nombre es", "me gusta", "vivo en", "trabajo en", "tengo 25 años"...
_PARECE_DATO_PERSONAL = re.compile(
    r"\b(me llamo|mi nombre es|me gustan?|me encantan?|odio|no me gusta|prefiero|soy de|vivo en|"
    r"trabajo (en|como|de)|estudio|mi cumpleaños|nac[íi]|tengo \d+ años|mi (esposa|esposo|novia|novio|"
    r"mamá|papá|hermana|hermano|hijo|hija|perro|gato))\b",
    re.IGNORECASE,
)


def aprender_si_quedo_sin_guardar(texto_usuario: str, herramientas_usadas: list[str]) -> None:
    """Red de seguridad: si el usuario contó algo personal y el agente no lo guardó, se extrae ya.

    En pruebas reales el modelo a veces respondía "Mucho gusto, Josué" sin
    llamar a recordar_sobre_usuario. Esperar a la reflexión (cada 10
    interacciones) sería demasiado tarde para algo como su nombre. Corre en
    segundo plano, sin sumar latencia; tampoco Gemini tiene herramientas,
    así que esto es lo que le permite aprender a Clover.
    """
    if "recordar_sobre_usuario" in herramientas_usadas or not _PARECE_DATO_PERSONAL.search(texto_usuario):
        return

    def trabajo() -> None:
        try:
            _extraer_y_anotar([f"**Usuario:** {texto_usuario}"], incluir_patrones=False)
        except (RuntimeError, ValueError, OSError):
            pass

    threading.Thread(target=trabajo, daemon=True).start()


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
