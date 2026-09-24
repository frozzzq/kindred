"""Conecta la boveda con el flujo de conversacion: arma contexto para los
prompts y decide que guardar/actualizar despues de cada respuesta relevante.
"""

from src.obsidian.vault_reader import buscar_en_boveda
from src.obsidian.vault_writer import agregar_pendiente, registrar_interaccion

PALABRAS_CLAVE_PENDIENTE = ("recuérdame", "recuerdame", "pendiente", "anota", "agenda")


def construir_contexto(texto: str) -> str:
    """Devuelve un bloque de contexto con fragmentos relevantes de la bóveda.

    Devuelve cadena vacía si no hay bóveda configurada o no hay coincidencias,
    para que el flujo principal nunca dependa de que Obsidian esté disponible.
    """
    try:
        resultados = buscar_en_boveda(texto)
    except RuntimeError:
        return ""

    if not resultados:
        return ""

    bloques = [f"[{r.ruta_relativa}]: {r.fragmento}" for r in resultados]
    return "Contexto relevante de tu bóveda de notas:\n" + "\n".join(bloques)


def evaluar_guardado(texto: str, respuesta: str, motor: str) -> None:
    """Registra la interacción y, si aplica, agrega un pendiente a la bóveda."""
    try:
        registrar_interaccion(texto, respuesta, motor)
        texto_normalizado = texto.lower()
        if any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE_PENDIENTE):
            agregar_pendiente(texto)
    except RuntimeError:
        pass
