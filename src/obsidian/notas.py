"""Gestión de las notas libres de la bóveda: crear, ampliar, editar, mover, conectar y eliminar.

Cada función es una herramienta del agente (se registra con su riesgo en src/herramientas/
catalogo.py) y devuelve un texto que el modelo lee para contarle al usuario qué pasó.

Mantiene la bóveda ordenada sola:
- Una nota nueva sin carpeta cae junto a las notas de su mismo tema.
- Las notas de un área (04-Conocimiento/<área>/) se agregan a la nota índice del área, y el
  área a la nota de Inicio: el grafo queda con estructura aunque el usuario no enlace nada.
- Se conecta con las notas que de verdad tratan lo mismo: las que se mencionan por su título
  (como las "menciones sin enlazar" de Obsidian) o las que comparten un fragmento muy parecido
  (similitud semántica sobre un umbral medido). Nunca con notas del sistema ni listas de tareas.
- Mover o renombrar actualiza los [[enlaces]] que apuntaban a la nota; eliminarla quita los
  enlaces de "Relacionado" que quedarían rotos.
"""

import re
from datetime import datetime
from pathlib import PurePosixPath

from send2trash import send2trash

from src.local import carpeta_local
from src.obsidian import indice
from src.obsidian.config import ruta_boveda
from src.obsidian.estructura import (
    CARPETA_CONOCIMIENTO,
    CARPETAS,
    NOTA_INICIO,
    NOTAS_INICIALES,
    NOTAS_OPERATIVAS,
    es_conocimiento,
    es_de_sistema,
    es_indice,
    ruta_indice,
)
from src.obsidian.formato import (
    SECCION_NOTAS,
    SECCION_RELACIONADO,
    agregar_item,
    insertar_antes_de_relacionado,
    items_de_seccion,
    quitar_items,
    quitar_seccion,
    separar_frontmatter,
    texto_para_indexar,
)
from src.obsidian.grafo import enlaces_de
from src.obsidian.texto import PALABRAS_VACIAS, normalizar
from src.obsidian.vault_reader import (
    leer_nota,
    listar_rutas_relativas,
    resolver_nombre,
    resolver_nota,
    resolver_ruta,
)
from src.obsidian.vault_writer import escribir_nota

# Similitud del mejor par de fragmentos, medida con qwen3-embedding:0.6b en la bóveda de ejemplo:
# del mismo tema, Node.js ↔ Express 0.71, Jarvis ↔ Ollama 0.57, Node.js ↔ TypeScript 0.53; solo
# "de tecnología" sin relación real, Jarvis ↔ Express 0.42, Bases de datos ↔ Express 0.40.
UMBRAL_CONEXION_AUTO = 0.5
UMBRAL_SUGERENCIA = 0.4
LARGO_MINIMO_TITULO = 3  # "Git" sí cuenta como mención; títulos de 1-2 letras no
UMBRAL_CARPETA = 0.5
MAX_CONEXIONES_AUTO = 3
SECCION_AREAS = "## Áreas"

_ENLACE_WIKI = re.compile(r"\[\[([^\]|#^]+)([^\]]*)\]\]")
_NO_TOCAR = frozenset(NOTAS_INICIALES) | NOTAS_OPERATIVAS


def _ahora() -> datetime:
    return datetime.now()


def _nombre_enlace(ruta: str, rutas: list[str]) -> str:
    """Cómo enlazar la nota: por su nombre si es único en la bóveda, si no por su ruta."""
    nombre = PurePosixPath(ruta).stem
    repetidos = [r for r in rutas if normalizar(PurePosixPath(r).stem) == normalizar(nombre)]
    return nombre if len(repetidos) <= 1 else ruta.removesuffix(".md")


def _destino_de_item(item: str, rutas: list[str]) -> str | None:
    coincidencia = _ENLACE_WIKI.search(item)
    return resolver_nombre(coincidencia.group(1), rutas) if coincidencia else None


def _escribir(ruta: str, contenido: str) -> None:
    escribir_nota(ruta, contenido, sobrescribir=True)


def _refrescar_indice() -> None:
    """Pone el índice al día (incremental: solo re-procesa lo que cambió, incluidas notas escritas a mano)."""
    indice.actualizar_sin_fallar()


def _respaldar(ruta: str, contenido: str) -> None:
    """Guarda la versión anterior antes de reescribir una nota: editar sigue siendo reversible."""
    carpeta = carpeta_local() / "respaldos" / _ahora().strftime("%Y-%m-%d")
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{_ahora():%H%M%S}-{ruta.replace('/', '__')}").write_text(contenido, encoding="utf-8")


