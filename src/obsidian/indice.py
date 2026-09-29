"""Memoria semántica de la bóveda: índice híbrido (significado + palabras clave) de todas las notas.

Cada nota se parte en fragmentos (por encabezado y párrafos) y cada fragmento se guarda con su
embedding (src/engines/embeddings.py) en un SQLite local, fuera de la bóveda. Buscar combina:
- similitud semántica: entiende paráfrasis ("JS del lado del servidor" encuentra la nota de Node.js);
- BM25 por palabras: nombres propios, siglas o palabras raras que el embedding podría diluir.

Se actualiza de forma incremental (solo las notas cuya fecha o tamaño cambió). Si el modelo de
embeddings no está, sigue funcionando solo por palabras y completa los vectores cuando vuelva.

Umbrales medidos con qwen3-embedding:0.6b (ver tests/test_indice.py y pruebas/evaluar_agentes.py):
una pregunta y la nota que la responde dan ~0.55-0.75 de similitud; temas sin relación, < 0.35.
"""

import hashlib
import math
import re
import sqlite3
import threading
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath

import numpy as np

from src.engines import embeddings
from src.local import abrir_sqlite, carpeta_local
from src.obsidian.config import ruta_boveda
from src.obsidian.estructura import es_buscable, es_conocimiento
from src.obsidian.formato import propiedades, separar_frontmatter, texto_para_indexar
from src.obsidian.texto import palabras
from src.obsidian.vault_reader import listar_notas

MAX_CARACTERES_FRAGMENTO = 900
LOTE_EMBEDDINGS = 32
UMBRAL_CONTEXTO = 0.5  # similitud mínima para darle una nota al agente sin que la pida
PESO_SEMANTICO = 0.8  # el resto es BM25 normalizado
BM25_K1, BM25_B = 1.2, 0.75

