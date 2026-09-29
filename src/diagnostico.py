"""Diagnóstico: revisa que todo lo que necesitan Crimson y Clover esté en orden, y dice cómo arreglarlo.

Lo usan el lanzador (opción "Diagnóstico") y el panel de estado de la UI.
Uso: python -m src.diagnostico
"""

import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src.consola import forzar_utf8

TIMEOUT = 3


@dataclass(frozen=True)
class Chequeo:
    nombre: str
    ok: bool | None  # None: funciona, pero con un aviso
    detalle: str
    solucion: str = ""


def _host() -> str:
    return os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def revisar_boveda() -> Chequeo:
    ruta = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not ruta:
        return Chequeo("Bóveda", False, "OBSIDIAN_VAULT_PATH no está configurada", "Agrégala al .env")
    if not Path(ruta).is_dir():
        return Chequeo("Bóveda", False, f"No existe la carpeta {ruta}", "Revisa OBSIDIAN_VAULT_PATH en el .env")
    notas = sum(1 for _ in Path(ruta).rglob("*.md"))
    return Chequeo("Bóveda", True, f"{ruta} · {notas} notas")


def revisar_ollama() -> list[Chequeo]:
    from src.engines.embeddings import modelo_embeddings

    modelo = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    try:
        instalados = {m["name"] for m in httpx.get(f"{_host()}/api/tags", timeout=TIMEOUT).json()["models"]}
        cargados = {m["name"]: m.get("size_vram", 0) for m in httpx.get(f"{_host()}/api/ps", timeout=TIMEOUT).json()["models"]}
    except (httpx.HTTPError, KeyError, ValueError):
        return [Chequeo("Ollama", False, f"No responde en {_host()}", "Abre Ollama (o revisa OLLAMA_HOST en el .env)")]
    chequeos = [Chequeo("Ollama", True, f"Responde en {_host()}")]
    if modelo not in instalados:
        chequeos.append(Chequeo("Modelo de Crimson", False, f"{modelo} no está instalado", f"ollama pull {modelo}"))
    elif modelo in cargados:
        chequeos.append(Chequeo("Modelo de Crimson", True, f"{modelo} cargado en la GPU ({cargados[modelo] / 1e9:.1f} GB)"))
    else:
        chequeos.append(Chequeo("Modelo de Crimson", None, f"{modelo} instalado pero no cargado", "Se carga solo con el primer mensaje (~30 s)"))
    embebedor = modelo_embeddings()
    if embebedor not in instalados:
        chequeos.append(
            Chequeo("Memoria semántica", None, f"Falta {embebedor}: la búsqueda será solo por palabras", f"ollama pull {embebedor}")
        )
    else:
        chequeos.append(Chequeo("Memoria semántica", True, f"{embebedor} instalado"))
    return chequeos


def revisar_gemini() -> Chequeo:
    if not os.getenv("GEMINI_API_KEY"):
        return Chequeo("Clover (Gemini)", False, "Falta GEMINI_API_KEY", "Agrégala al .env (Google AI Studio)")
    return Chequeo("Clover (Gemini)", True, f"Clave configurada · modelo {os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')}")


def revisar_indice() -> Chequeo:
    try:
        from src.obsidian import indice

        estado = indice.estado()
    except (RuntimeError, OSError) as error:
        return Chequeo("Índice de la bóveda", False, str(error))
    if estado.notas == 0:
        return Chequeo("Índice de la bóveda", None, "Vacío todavía", "Se llena solo al abrir la UI o con el núcleo")
    if estado.sin_vector:
        return Chequeo(
            "Índice de la bóveda", None, f"{estado.notas} notas · {estado.sin_vector} fragmentos sin vector (solo por palabras)",
            "Se completan solos cuando el modelo de embeddings responde",
        )
    return Chequeo("Índice de la bóveda", True, f"{estado.notas} notas · {estado.fragmentos} fragmentos con búsqueda semántica")


def revisar_nucleo() -> Chequeo:
    from src.nucleo.proceso import esta_vivo, segundos_desde_ultima_vuelta

    if esta_vivo():
        return Chequeo("Núcleo (recordatorios)", True, f"Vivo · última vuelta hace {int(segundos_desde_ultima_vuelta())} s")
    return Chequeo("Núcleo (recordatorios)", None, "No está corriendo: no llegarán avisos", "Inícialo desde la UI o el lanzador")


def revisar_microfono() -> Chequeo:
    try:
        import sounddevice as sd

        dispositivo = sd.query_devices(kind="input")
    except Exception as error:  # noqa: BLE001 - cualquier fallo de audio es solo un diagnóstico
        return Chequeo("Micrófono", False, f"No se encontró: {error}", "Conecta un micrófono o revisa los permisos de Windows")
    return Chequeo("Micrófono", True, dispositivo["name"])


def revisar_voz() -> Chequeo:
    from src import ajustes
    from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA
    from src.voice.tts import _sintetizar_edge_tts

    audio = _sintetizar_edge_tts("Prueba.", MOTOR_OLLAMA)
    if audio is None:
        return Chequeo("Voz (edge-tts)", False, "No se pudo sintetizar", "Revisa la conexión a internet")
    return Chequeo("Voz (edge-tts)", True, f"Crimson: {ajustes.voz_de(MOTOR_OLLAMA)} · Clover: {ajustes.voz_de(MOTOR_GEMINI)}")


def todos(con_audio: bool = True) -> list[Chequeo]:
    chequeos = [revisar_boveda(), *revisar_ollama(), revisar_gemini(), revisar_indice(), revisar_nucleo()]
    if con_audio:
        chequeos += [revisar_microfono(), revisar_voz()]
    return chequeos


def main() -> None:
    forzar_utf8()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
    print("Diagnóstico de Crimson y Clover\n")
    for chequeo in todos():
        marca = {True: "✓", False: "✗", None: "!"}[chequeo.ok]
        print(f" {marca} {chequeo.nombre:26s} {chequeo.detalle}")
        if chequeo.solucion and chequeo.ok is not True:
            print(f"   {'':26s} → {chequeo.solucion}")


if __name__ == "__main__":
    main()