# ---------- enlaces ----------


def agregar_enlace(origen: str, destino: str, motivo: str | None = None) -> bool:
    """Agrega [[destino]] a "## Relacionado" de origen. False si ya enlazaba a destino (en cualquier parte)."""
    rutas = listar_rutas_relativas()
    contenido = leer_nota(origen) or ""
    if destino in enlaces_de(contenido, rutas):
        return False
    item = f"[[{_nombre_enlace(destino, rutas)}]]"
    if motivo and motivo.strip():
        item += f" — {motivo.strip()}"
    _escribir(origen, agregar_item(contenido, SECCION_RELACIONADO, item))
    return True


def quitar_enlace(origen: str, destino: str) -> int:
    """Quita de "## Relacionado" de origen los enlaces a destino. Devuelve cuántos quitó."""
    rutas = listar_rutas_relativas()
    contenido = leer_nota(origen) or ""
    nuevo, quitados = quitar_items(contenido, SECCION_RELACIONADO, lambda item: _destino_de_item(item, rutas) == destino)
    if quitados:
        _escribir(origen, nuevo)
    return quitados


def _menciona(texto_normalizado: str, titulo: str) -> bool:
    titulo = normalizar(titulo).strip()
    if len(titulo) < LARGO_MINIMO_TITULO or titulo in PALABRAS_VACIAS:
        return False
    return re.search(rf"(?<![\w]){re.escape(titulo)}(?![\w])", texto_normalizado) is not None


def _ya_conectadas(ruta: str, rutas: list[str]) -> set[str]:
    """Notas enlazadas con `ruta` en cualquier dirección (el enlace se escribe en una sola nota)."""
    conectadas = enlaces_de(leer_nota(ruta) or "", rutas)
    for otra in rutas:
        if otra != ruta and not es_de_sistema(otra) and ruta in enlaces_de(leer_nota(otra) or "", rutas):
            conectadas.add(otra)
    return conectadas


def menciones(ruta: str) -> list[tuple[str, str]]:
    """(nota, motivo) de conocimiento que se mencionan por título con `ruta`, en cualquier dirección."""
    rutas = listar_rutas_relativas()
    propio = normalizar(texto_para_indexar(leer_nota(ruta) or ""))
    titulo_propio = PurePosixPath(ruta).stem
    encontradas = []
    for otra in rutas:
        if otra == ruta or not es_conocimiento(otra):
            continue
        if _menciona(propio, PurePosixPath(otra).stem):
            encontradas.append((otra, f"menciona «{PurePosixPath(otra).stem}»"))
        elif _menciona(normalizar(texto_para_indexar(leer_nota(otra) or "")), titulo_propio):
            encontradas.append((otra, f"«{PurePosixPath(otra).stem}» la menciona"))
    return encontradas


def candidatas(ruta: str, umbral: float = UMBRAL_CONEXION_AUTO, k: int = MAX_CONEXIONES_AUTO) -> list[tuple[str, str]]:
    """(nota, motivo) con las que conviene conectar y todavía no lo están: primero menciones, luego parecido."""
    ya = _ya_conectadas(ruta, listar_rutas_relativas())
    resultado = [(otra, motivo) for otra, motivo in menciones(ruta) if otra not in ya]
    vistas = {otra for otra, _ in resultado} | ya
    for otra, similitud in indice.notas_similares(ruta, k=k * 2):
        if similitud < umbral:
            break
        if otra not in vistas:
            resultado.append((otra, f"{round(similitud * 100)}% parecida"))
            vistas.add(otra)
    return resultado[:k]


def auto_conectar(ruta: str) -> list[str]:
    """Enlaza la nota con las que de verdad tratan lo mismo. Devuelve con cuáles."""
    if not es_conocimiento(ruta):
        return []
    conectadas = [PurePosixPath(otra).stem for otra, _motivo in candidatas(ruta) if agregar_enlace(ruta, otra)]
    if conectadas:
        _refrescar_indice()
    return conectadas


# ---------- índices de carpeta ----------


def _es_area(carpeta: str) -> bool:
    return PurePosixPath(carpeta).parent.as_posix() == CARPETA_CONOCIMIENTO


