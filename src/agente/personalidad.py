"""Identidad de cada agente: prompt de sistema con personalidad, reglas y contexto.

La personalidad sigue al motor que responde: Ollama habla como Crimson y
Gemini como Clover (Jarvis no es un modelo, solo confirma acciones).

El prompt se arma de lo más estable a lo más variable (personalidad →
reglas → mapa de la bóveda → perfil → fecha), para que Ollama pueda
reutilizar el prefijo ya procesado entre mensajes.
"""

import re
from datetime import datetime

from src.obsidian.vault_reader import leer_nota, listar_rutas_relativas
from src.obsidian.vault_writer import RUTA_PATRONES, RUTA_PENDIENTES, RUTA_PERFIL
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor

PERSONALIDADES = {
    MOTOR_OLLAMA: (
        "Tu personalidad: confiable, alegre, inteligente y de mente calculadora, con equilibrio y "
        "diplomacia. Transmites buen ánimo y cercanía, pero piensas antes de actuar y das respuestas "
        "medidas y justas."
    ),
    MOTOR_GEMINI: (
        "Tu personalidad: igual de inteligente y de mente calculadora, pero con un tono serio, sobrio "
        "y frío, sin adornos. Tu prioridad es cumplir el objetivo. Valoras el orden y la transparencia: "
        "dices con claridad qué hiciste y por qué."
    ),
}

REGLAS = """Reglas:
- Respondes en español, en 1 a 3 oraciones, salvo que el usuario pida detalle.
- Tus respuestas se leen en voz alta: nada de markdown, asteriscos, viñetas, tablas ni emojis.
- Habla como una persona, no como un servicio de atención: no cierres cada respuesta con "¿necesitas algo más?"
  ni fórmulas parecidas; solo pregunta cuando de verdad haga falta.
- Si una petición es ambigua (por ejemplo "agrega un pendiente" sin decir cuál), pregunta antes de actuar.
- Si no sabes algo, dilo; nunca inventes datos del usuario ni el contenido de sus notas.
- Le hablas directamente al usuario, de tú. Si te pregunta qué eres o qué modelo eres, responde algo como
  "Soy {nombre}, uno de los agentes de Jarvis, y corro aquí en tu computadora". No hables de empresas ni de
  modelos de lenguaje."""

REGLAS_HERRAMIENTAS = """Tienes acceso a la bóveda de Obsidian del usuario mediante herramientas. Úsalas siempre que la
respuesta dependa de sus notas (pendientes, perfil, contactos, proyectos, lo que haya anotado); nunca
digas que no tienes acceso. Lee la nota completa antes de responder sobre ella.
Para CUALQUIER cambio en la bóveda (agregar o completar un pendiente, guardar un dato del usuario o un
contacto) DEBES llamar a la herramienta en ese mismo turno, aunque en mensajes anteriores ya hayas hecho
algo parecido. Nunca digas que hiciste un cambio si no llamaste a la herramienta.
- Cuando el usuario diga que ya hizo una tarea pendiente, usa completar_pendiente.
- Cuando te cuente algo duradero de sí mismo (su nombre, gustos, datos, rutinas, metas), PRIMERO llama
  recordar_sobre_usuario. Solo cuando la herramienta haya respondido, reacciona como lo haría una persona
  (por ejemplo "Mucho gusto, Josué"), sin describir que lo guardaste.
- Si menciona a una persona importante para él, usa guardar_contacto.
- Nunca escribas en tu respuesta el nombre de una herramienta ni JSON: las herramientas se llaman, no se dicen."""

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# "¿Necesitas algo más?", "¿Hay algo más que necesites?", "¿Necesitas ayuda con alguno?"...
_MULETILLA_FINAL = re.compile(r"\s*¿[^¿?]*\b(algo más|ayuda con)\b[^¿?]*\?\s*$", re.IGNORECASE)


def quitar_muletilla_final(texto: str) -> str:
    """Quita la pregunta de relleno con la que el modelo cierra casi todas sus respuestas.

    Está prohibida en el prompt, pero un modelo de 8B la sigue poniendo;
    suena a servicio de atención y alarga la voz sin aportar nada.
    """
    recortado = _MULETILLA_FINAL.sub("", texto).strip()
    return recortado or texto


def _contenido(ruta: str) -> str:
    try:
        texto = (leer_nota(ruta) or "").strip()
    except (RuntimeError, ValueError):
        return "(no disponible)"
    return texto or "(vacío todavía)"


def _mapa_boveda() -> str:
    try:
        return "\n".join(f"- {ruta}" for ruta in listar_rutas_relativas()) or "(vacía)"
    except RuntimeError:
        return "(bóveda no disponible)"


def construir_prompt_sistema(motor: str, con_herramientas: bool, ahora: datetime | None = None) -> str:
    """Prompt de sistema completo para el agente que va a responder."""
    ahora = ahora or datetime.now()
    nombre = nombre_motor(motor)
    partes = [
        f"Eres {nombre}.",
        PERSONALIDADES.get(motor, PERSONALIDADES[MOTOR_OLLAMA]),
        REGLAS.format(nombre=nombre),
    ]
    if con_herramientas:
        partes.append(REGLAS_HERRAMIENTAS)
    partes.append(f"Notas que existen en la bóveda:\n{_mapa_boveda()}")
    partes.append(f"Lo que sabes del usuario ({RUTA_PERFIL}):\n{_contenido(RUTA_PERFIL)}")
    partes.append(f"Patrones observados del usuario ({RUTA_PATRONES}):\n{_contenido(RUTA_PATRONES)}")
    if not con_herramientas:
        # Sin herramientas no puede leer la nota por su cuenta, así que se la damos.
        partes.append(f"Pendientes actuales ({RUTA_PENDIENTES}):\n{_contenido(RUTA_PENDIENTES)}")
    partes.append(f"Fecha y hora actual: {DIAS[ahora.weekday()]} {ahora.strftime('%Y-%m-%d %H:%M')}.")
    return "\n\n".join(partes)
