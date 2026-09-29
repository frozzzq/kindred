"""Embeddings locales con Ollama: convierten un texto en un vector que representa su significado.

Dos textos que hablan de lo mismo con otras palabras ("JS del lado del servidor" y "Node.js")
quedan cerca; es lo que permite buscar por tema y conectar notas que de verdad se relacionan.

El modelo corre en CPU (num_gpu=0): en GPU competiría por la VRAM con el modelo de chat y Ollama
podría descargar a qwen3:8b, que luego tarda segundos en volver a cargarse. En CPU, una consulta
tarda ~0.3s (medido con qwen3-embedding:0.6b).

Si Ollama o el modelo no están disponibles, devuelve None y el resto del sistema sigue con
búsqueda por palabras. Tras un fallo se deja de intentar un rato, para no sumarle un timeout a
cada respuesta.
"""

import os
import time

import httpx
import numpy as np

MODELO_POR_DEFECTO = "qwen3-embedding:0.6b"
# Qwen3-Embedding recomienda instrucción en las consultas (no en los documentos), en inglés.
INSTRUCCION_CONSULTA = "Instruct: Given a user's question, retrieve the personal notes that answer it\nQuery: "
TAMANO_LOTE = 16
TIMEOUT_LOTE = 120
TIMEOUT_CONSULTA = 8
SEGUNDOS_SIN_REINTENTAR = 60
KEEP_ALIVE = "3h"

_fallo_hasta = 0.0


def modelo_embeddings() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", MODELO_POR_DEFECTO)


def disponible() -> bool:
    return time.monotonic() >= _fallo_hasta


def _marcar_fallo() -> None:
    global _fallo_hasta
    _fallo_hasta = time.monotonic() + SEGUNDOS_SIN_REINTENTAR


def _pedir(textos: list[str], timeout: float) -> np.ndarray | None:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    cuerpo = {
        "model": modelo_embeddings(),
        "input": textos,
        "keep_alive": KEEP_ALIVE,
        "truncate": True,
        "options": {"num_gpu": 0},
    }
    try:
        respuesta = httpx.post(f"{host}/api/embed", json=cuerpo, timeout=timeout)
        respuesta.raise_for_status()
        vectores = np.asarray(respuesta.json()["embeddings"], dtype=np.float32)
    except (httpx.HTTPError, KeyError, ValueError):
        _marcar_fallo()
        return None
    if vectores.ndim != 2 or len(vectores) != len(textos):
        _marcar_fallo()
        return None
    normas = np.linalg.norm(vectores, axis=1, keepdims=True)
    return vectores / np.maximum(normas, 1e-9)


def embeber(textos: list[str]) -> np.ndarray | None:
    """Vectores normalizados (una fila por texto), o None si no se pudo."""
    if not textos:
        return np.zeros((0, 0), dtype=np.float32)
    if not disponible():
        return None
    partes = []
    for inicio in range(0, len(textos), TAMANO_LOTE):
        lote = _pedir(textos[inicio : inicio + TAMANO_LOTE], TIMEOUT_LOTE)
        if lote is None:
            return None
        partes.append(lote)
    return np.vstack(partes)


def embeber_consulta(consulta: str) -> np.ndarray | None:
    """Vector de una pregunta del usuario (con la instrucción que el modelo espera para consultas)."""
    if not disponible():
        return None
    vectores = _pedir([INSTRUCCION_CONSULTA + consulta], TIMEOUT_CONSULTA)
    return None if vectores is None else vectores[0]