def registrar_en_indice(ruta: str) -> None:
    """Agrega la nota a la nota índice de su carpeta (y crea la del área si es la primera nota)."""
    carpeta = PurePosixPath(ruta).parent.as_posix()
    if carpeta == "." or es_de_sistema(ruta) or es_indice(ruta):
        return
    ruta_del_indice = ruta_indice(carpeta)
    contenido = leer_nota(ruta_del_indice)
    if contenido is None:
        if not _es_area(carpeta):
            return
        area = PurePosixPath(carpeta).name
        contenido = f"---\ntipo: indice\n---\nNotas del área de {area}. Cada nota nueva de esta carpeta se agrega aquí sola.\n"
        inicio = leer_nota(NOTA_INICIO)
        if inicio is not None:
            _escribir(NOTA_INICIO, agregar_item(inicio, SECCION_AREAS, f"[[{area}]]"))
    rutas = listar_rutas_relativas()
    if ruta in {_destino_de_item(item, rutas) for item in items_de_seccion(contenido, SECCION_NOTAS)}:
        return
    _escribir(ruta_del_indice, agregar_item(contenido, SECCION_NOTAS, f"[[{_nombre_enlace(ruta, rutas)}]]"))


def quitar_de_indice(ruta: str, rutas: list[str]) -> None:
    carpeta = PurePosixPath(ruta).parent.as_posix()
    if carpeta == ".":
        return
    ruta_del_indice = ruta_indice(carpeta)
    contenido = leer_nota(ruta_del_indice)
    if contenido is None:
        return
    nuevo, quitados = quitar_items(contenido, SECCION_NOTAS, lambda item: _destino_de_item(item, rutas) == ruta)
    if quitados:
        _escribir(ruta_del_indice, nuevo)


def elegir_carpeta(titulo: str, contenido: str) -> str:
    """Carpeta para una nota nueva sin carpeta: la de las notas más parecidas, o 04-Conocimiento."""
    for ruta, similitud in indice.similares_a_texto(f"{titulo}\n{contenido}", k=3):
        carpeta = PurePosixPath(ruta).parent.as_posix()
        if similitud >= UMBRAL_CARPETA and carpeta.startswith(("03-", "04-", "05-")):
            return carpeta
    return CARPETA_CONOCIMIENTO


# ---------- herramientas ----------


def _no_existe(nombre: str) -> str:
    return f"No encontré ninguna nota llamada '{nombre}'. Usa listar_notas o buscar_en_boveda para ver cuáles hay."


def _normalizar_ruta_nueva(ruta: str, contenido: str) -> str:
    ruta = ruta.strip().replace("\\", "/").strip("/")
    if not ruta.lower().endswith(".md"):
        ruta += ".md"
    if "/" not in ruta:
        ruta = f"{elegir_carpeta(ruta[:-3], contenido)}/{ruta}"
    return ruta


def crear_nota(ruta: str, contenido: str, etiquetas: str | None = None) -> str:
    """Crea una nota nueva, la registra en su índice de carpeta y la conecta con su tema."""
    if "/" not in ruta.strip().replace("\\", "/").strip("/"):
        _refrescar_indice()  # para elegir la carpeta según las notas que ya existen
    ruta = _normalizar_ruta_nueva(ruta, contenido)
    try:
        ruta_absoluta = resolver_ruta(ruta)
    except ValueError as error:
        return str(error)
    if es_de_sistema(ruta):
        return "00-Sistema es de uso interno; elige otra carpeta para la nota."
    existente = resolver_nombre(PurePosixPath(ruta).stem, listar_rutas_relativas())
    if ruta_absoluta.exists() or existente:
        return (
            f"Ya existe una nota llamada '{PurePosixPath(ruta).stem}' ({existente or ruta}); no la sobrescribí. "
            "Para cambiarla usa agregar_a_nota o editar_nota."
        )

    frontmatter = f"---\ncreado: {_ahora():%Y-%m-%d}\n"
    if etiquetas and etiquetas.strip():
        lista = [e.strip().lstrip("#") for e in re.split(r"[,;]", etiquetas) if e.strip()]
        frontmatter += f"tags: [{', '.join(lista)}]\n"
    frontmatter += "---\n"
    _frontmatter_modelo, cuerpo = separar_frontmatter(contenido.strip())
    _escribir(ruta, frontmatter + quitar_seccion(cuerpo, SECCION_RELACIONADO).strip() + "\n")

    registrar_en_indice(ruta)
    _refrescar_indice()
    conectadas = auto_conectar(ruta)
    mensaje = f"Nota creada: {ruta}."
    if conectadas:
        mensaje += f" La conecté con: {', '.join(conectadas)}."
    return mensaje


