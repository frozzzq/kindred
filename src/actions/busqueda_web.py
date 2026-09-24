"""Búsqueda web auxiliar, independiente del motor que vaya a responder.

Gemini ya tiene su propio grounding con Google Search (ver
engines/gemini_client.py), pero Ollama no tiene forma nativa de acceder a
internet. Este módulo usa DuckDuckGo (sin API key, sin costo) para darle a
Ollama resultados reales como contexto — típicamente se usa cuando Gemini
falla (ej. sin facturación configurada) y el router cae a Ollama para una
pregunta que necesitaba buscar en internet.
"""

from dataclasses import dataclass

from ddgs import DDGS

MAX_RESULTADOS = 4


@dataclass
class ResultadoBusquedaWeb:
    titulo: str
    fragmento: str
    url: str


def buscar_en_internet(consulta: str, max_resultados: int = MAX_RESULTADOS) -> list[ResultadoBusquedaWeb]:
    """Busca en internet vía DuckDuckGo. Lista vacía si falla, no crashea."""
    try:
        with DDGS() as motor:
            resultados = motor.text(consulta, max_results=max_resultados)
    except Exception:  # noqa: BLE001 - la búsqueda es auxiliar, nunca debe tumbar la respuesta
        return []

    return [
        ResultadoBusquedaWeb(
            titulo=r.get("title", ""),
            fragmento=r.get("body", ""),
            url=r.get("href", ""),
        )
        for r in resultados
    ]


def construir_contexto_web(consulta: str) -> str:
    """Arma un bloque de texto con resultados reales para inyectar en el prompt."""
    resultados = buscar_en_internet(consulta)
    if not resultados:
        return ""

    bloques = [f"- {r.titulo}: {r.fragmento} ({r.url})" for r in resultados]
    return "Resultados de una búsqueda real en internet ahora mismo:\n" + "\n".join(bloques)