_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")
_FIN_ORACION = re.compile(r"(?<=[.!?])\s+")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notas (ruta TEXT PRIMARY KEY, firma TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fragmentos (
    ruta TEXT NOT NULL, orden INTEGER NOT NULL, encabezado TEXT NOT NULL, texto TEXT NOT NULL,
    entrada TEXT NOT NULL, vector BLOB, PRIMARY KEY (ruta, orden)
);
"""

_bloqueo = threading.Lock()


# ---------- fragmentar ----------


@dataclass(frozen=True)
class Fragmento:
    encabezado: str
    texto: str


def _partir(texto: str) -> list[str]:
    """Trozos de hasta MAX_CARACTERES_FRAGMENTO, cortando por párrafo y, si hace falta, por oración."""
    unidades: list[str] = []
    for parrafo in re.split(r"\n\s*\n", texto):
        parrafo = parrafo.strip()
        if not parrafo:
            continue
        if len(parrafo) <= MAX_CARACTERES_FRAGMENTO:
            unidades.append(parrafo)
            continue
        for oracion in _FIN_ORACION.split(parrafo):
            while len(oracion) > MAX_CARACTERES_FRAGMENTO:
                unidades.append(oracion[:MAX_CARACTERES_FRAGMENTO])
                oracion = oracion[MAX_CARACTERES_FRAGMENTO:]
            if oracion.strip():
                unidades.append(oracion.strip())
    trozos: list[str] = []
    for unidad in unidades:
        if trozos and len(trozos[-1]) + len(unidad) + 2 <= MAX_CARACTERES_FRAGMENTO:
            trozos[-1] = f"{trozos[-1]}\n\n{unidad}"
        else:
            trozos.append(unidad)
    return trozos


def fragmentar(contenido: str) -> list[Fragmento]:
    secciones: list[tuple[str, list[str]]] = [("", [])]
    for linea in texto_para_indexar(contenido).splitlines():
        coincidencia = _ENCABEZADO.match(linea)
        if coincidencia:
            secciones.append((coincidencia.group(2).strip(), []))
        else:
            secciones[-1][1].append(linea)
    return [
        Fragmento(encabezado, trozo)
        for encabezado, lineas in secciones
        for trozo in _partir("\n".join(lineas).strip())
    ]


def _entrada(ruta: str, contenido: str, fragmento: Fragmento) -> str:
    """Lo que se le da al modelo de embeddings: el fragmento con el título y etiquetas de su nota."""
    frontmatter, _ = separar_frontmatter(contenido)
    etiquetas = " ".join(v for k, v in propiedades(frontmatter).items() if k in ("tags", "resumen", "aliases"))
    titulo = PurePosixPath(ruta).stem
    cabecera = f"{titulo} > {fragmento.encabezado}" if fragmento.encabezado else titulo
    return f"{cabecera} {etiquetas}".strip() + f"\n{fragmento.texto}"


# ---------- base de datos ----------


def _ruta_db():
    huella = hashlib.sha1(str(ruta_boveda().resolve()).lower().encode()).hexdigest()[:10]
    return carpeta_local() / f"indice-{huella}.db"


@contextmanager
def _db():
    with abrir_sqlite(_ruta_db(), _ESQUEMA) as conexion:
        yield conexion


def _meta(conexion, clave: str) -> str | None:
    fila = conexion.execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
    return fila[0] if fila else None


def _poner_meta(conexion, clave: str, valor: str) -> None:
    conexion.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES (?, ?)", (clave, valor))


def _subir_version(conexion) -> None:
    _poner_meta(conexion, "version", str(int(_meta(conexion, "version") or 0) + 1))


def _firma(ruta_absoluta) -> str:
    datos = ruta_absoluta.stat()
    return f"{datos.st_mtime_ns}:{datos.st_size}"


# ---------- actualizar ----------


@dataclass(frozen=True)
class Resumen:
    procesadas: int
    borradas: int
    sin_vector: int


def actualizar(solo: Iterable[str] | None = None, esperar: bool = True) -> Resumen | None:
    """Pone el índice al día con la bóveda. `solo` limita la revisión a esas notas (tras escribirlas).

    Nunca lanza por un fallo de embeddings: los fragmentos quedan sin vector y se completan después.
    Con esperar=False, si ya hay otra actualización en curso en este proceso (ej. la indexación
    inicial de una bóveda grande), no espera: devuelve None y se usa el índice como está.
    """
    if not esperar:
        if not _bloqueo.acquire(blocking=False):
            return None
        _bloqueo.release()
    boveda = ruta_boveda()
    actuales = {
        ruta.relative_to(boveda).as_posix(): ruta
        for ruta in listar_notas()
        if es_buscable(ruta.relative_to(boveda).as_posix())
    }
    solo = set(solo) if solo is not None else None
    with _bloqueo:
        with _db() as conexion:
            if _meta(conexion, "modelo") != embeddings.modelo_embeddings():
                conexion.execute("UPDATE fragmentos SET vector = NULL")
                _poner_meta(conexion, "modelo", embeddings.modelo_embeddings())
            existentes = dict(conexion.execute("SELECT ruta, firma FROM notas"))
            revisar = set(existentes) | set(actuales)
            if solo is not None:
                revisar &= solo
            borradas = procesadas = 0
            for ruta in revisar:
                if ruta not in actuales:
                    conexion.execute("DELETE FROM notas WHERE ruta = ?", (ruta,))
                    conexion.execute("DELETE FROM fragmentos WHERE ruta = ?", (ruta,))
                    borradas += 1
                    continue
                try:
                    firma = _firma(actuales[ruta])
                    if existentes.get(ruta) == firma:
                        continue
                    contenido = actuales[ruta].read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue  # se borró o se está escribiendo justo ahora: en la próxima vuelta
                conexion.execute("DELETE FROM fragmentos WHERE ruta = ?", (ruta,))
                for orden, fragmento in enumerate(fragmentar(contenido)):
                    conexion.execute(
                        "INSERT INTO fragmentos (ruta, orden, encabezado, texto, entrada) VALUES (?, ?, ?, ?, ?)",
                        (ruta, orden, fragmento.encabezado, fragmento.texto, _entrada(ruta, contenido, fragmento)),
                    )
                conexion.execute("INSERT OR REPLACE INTO notas (ruta, firma) VALUES (?, ?)", (ruta, firma))
                procesadas += 1
            if procesadas or borradas:
                _subir_version(conexion)
        sin_vector = _completar_vectores(solo)
    return Resumen(procesadas=procesadas, borradas=borradas, sin_vector=sin_vector)


def _completar_vectores(solo: set[str] | None) -> int:
    """Calcula los embeddings que falten, por lotes (cada lote en su propia transacción corta)."""
    while embeddings.disponible():
        consulta = "SELECT ruta, orden, entrada FROM fragmentos WHERE vector IS NULL"
        parametros: list = []
        if solo is not None:
            if not solo:
                break
            consulta += f" AND ruta IN ({','.join('?' * len(solo))})"
            parametros = sorted(solo)
        with _db() as conexion:
            filas = conexion.execute(consulta + " LIMIT ?", (*parametros, LOTE_EMBEDDINGS)).fetchall()
        if not filas:
            break
        vectores = embeddings.embeber([fila[2] for fila in filas])
        if vectores is None:
            break
        with _db() as conexion:
            for (ruta, orden, _entrada_texto), vector in zip(filas, vectores):
                conexion.execute(
                    "UPDATE fragmentos SET vector = ? WHERE ruta = ? AND orden = ?",
                    (vector.astype(np.float32).tobytes(), ruta, orden),
                )
            _subir_version(conexion)
    with _db() as conexion:
        return conexion.execute("SELECT COUNT(*) FROM fragmentos WHERE vector IS NULL").fetchone()[0]


def actualizar_sin_fallar(esperar: bool = True) -> Resumen | None:
    try:
        return actualizar(esperar=esperar)
    except (sqlite3.Error, OSError, RuntimeError, ValueError) as error:
        print(f"[aviso] No se pudo actualizar el índice de la bóveda: {error}")
        return None


# ---------- caché en memoria ----------


@dataclass
class _Cache:
    version: str = ""
    rutas: list[str] | None = None
    encabezados: list[str] | None = None
    textos: list[str] | None = None
    matriz: np.ndarray | None = None  # una fila por fragmento; filas sin vector en cero
    con_vector: np.ndarray | None = None  # máscara booleana
    tokens: list[Counter] | None = None
    frecuencia_doc: Counter | None = None
    largo_promedio: float = 1.0
    notas: dict[str, np.ndarray] | None = None  # vector de cada nota (promedio de sus fragmentos)


_cache = _Cache()


def _cargar() -> _Cache:
    global _cache
    with _db() as conexion:
        version = f"{_ruta_db()}:{_meta(conexion, 'version') or '0'}"
        if version == _cache.version and _cache.rutas is not None:
            return _cache
        filas = conexion.execute("SELECT ruta, encabezado, texto, vector FROM fragmentos ORDER BY ruta, orden").fetchall()
    rutas = [fila[0] for fila in filas]
    vectores = [np.frombuffer(fila[3], dtype=np.float32) if fila[3] else None for fila in filas]
    dimension = next((len(v) for v in vectores if v is not None), 0)
    matriz = np.zeros((len(filas), dimension), dtype=np.float32) if dimension else None
    con_vector = np.array([v is not None and len(v) == dimension for v in vectores], dtype=bool)
    if matriz is not None:
        for i, vector in enumerate(vectores):
            if con_vector[i]:
                matriz[i] = vector
    tokens = [Counter(palabras(f"{PurePosixPath(fila[0]).stem} {fila[1]} {fila[2]}")) for fila in filas]
    frecuencia_doc: Counter = Counter()
    for conteo in tokens:
        frecuencia_doc.update(conteo.keys())
    notas: dict[str, np.ndarray] = {}
    if matriz is not None:
        por_nota: dict[str, list[int]] = {}
        for i, ruta in enumerate(rutas):
            if con_vector[i]:
                por_nota.setdefault(ruta, []).append(i)
        for ruta, indices in por_nota.items():
            promedio = matriz[indices].mean(axis=0)
            notas[ruta] = promedio / max(float(np.linalg.norm(promedio)), 1e-9)
    _cache = _Cache(
        version=version,
        rutas=rutas,
        encabezados=[fila[1] for fila in filas],
        textos=[fila[2] for fila in filas],
        matriz=matriz,
        con_vector=con_vector,
        tokens=tokens,
        frecuencia_doc=frecuencia_doc,
        largo_promedio=max(1.0, sum(sum(c.values()) for c in tokens) / max(1, len(tokens))),
        notas=notas,
    )
    return _cache


# ---------- buscar ----------


@dataclass(frozen=True)
class Resultado:
    ruta: str
    encabezado: str
    texto: str
    similitud: float | None  # coseno del mejor fragmento con la consulta; None si solo hubo palabras
    palabras_en_comun: int
    puntaje: float


def _bm25(cache: _Cache, consulta: list[str]) -> np.ndarray:
    total = len(cache.tokens)
    puntajes = np.zeros(total, dtype=np.float32)
    for palabra in set(consulta):
        frecuencia = cache.frecuencia_doc.get(palabra, 0)
        if not frecuencia:
            continue
        idf = math.log(1 + (total - frecuencia + 0.5) / (frecuencia + 0.5))
        for i, conteo in enumerate(cache.tokens):
            veces = conteo.get(palabra, 0)
            if veces:
                largo = sum(conteo.values())
                norma = BM25_K1 * (1 - BM25_B + BM25_B * largo / cache.largo_promedio)
                puntajes[i] += idf * veces * (BM25_K1 + 1) / (veces + norma)
    return puntajes


def buscar(
    consulta: str,
    k: int = 5,
    filtro: Callable[[str], bool] = es_buscable,
    excluir: Iterable[str] = (),
) -> list[Resultado]:
    """Las k notas más relevantes para la consulta (el mejor fragmento de cada una)."""
    cache = _cargar()
    if not cache.rutas:
        return []
    palabras_consulta = palabras(consulta)
    lexico = _bm25(cache, palabras_consulta)
    maximo = float(lexico.max()) if len(lexico) else 0.0
    lexico_norm = lexico / maximo if maximo > 0 else lexico

    semantico = None
    if cache.matriz is not None and cache.con_vector.any():
        vector = embeddings.embeber_consulta(consulta)
        if vector is not None and len(vector) == cache.matriz.shape[1]:
            semantico = np.where(cache.con_vector, cache.matriz @ vector, 0.0)
    combinado = PESO_SEMANTICO * semantico + (1 - PESO_SEMANTICO) * lexico_norm if semantico is not None else lexico_norm

    excluir = set(excluir)
    conjunto_consulta = set(palabras_consulta)
    mejores: dict[str, Resultado] = {}
    for i in np.argsort(-combinado):
        ruta = cache.rutas[i]
        if ruta in mejores or ruta in excluir or not filtro(ruta):
            continue
        if combinado[i] <= 0:
            break
        mejores[ruta] = Resultado(
            ruta=ruta,
            encabezado=cache.encabezados[i],
            texto=cache.textos[i],
            similitud=float(semantico[i]) if semantico is not None else None,
            palabras_en_comun=len(conjunto_consulta & set(cache.tokens[i])),
            puntaje=float(combinado[i]),
        )
        if len(mejores) >= k:
            break
    return list(mejores.values())


def es_relevante(resultado: Resultado) -> bool:
    """¿Vale la pena darle este resultado al agente aunque no lo haya pedido?

    Con embeddings: similitud semántica sobre el umbral. Solo por palabras: al menos dos palabras
    de la consulta en el fragmento (una sola palabra en común es casi siempre coincidencia).
    """
    if resultado.similitud is not None:
        return resultado.similitud >= UMBRAL_CONTEXTO
    return resultado.palabras_en_comun >= 2


def contexto_relevante(consulta: str, k: int = 3, excluir: Iterable[str] = ()) -> list[Resultado]:
    """Notas que probablemente ayudan a responder esta consulta. Nunca lanza."""
    try:
        return [r for r in buscar(consulta, k=k, excluir=excluir) if es_relevante(r)]
    except (sqlite3.Error, OSError, RuntimeError):
        return []


# ---------- similitud entre notas ----------


def _mejor_por_nota(cache: _Cache, similitudes: np.ndarray, filtro: Callable[[str], bool], excluir: str = "") -> list[tuple[str, float]]:
    """Agrupa similitudes por fragmento en la mejor de cada nota."""
    mejores: dict[str, float] = {}
    for i, similitud in enumerate(similitudes):
        ruta = cache.rutas[i]
        if not cache.con_vector[i] or ruta == excluir or not filtro(ruta):
            continue
        if similitud > mejores.get(ruta, -1.0):
            mejores[ruta] = float(similitud)
    return sorted(mejores.items(), key=lambda par: -par[1])


def notas_similares(ruta: str, k: int = 5, filtro: Callable[[str], bool] = es_conocimiento) -> list[tuple[str, float]]:
    """Las notas que más se parecen a `ruta`: la mejor similitud entre cualquier par de sus fragmentos.

    Se usa el mejor par de fragmentos y no el promedio de la nota: con el promedio, todas las
    notas técnicas se parecían ~0.40-0.49 entre sí (Jarvis ↔ Express igual que Jarvis ↔ Ollama);
    con el mejor par, lo que de verdad comparten un tema resalta (Jarvis ↔ Ollama 0.57, Jarvis ↔
    Express 0.42). Medido con qwen3-embedding:0.6b.
    """
    cache = _cargar()
    if cache.matriz is None:
        return []
    propios = [i for i, r in enumerate(cache.rutas) if r == ruta and cache.con_vector[i]]
    if not propios:
        return []
    similitudes = (cache.matriz[propios] @ cache.matriz.T).max(axis=0)
    return _mejor_por_nota(cache, similitudes, filtro, excluir=ruta)[:k]


def similares_a_texto(texto: str, k: int = 5, filtro: Callable[[str], bool] = es_conocimiento) -> list[tuple[str, float]]:
    """Notas cuyo contenido se parece a un texto que todavía no es una nota."""
    cache = _cargar()
    if cache.matriz is None:
        return []
    vectores = embeddings.embeber([texto])
    if vectores is None or vectores.shape[1] != cache.matriz.shape[1]:
        return []
    return _mejor_por_nota(cache, cache.matriz @ vectores[0], filtro)[:k]


def main() -> None:
    """python -m src.obsidian.indice: pone el índice al día y dice cómo quedó."""
    from src.arranque import preparar

    preparar()
    print("Indexando la bóveda (la primera vez puede tardar un par de minutos)...")
    resumen = actualizar()
    situacion = estado()
    print(f"Listo: {resumen.procesadas} nota(s) procesadas, {resumen.borradas} quitadas.")
    print(f"Índice: {situacion.notas} notas, {situacion.fragmentos} fragmentos, {situacion.sin_vector} sin vector.")
    if situacion.sin_vector:
        print(f"Los que no tienen vector se buscan solo por palabras: revisa que Ollama tenga {situacion.modelo}.")


@dataclass(frozen=True)
class Estado:
    notas: int
    fragmentos: int
    sin_vector: int
    modelo: str
    semantico: bool


def estado() -> Estado:
    with _db() as conexion:
        notas = conexion.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
        fragmentos = conexion.execute("SELECT COUNT(*) FROM fragmentos").fetchone()[0]
        sin_vector = conexion.execute("SELECT COUNT(*) FROM fragmentos WHERE vector IS NULL").fetchone()[0]
    return Estado(
        notas=notas,
        fragmentos=fragmentos,
        sin_vector=sin_vector,
        modelo=embeddings.modelo_embeddings(),
        semantico=fragmentos > 0 and sin_vector < fragmentos,
    )


if __name__ == "__main__":
    main()