def _nota_editable(nombre: str) -> tuple[str | None, str | None]:
    """(ruta, error) de una nota que se puede modificar con las herramientas generales."""
    ruta = resolver_nota(nombre)
    if ruta is None:
        return None, _no_existe(nombre)
    if es_de_sistema(ruta):
        return None, "Esa nota es de uso interno del sistema; no la modifico."
    if ruta.startswith("02-Tareas/"):
        return None, "Las listas de tareas se cambian con agregar_pendiente, completar_pendiente o reprogramar_pendiente."
    return ruta, None


def agregar_a_nota(ruta: str, texto: str) -> str:
    """Agrega texto al final de una nota existente (antes de su sección Relacionado)."""
    ruta_real, error = _nota_editable(ruta)
    if error:
        return error
    if not texto.strip():
        return "No me dijiste qué agregar a la nota."
    _escribir(ruta_real, insertar_antes_de_relacionado(leer_nota(ruta_real) or "", texto.strip()))
    _refrescar_indice()
    conectadas = auto_conectar(ruta_real)
    mensaje = f"Agregué el texto a {ruta_real}."
    if conectadas:
        mensaje += f" Ahora también está conectada con: {', '.join(conectadas)}."
    return mensaje


def editar_nota(ruta: str, contenido: str) -> str:
    """Reemplaza el contenido de una nota, conservando sus propiedades y sus enlaces de Relacionado.

    La versión anterior queda respaldada en %LOCALAPPDATA%\\kindred\\respaldos.
    """
    ruta_real, error = _nota_editable(ruta)
    if error:
        return error
    if not contenido.strip():
        return "No voy a dejar la nota vacía; si quieres borrarla, pídeme que la elimine."
    anterior = leer_nota(ruta_real) or ""
    frontmatter_anterior, _ = separar_frontmatter(anterior)
    frontmatter_nuevo, cuerpo = separar_frontmatter(contenido.strip())
    nuevo = (frontmatter_nuevo or frontmatter_anterior) + quitar_seccion(cuerpo, SECCION_RELACIONADO).strip() + "\n"
    for item in items_de_seccion(anterior, SECCION_RELACIONADO):
        nuevo = agregar_item(nuevo, SECCION_RELACIONADO, item)
    _respaldar(ruta_real, anterior)
    _escribir(ruta_real, nuevo)
    _refrescar_indice()
    conectadas = auto_conectar(ruta_real)
    mensaje = f"Actualicé {ruta_real} (la versión anterior quedó respaldada)."
    if conectadas:
        mensaje += f" Ahora también está conectada con: {', '.join(conectadas)}."
    return mensaje


def _ruta_destino(origen: str, destino: str) -> str:
    destino = destino.strip().replace("\\", "/").strip("/")
    nombre = PurePosixPath(origen).name
    if destino.lower().endswith(".md"):
        return destino
    es_carpeta = "/" in destino or destino in CARPETAS or (ruta_boveda() / destino).is_dir()
    if es_carpeta:
        return f"{destino}/{nombre}"
    carpeta = PurePosixPath(origen).parent.as_posix()
    return f"{destino}.md" if carpeta == "." else f"{carpeta}/{destino}.md"


def mover_nota(ruta: str, destino: str) -> str:
    """Mueve o renombra una nota y actualiza los [[enlaces]] que apuntaban a ella."""
    origen = resolver_nota(ruta)
    if origen is None:
        return _no_existe(ruta)
    if es_de_sistema(origen) or origen in _NO_TOCAR:
        return "Esa nota es parte de la estructura base; no la muevo."
    nueva = _ruta_destino(origen, destino)
    try:
        absoluta_nueva = resolver_ruta(nueva)
    except ValueError as error:
        return str(error)
    if es_de_sistema(nueva):
        return "00-Sistema es de uso interno; elige otra carpeta."
    if absoluta_nueva.exists():
        return f"Ya existe una nota en '{nueva}'; no la muevo para no sobrescribirla."

    rutas_antes = listar_rutas_relativas()
    absoluta_nueva.parent.mkdir(parents=True, exist_ok=True)
    resolver_ruta(origen).rename(absoluta_nueva)
    rutas_despues = listar_rutas_relativas()
    nombre_nuevo = _nombre_enlace(nueva, rutas_despues)

    actualizadas = 0
    for otra in rutas_despues:
        if es_de_sistema(otra):
            continue
        contenido = leer_nota(otra) or ""

        def reemplazar(coincidencia: re.Match) -> str:
            if resolver_nombre(coincidencia.group(1), rutas_antes) == origen:
                return f"[[{nombre_nuevo}{coincidencia.group(2)}]]"
            return coincidencia.group(0)

        nuevo = _ENLACE_WIKI.sub(reemplazar, contenido)
        if nuevo != contenido:
            _escribir(otra, nuevo)
            actualizadas += 1

    quitar_de_indice(origen, rutas_antes)
    registrar_en_indice(nueva)
    _refrescar_indice()
    mensaje = f"Moví la nota a {nueva}."
    if actualizadas:
        mensaje += f" Actualicé los enlaces en {actualizadas} nota(s)."
    return mensaje


