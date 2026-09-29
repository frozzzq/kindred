"""Formato de una nota: frontmatter (propiedades de Obsidian) y secciones que mantienen las herramientas.

- "## Relacionado": enlaces a notas del mismo tema. Siempre va al final de la nota.
- "## Notas": en las notas índice de carpeta, la lista de notas de esa carpeta.

Todo aquí son funciones puras sobre texto (sin tocar archivos), para poder probarlas solas y
usarlas tanto al escribir notas como al indexarlas.
"""

import re

SECCION_RELACIONADO = "## Relacionado"
SECCION_NOTAS = "## Notas"

_ENCABEZADO_NIVEL_1_O_2 = re.compile(r"^#{1,2}\s")


def separar_frontmatter(contenido: str) -> tuple[str, str]:
    """(frontmatter con sus líneas ---, resto). Frontmatter vacío si la nota no tiene."""
    if not contenido.startswith("---\n"):
        return "", contenido
    fin = contenido.find("\n---", 4)
    if fin == -1:
        return "", contenido
    corte = contenido.find("\n", fin + 4)
    corte = len(contenido) if corte == -1 else corte + 1
    return contenido[:corte], contenido[corte:]


def propiedades(frontmatter: str) -> dict[str, str]:
    """Propiedades simples "clave: valor" del frontmatter (sin interpretar YAML completo)."""
    resultado = {}
    for linea in frontmatter.splitlines():
        if ":" in linea and not linea.startswith((" ", "-")):
            clave, valor = linea.split(":", 1)
            resultado[clave.strip()] = valor.strip()
    return resultado


def _limites_seccion(lineas: list[str], encabezado: str) -> tuple[int, int] | None:
    """(índice del encabezado, índice donde termina la sección) o None si no existe."""
    buscado = encabezado.strip().lower()
    for inicio, linea in enumerate(lineas):
        if linea.strip().lower() == buscado:
            fin = inicio + 1
            while fin < len(lineas) and not _ENCABEZADO_NIVEL_1_O_2.match(lineas[fin]):
                fin += 1
            return inicio, fin
    return None


def items_de_seccion(contenido: str, encabezado: str) -> list[str]:
    """Líneas de lista ("- ...") de una sección, sin el guion."""
    lineas = contenido.splitlines()
    limites = _limites_seccion(lineas, encabezado)
    if limites is None:
        return []
    inicio, fin = limites
    return [linea.strip()[2:].strip() for linea in lineas[inicio + 1 : fin] if linea.strip().startswith("- ")]


def quitar_seccion(contenido: str, encabezado: str) -> str:
    lineas = contenido.splitlines()
    limites = _limites_seccion(lineas, encabezado)
    if limites is None:
        return contenido
    inicio, fin = limites
    return "\n".join(lineas[:inicio] + lineas[fin:]).rstrip() + "\n"


def _con_salto_final(texto: str) -> str:
    return texto.rstrip() + "\n"


def insertar_antes_de_relacionado(contenido: str, texto: str, separar: bool = True) -> str:
    """Agrega texto al final del cuerpo de la nota, pero antes de "## Relacionado" (que va al final).

    separar=False lo pega sin línea en blanco: para sumar un elemento a una lista.
    """
    lineas = contenido.rstrip().splitlines()
    limites = _limites_seccion(lineas, SECCION_RELACIONADO)
    nuevo = texto.strip("\n").splitlines()
    if limites is None:
        separador = [""] if lineas and separar else []
        return _con_salto_final("\n".join(lineas + separador + nuevo))
    inicio, _fin = limites
    cuerpo = lineas[:inicio]
    while cuerpo and not cuerpo[-1].strip():
        cuerpo.pop()
    separador = [""] if cuerpo and separar else []
    return _con_salto_final("\n".join(cuerpo + separador + nuevo + [""] + lineas[inicio:]))


def agregar_item(contenido: str, encabezado: str, item: str) -> str:
    """Agrega "- item" a una sección, creándola si falta ("## Relacionado" al final; otras, antes de ella)."""
    lineas = contenido.rstrip().splitlines()
    limites = _limites_seccion(lineas, encabezado)
    if limites is not None:
        inicio, fin = limites
        ultimo = fin
        while ultimo > inicio + 1 and not lineas[ultimo - 1].strip():
            ultimo -= 1
        return _con_salto_final("\n".join(lineas[:ultimo] + [f"- {item}"] + lineas[ultimo:]))
    seccion = f"{encabezado}\n- {item}"
    if encabezado == SECCION_RELACIONADO:
        separador = [""] if lineas else []
        return _con_salto_final("\n".join(lineas + separador + seccion.splitlines()))
    return insertar_antes_de_relacionado(contenido, seccion)


def quitar_items(contenido: str, encabezado: str, debe_quitarse) -> tuple[str, int]:
    """Quita de una sección los items para los que debe_quitarse(item) es True. Si queda vacía, la quita."""
    lineas = contenido.splitlines()
    limites = _limites_seccion(lineas, encabezado)
    if limites is None:
        return contenido, 0
    inicio, fin = limites
    conservadas, quitadas = [], 0
    for linea in lineas[inicio + 1 : fin]:
        if linea.strip().startswith("- ") and debe_quitarse(linea.strip()[2:].strip()):
            quitadas += 1
        else:
            conservadas.append(linea)
    if not quitadas:
        return contenido, 0
    if not any(linea.strip() for linea in conservadas):
        nuevas = lineas[:inicio] + lineas[fin:]
    else:
        nuevas = lineas[: inicio + 1] + conservadas + lineas[fin:]
    while nuevas and not nuevas[-1].strip():
        nuevas.pop()
    return ("\n".join(nuevas) + "\n") if nuevas else "", quitadas


def texto_para_indexar(contenido: str) -> str:
    """Lo que dice la nota, sin frontmatter ni "## Relacionado".

    Los enlaces de Relacionado no son contenido: si contaran, dos notas ya conectadas se verían
    cada vez más parecidas entre sí y las conexiones se reforzarían solas.
    """
    _frontmatter, cuerpo = separar_frontmatter(contenido)
    return quitar_seccion(cuerpo, SECCION_RELACIONADO).strip()
