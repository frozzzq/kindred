"""El contexto que acompaña cada mensaje: qué hora es, qué tiene pendiente y qué notas vienen al caso.

Antes el agente tenía que llamar a leer_nota o buscar_en_boveda para enterarse de algo, y cada
llamada es otra vuelta completa del modelo (~1-2 s más por respuesta). Ahora se le da de entrada
lo que probablemente necesita: puede responder "¿qué tengo hoy?" o "¿qué sabes de Node.js?" en una
sola vuelta, y las herramientas quedan para cuando necesita más.

Va al final del mensaje del usuario (no en el prompt de sistema) para no romper la caché de
Ollama: el prompt de sistema y el historial quedan idénticos entre turnos y no se re-procesan.
"""

import re
from datetime import datetime, timedelta

from src.agente.conversacion import Conversacion
from src.obsidian import indice
from src.obsidian.herramientas import como_dato
from src.obsidian.tareas import DIAS, cuando, leer_pendientes, resumen_para_contexto
from src.obsidian.texto import normalizar
from src.obsidian.vault_reader import leer_nota
from src.obsidian.vault_writer import RUTA_CONTACTOS, RUTA_PATRONES, RUTA_PENDIENTES, RUTA_PERFIL, RUTA_RECURRENTES

MAX_CARACTERES_FRAGMENTO = 1200
# Ya van en el prompt de sistema o en el resumen de pendientes: repetirlas solo gasta contexto.
# Patrones tampoco: son observaciones sobre el usuario ("suele pedir sus pendientes en la mañana"),
# y en pruebas se colaban como si fueran la respuesta a "¿qué pendientes tengo?".
_YA_INCLUIDAS = frozenset({RUTA_PERFIL, RUTA_CONTACTOS, RUTA_PENDIENTES, RUTA_RECURRENTES, RUTA_PATRONES})
SIN_NOTAS = "Notas de su bóveda relevantes para este mensaje: ninguna. Si te pregunta por una nota o un tema de sus notas, no existe o no habla de eso: díselo, no lo inventes."

INICIO = "[Contexto automático de este momento. Es información para ti: no lo leas en voz alta ni lo menciones si no viene al caso.]"
FIN = "[Fin del contexto]"


def _consulta(texto: str, conversacion: Conversacion | None) -> str:
    """El mensaje, más el anterior del usuario: "¿y qué más dice?" solo tiene sentido con lo previo."""
    if conversacion is None:
        return texto
    anteriores = [m["content"] for m in conversacion.mensajes() if m["role"] == "user"]
    return f"{anteriores[-1]}\n{texto}" if anteriores and len(texto.split()) < 8 else texto


def _notas_relevantes(texto: str, conversacion: Conversacion | None) -> str:
    # Síncrono a propósito: si el usuario acaba de escribir una nota en Obsidian y pregunta por ella,
    # esta misma respuesta ya debe verla. Es incremental (sin cambios: milisegundos; una nota nueva:
    # ~0.3-1 s de embedding) y nunca espera a otra indexación larga que esté en curso.
    indice.actualizar_sin_fallar(esperar=False)
    resultados = indice.contexto_relevante(_consulta(texto, conversacion), k=3, excluir=_YA_INCLUIDAS)
    if not resultados:
        return ""
    bloques = []
    for resultado in resultados:
        titulo = resultado.ruta + (f" > {resultado.encabezado}" if resultado.encabezado else "")
        fragmento = resultado.texto[:MAX_CARACTERES_FRAGMENTO]
        bloques.append(f"[{titulo}]\n{fragmento}")
    return "Notas de su bóveda que parecen relevantes:\n" + como_dato("\n\n".join(bloques))


_DIAS_ATRAS = {"anteayer": 2, "antier": 2, "ayer": 1}


def _diario_mencionado(texto: str, ahora: datetime) -> str:
    """Si pregunta por "ayer" o "anteayer", la nota del diario de ese día (la búsqueda por tema no la encuentra)."""
    from src.nucleo.diario import ruta_diario  # import local: el núcleo importa cosas pesadas que aquí no hacen falta

    normalizado = normalizar(texto)
    for palabra, dias in _DIAS_ATRAS.items():
        if re.search(rf"\b{palabra}\b", normalizado):
            dia = (ahora - timedelta(days=dias)).date()
            try:
                contenido = leer_nota(ruta_diario(dia))
            except (RuntimeError, ValueError):
                return ""
            if contenido:
                return f"Su diario de {palabra} ({dia.isoformat()}):\n" + como_dato(contenido[:MAX_CARACTERES_FRAGMENTO])
            return f"No hay nota de diario de {palabra} ({dia.isoformat()})."
    return ""


def _aviso_proactivo(ahora: datetime) -> str:
    """Solo en el primer mensaje de una conversación: algo que conviene mencionarle si viene al caso."""
    pendientes = leer_pendientes()
    vencidos = [p for p in pendientes if p.vencido(ahora)]
    de_hoy = [p for p in pendientes if p.es_de_hoy(ahora) and not p.vencido(ahora)]
    if not vencidos and not de_hoy:
        return ""
    partes = []
    if vencidos:
        partes.append("tiene vencido: " + "; ".join(f"{p.tarea} ({cuando(p, ahora)})" for p in vencidos[:3]))
    if de_hoy:
        partes.append("para hoy tiene: " + "; ".join(f"{p.tarea} ({cuando(p, ahora)})" for p in de_hoy[:3]))
    return (
        "Es el primer mensaje de esta conversación y " + " y ".join(partes) + ". Después de atender lo que pidió, "
        "puedes mencionárselo en una frase breve y amable (sin regañarlo), solo si no interrumpe lo que está haciendo."
    )


def construir_contexto(texto: str, conversacion: Conversacion | None = None, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    partes = [f"Ahora es {DIAS[ahora.weekday()]} {ahora:%d/%m/%Y}, {ahora:%H:%M}."]
    try:
        partes.append(resumen_para_contexto(ahora))
    except (RuntimeError, ValueError, OSError):
        pass
    diario = _diario_mencionado(texto, ahora)
    if diario:
        partes.append(diario)
    partes.append(_notas_relevantes(texto, conversacion) or SIN_NOTAS)
    if conversacion is not None and not conversacion.mensajes():
        aviso = _aviso_proactivo(ahora)
        if aviso:
            partes.append(aviso)
    return "\n\n".join([INICIO, *partes, FIN])


def mensaje_con_contexto(texto: str, conversacion: Conversacion | None = None, ahora: datetime | None = None) -> str:
    return f"{construir_contexto(texto, conversacion, ahora)}\n\nMensaje del usuario: {texto}"
