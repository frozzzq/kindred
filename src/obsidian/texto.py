"""Utilidades de texto compartidas: comparar sin importar acentos/mayúsculas y partir en palabras para buscar.

Vive aparte (sin importar nada del proyecto) para que cualquier módulo lo use sin ciclos de imports.
"""

import re
import unicodedata

# Palabras que no ayudan a distinguir de qué habla una nota: se ignoran al buscar por palabras.
PALABRAS_VACIAS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada casi como con contra cual cuales
    cuando de del desde donde dos el ella ellas ellos en entre era eran es esa esas ese eso esos esta estan estas
    este esto estos fue fueron ha han hace hacer hasta hay la las le les lo los mas me mi mis mucho muy nada ni no
    nos nosotros nuestra nuestro o otra otras otro otros para pero poco por porque que quien se sea segun ser si
    sin sobre solo son su sus tal tambien tan tanto te tener tengo tiene tienen todo todos tu tus un una unas uno
    unos usted ya yo sabes dime dame puedes quiero oye hola favor cosa cosas nota notas acerca tengo tenia
    """.split()
)


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar textos sin importar cómo se escribieron."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


def palabras(texto: str) -> list[str]:
    """Palabras significativas (normalizadas, sin vacías), con un recorte ligero del plural.

    "Node.js" queda como "node" y "js"; "procesos" como "proceso". No es un lematizador: solo lo
    suficiente para que la búsqueda por palabras encuentre plural y singular.
    """
    resultado = []
    for palabra in re.findall(r"[a-z0-9ñ]+", normalizar(texto)):
        if len(palabra) < 2 or palabra in PALABRAS_VACIAS:
            continue
        if len(palabra) > 4 and palabra.endswith("s") and not palabra.endswith("ss"):
            palabra = palabra[:-1]
        resultado.append(palabra)
    return resultado
