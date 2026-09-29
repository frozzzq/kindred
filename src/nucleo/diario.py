"""Diario automático: al cierre de cada día, una nota en 06-Diario con lo que pasó.

Es la memoria episódica del asistente: como queda en la bóveda (y en el índice), después se le
puede preguntar "¿qué hice ayer?" o "¿cuándo terminé lo del padel?". Si el usuario ya escribió su
propia nota del día, no se toca lo suyo: solo se agrega la sección de Crimson al final.
"""

import re
from datetime import date, datetime

from src.engines.ollama_client import preguntar_ollama
from src.obsidian.estructura import CARPETA_DIARIO
from src.obsidian.formato import insertar_antes_de_relacionado
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import RUTA_COMPLETADAS, escribir_nota, ruta_log

SECCION = "## Lo que pasó (resumen de Crimson)"
MAX_CARACTERES_CONVERSACION = 6000
_ACCIONES_DE_NOTAS = ("crear_nota", "agregar_a_nota", "editar_nota", "mover_nota", "conectar_notas", "eliminar_nota")

PROMPT = """Resume en 3 a 5 oraciones, en segunda persona y en español ("hoy estudiaste...", "le preguntaste a \
Crimson..."), lo que hizo el usuario hoy según estas conversaciones con su asistente. Solo lo importante: temas, \
decisiones, cosas que terminó o que quedaron pendientes. Ignora saludos, pruebas del sistema y frases mal \
transcritas. Usa SOLO lo que está abajo; si no hay nada relevante, responde exactamente "Sin conversaciones relevantes."

Conversaciones de hoy:
{conversaciones}"""


def ruta_diario(dia: date) -> str:
    return f"{CARPETA_DIARIO}/{dia.isoformat()}.md"


def _conversaciones(dia: date) -> str:
    contenido = leer_nota(ruta_log(datetime.combine(dia, datetime.min.time()))) or ""
    entradas = [e for e in re.split(r"^(?=### )", contenido, flags=re.MULTILINE) if e.startswith(f"### {dia.isoformat()}")]
    return "\n".join(entradas)[-MAX_CARACTERES_CONVERSACION:]


def _completadas(dia: date) -> list[str]:
    completadas = []
    for linea in (leer_nota(RUTA_COMPLETADAS) or "").splitlines():
        if f"(completado {dia.isoformat()}" in linea:
            completadas.append(re.sub(r"\s*\((agregado|completado)[^)]*\)", "", linea.removeprefix("- [x] ")).strip())
    return completadas


def _notas_tocadas(dia: date) -> list[str]:
    registro = leer_nota("00-Sistema/Registro-Acciones.md") or ""
    tocadas = []
    for linea in registro.splitlines():
        if not linea.startswith(f"- {dia.isoformat()}") or not any(f"`{a}`" in linea for a in _ACCIONES_DE_NOTAS):
            continue
        coincidencia = re.search(r"→ (Nota creada: [^.]+|Agregué el texto a [^.]+|Actualicé [^ ]+|Moví la nota a [^.]+)", linea)
        if coincidencia:
            tocadas.append(coincidencia.group(1))
    return tocadas


def escribir_diario(dia: date | None = None) -> str | None:
    """Escribe (o completa) la nota del día. Devuelve su ruta, o None si no hubo nada que anotar."""
    dia = dia or date.today()
    conversaciones = _conversaciones(dia)
    completadas = _completadas(dia)
    tocadas = _notas_tocadas(dia)
    if not (conversaciones or completadas or tocadas):
        return None

    partes = []
    if conversaciones:
        respuesta = preguntar_ollama(PROMPT.format(conversaciones=conversaciones))
        if respuesta.exito and respuesta.texto.strip() and "Sin conversaciones relevantes" not in respuesta.texto:
            partes.append(respuesta.texto.strip())
    if completadas:
        partes.append("Terminaste:\n" + "\n".join(f"- {c}" for c in completadas))
    if tocadas:
        partes.append("En tus notas:\n" + "\n".join(f"- {t}" for t in tocadas))
    if not partes:
        return None

    ruta = ruta_diario(dia)
    actual = leer_nota(ruta) or f"---\nfecha: {dia.isoformat()}\n---\n"
    if SECCION in actual:
        return ruta  # ya se escribió hoy
    escribir_nota(ruta, insertar_antes_de_relacionado(actual, SECCION + "\n" + "\n\n".join(partes)), sobrescribir=True)
    return ruta
