"""Herramientas de la bóveda que el agente decide usar por sí mismo (tool calling).

En vez de inyectarle fragmentos pasivos, el modelo pide lo que necesita:
leer una nota completa, buscar, o escribir (pendientes, perfil, contactos).
Aquí están las implementaciones que devuelven texto para el modelo; se
registran con su riesgo en src/herramientas/catalogo.py.
"""

import re

from src.obsidian.vault_reader import buscar_en_boveda, leer_nota, listar_rutas_relativas

MAX_CARACTERES_NOTA = 6000


def herramienta_leer_nota(ruta: str) -> str:
    contenido = leer_nota(ruta)
    if contenido is None:
        return f"La nota '{ruta}' no existe. Usa listar_notas para ver las disponibles."
    if not contenido.strip():
        return f"La nota '{ruta}' está vacía."
    if len(contenido) > MAX_CARACTERES_NOTA:
        return contenido[-MAX_CARACTERES_NOTA:] + "\n[nota recortada: se muestran solo las últimas líneas]"
    return contenido


def herramienta_listar_notas() -> str:
    return "\n".join(listar_rutas_relativas()) or "La bóveda está vacía."


def herramienta_buscar(consulta: str) -> str:
    resultados = buscar_en_boveda(consulta)
    if not resultados:
        return f"No encontré nada sobre '{consulta}' en la bóveda."
    return "\n".join(f"[{r.ruta_relativa}]: {r.fragmento}" for r in resultados)


HERRAMIENTAS_DE_ESCRITURA = {"agregar_pendiente", "completar_pendiente", "recordar_sobre_usuario", "guardar_contacto"}

# "Anoté", "marqué", "añadí", "he agregado", "ya quedó guardado", "Listo, anotado"... y también
# las formas naturales que se le piden al guardar un dato ("lo tendré presente"): si las dice
# sin haber llamado la herramienta, está afirmando algo que no hizo (pasó en pruebas reales).
# El participio solo cuenta como afirmación, no como descripción: al leer los pendientes decía
# "un pendiente agregado el 27" (la fecha de la nota) y se tomaba como un cambio no hecho.
_VERBOS_DE_CAMBIO = r"(agreg|añad|anot|apunt|guard|marc|marqu|complet|registr|elimin|borr)"
_AFIRMA_CAMBIO = re.compile(
    rf"\b{_VERBOS_DE_CAMBIO}(u?é|í)\b"
    rf"|(\b(he|ha|hemos|ya|qued[óoa]n?|está|están|fue|listo,?)\s+|(^|[.!?¡]\s*)(\w+\s+)?){_VERBOS_DE_CAMBIO}[ai]d[oa]s?\b"
    r"|\blo tendré (presente|en cuenta)\b|\blo recordaré\b|\bno lo olvidaré\b",
    re.IGNORECASE,
)

MENSAJE_VERIFICACION = (
    "Verificación del sistema: en este turno no ejecutaste ninguna herramienta de escritura, así que ese "
    "cambio NO se hizo en la bóveda. Si el usuario pidió un cambio, llama ahora la herramienta correcta. "
    "Si no pidió ningún cambio, responde de nuevo sin afirmar que hiciste algo."
)


def afirma_cambio_sin_hacerlo(texto: str, herramientas_usadas: list[str]) -> bool:
    """True si el modelo dice haber cambiado la bóveda sin haber llamado ninguna herramienta de escritura.

    Los modelos pequeños, después de ver en el historial un "He agregado...",
    tienden a repetir la frase sin llamar la herramienta (pasó en pruebas reales).
    """
    return bool(_AFIRMA_CAMBIO.search(texto)) and not HERRAMIENTAS_DE_ESCRITURA.intersection(herramientas_usadas)