def conectar_notas(origen: str, destino: str, motivo: str | None = None) -> str:
    """Enlaza dos notas existentes (en la sección Relacionado de origen, con el motivo si se da)."""
    ruta_origen, ruta_destino = resolver_nota(origen), resolver_nota(destino)
    if ruta_origen is None:
        return _no_existe(origen)
    if ruta_destino is None:
        return _no_existe(destino)
    if ruta_origen == ruta_destino:
        return "Esas son la misma nota; no puedo conectarla consigo misma."
    if es_de_sistema(ruta_origen) or es_de_sistema(ruta_destino):
        return "Las notas de 00-Sistema son de uso interno; no las conecto."
    if not agregar_enlace(ruta_origen, ruta_destino, motivo):
        return f"'{ruta_origen}' ya estaba conectada con '{ruta_destino}'."
    _refrescar_indice()
    return f"Conecté '{ruta_origen}' con '{ruta_destino}'."


def desconectar_notas(origen: str, destino: str) -> str:
    """Quita el enlace de Relacionado de origen hacia destino."""
    ruta_origen, ruta_destino = resolver_nota(origen), resolver_nota(destino)
    if ruta_origen is None:
        return _no_existe(origen)
    if ruta_destino is None:
        return _no_existe(destino)
    if not quitar_enlace(ruta_origen, ruta_destino):
        return f"'{ruta_origen}' no tenía un enlace a '{ruta_destino}' en su sección Relacionado."
    _refrescar_indice()
    return f"Desconecté '{ruta_origen}' de '{ruta_destino}'."


def sugerir_conexiones(ruta: str) -> str:
    """Las notas que más se parecen a esta, con qué tanto, para decidir qué conectar."""
    ruta_real = resolver_nota(ruta)
    if ruta_real is None:
        return _no_existe(ruta)
    _refrescar_indice()
    sugeridas = candidatas(ruta_real, umbral=UMBRAL_SUGERENCIA, k=6)
    if not sugeridas:
        if not indice.estado().semantico:
            return "El índice semántico todavía no está listo; solo puedo ver menciones por título, y no hay."
        return f"No encontré notas que traten el mismo tema que '{ruta_real}'."
    return f"Notas que se relacionan con '{ruta_real}' (y todavía no están conectadas):\n" + "\n".join(
        f"- {otra} ({motivo})" for otra, motivo in sugeridas
    )


def ruta_a_eliminar(nombre: str) -> str | None:
    """Solo coincidencia exacta (ruta o nombre): para borrar no se adivina por parecido."""
    return resolver_nombre(nombre, listar_rutas_relativas())


def eliminar_nota(ruta: str) -> str:
    """Manda una nota a la papelera de Windows (recuperable) y quita los enlaces que quedarían rotos."""
    ruta_real = ruta_a_eliminar(ruta)
    if ruta_real is None:
        return _no_existe(ruta)
    if es_de_sistema(ruta_real) or ruta_real in _NO_TOCAR:
        return "Esa nota es parte de la estructura base de la bóveda; no la elimino."
    rutas_antes = listar_rutas_relativas()
    send2trash(str(resolver_ruta(ruta_real)))
    for otra in listar_rutas_relativas():
        if es_de_sistema(otra):
            continue
        contenido = leer_nota(otra) or ""
        nuevo, quitados = quitar_items(contenido, SECCION_RELACIONADO, lambda item: _destino_de_item(item, rutas_antes) == ruta_real)
        if quitados:
            _escribir(otra, nuevo)
    quitar_de_indice(ruta_real, rutas_antes)
    _refrescar_indice()
    return f"Nota movida a la papelera: {ruta_real}"


def pregunta_eliminar(argumentos: dict) -> str:
    nombre = argumentos.get("ruta", "")
    ruta_real = ruta_a_eliminar(nombre) or nombre
    return f"¿Confirmas que elimine la nota '{ruta_real}'? Se irá a la papelera."
