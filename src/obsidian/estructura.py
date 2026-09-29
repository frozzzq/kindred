"""Estructura de la bóveda: qué carpetas hay, para qué sirve cada una y qué notas son de quién.

Tres categorías de notas, que deciden qué se busca y qué se conecta:
- Sistema (00-Sistema/): registros, estado y plantillas de la máquina. Nunca es conocimiento: no
  sale en búsquedas, no se conecta y no aparece en el grafo (antes el registro de acciones "ganaba"
  cualquier búsqueda y se enlazaba con todo, porque contiene de todo).
- Operativas (02-Tareas/, 01-Perfil/Patrones.md): listas que el agente mantiene. Se pueden buscar,
  pero no tiene sentido enlazarlas por tema.
- Conocimiento: todo lo demás (proyectos, áreas de estudio, decisiones, diario, personas).

Cada carpeta puede tener una nota índice con su mismo nombre ("04-Conocimiento/Programación/
Programación.md"): lista las notas de la carpeta y le da estructura al grafo, como un mapa de
contenido (MOC) de Obsidian. Las herramientas la mantienen al crear, mover o borrar notas.
"""

from pathlib import PurePosixPath

from src.obsidian.config import ruta_boveda

CARPETA_SISTEMA = "00-Sistema"
CARPETA_LOGS = "00-Sistema/Logs"
CARPETA_PLANTILLAS = "00-Sistema/Plantillas"
CARPETA_CONOCIMIENTO = "04-Conocimiento"
CARPETA_DIARIO = "06-Diario"
NOTA_INICIO = "Inicio.md"

# Lo que cada carpeta guarda: va en el prompt de los agentes para que sepan dónde está cada cosa.
CARPETAS = {
    "00-Sistema": "uso interno (registros, estado, plantillas); no es conocimiento del usuario",
    "01-Perfil": "quién es el usuario: Yo (perfil), Contactos (personas importantes), Patrones (hábitos)",
    "02-Tareas": "Pendientes, Completadas y Recurrentes",
    "03-Proyectos": "una nota por proyecto: objetivo, estado, próximos pasos",
    "04-Conocimiento": "lo que el usuario aprende, en una subcarpeta por área (cada área con su nota índice)",
    "05-Decisiones": "decisiones importantes y su porqué",
    "06-Diario": "una nota por día (AAAA-MM-DD) con lo que pasó",
    "07-Archivo": "lo que ya no está activo",
}

NOTAS_OPERATIVAS = frozenset(
    {"02-Tareas/Pendientes.md", "02-Tareas/Completadas.md", "02-Tareas/Recurrentes.md", "01-Perfil/Patrones.md"}
)

NOTAS_INICIALES = {
    "01-Perfil/Yo.md": "",
    "01-Perfil/Contactos.md": "",
    "01-Perfil/Patrones.md": "",
    "02-Tareas/Pendientes.md": "",
    "02-Tareas/Completadas.md": "",
    "02-Tareas/Recurrentes.md": "",
    "00-Sistema/HEARTBEAT.md": "",
    NOTA_INICIO: """# Inicio

Punto de entrada de la bóveda. Crimson y Clover la mantienen ordenada: cada nota nueva cae en su
carpeta, se agrega al índice de esa carpeta y se conecta con las notas del mismo tema.

## Mapa
- [[Yo]] · [[Contactos]]
- [[Pendientes]] · [[Recurrentes]] · [[Completadas]]
- Proyectos: carpeta `03-Proyectos`
- Conocimiento: carpeta `04-Conocimiento` (una subcarpeta por área)
- Decisiones: carpeta `05-Decisiones`
- Diario: carpeta `06-Diario`
""",
}

PLANTILLAS = {
    "Conocimiento.md": "---\ncreado: {{date}}\ntags: []\n---\n\n## Idea principal\n\n## Detalles\n\n## Dudas\n",
    "Proyecto.md": "---\ncreado: {{date}}\nestado: activo\n---\n\n## Objetivo\n\n## Estado actual\n\n## Próximos pasos\n- [ ] \n",
    "Decisión.md": "---\ncreado: {{date}}\n---\n\n## Contexto\n\n## Opciones\n\n## Decisión y porqué\n",
    "Diario.md": "---\nfecha: {{date}}\n---\n\n## Qué pasó\n\n## Qué aprendí\n",
    "Persona.md": "---\ncreado: {{date}}\n---\n\n## Quién es\n\n## Datos\n\n## Notas\n",
}


def es_de_sistema(ruta: str) -> bool:
    return ruta.startswith(CARPETA_SISTEMA + "/")


def es_buscable(ruta: str) -> bool:
    """Puede salir en búsquedas y en el contexto de una respuesta."""
    return not es_de_sistema(ruta)


def es_indice(ruta: str) -> bool:
    """Nota índice de su carpeta ("X/X.md") o la nota de Inicio."""
    camino = PurePosixPath(ruta)
    return ruta == NOTA_INICIO or (len(camino.parts) > 1 and camino.stem == camino.parent.name)


def es_conocimiento(ruta: str) -> bool:
    """Se puede conectar por tema con otras notas."""
    return not es_de_sistema(ruta) and ruta not in NOTAS_OPERATIVAS and not es_indice(ruta)


def ruta_indice(carpeta: str) -> str:
    """Ruta de la nota índice de una carpeta: "04-Conocimiento/Programación" → ".../Programación.md"."""
    return f"{carpeta}/{PurePosixPath(carpeta).name}.md"


def asegurar_estructura_boveda() -> None:
    """Crea carpetas, notas base y plantillas que falten. Nunca sobrescribe una nota existente."""
    boveda = ruta_boveda()
    for carpeta in (*CARPETAS, CARPETA_LOGS, CARPETA_PLANTILLAS):
        (boveda / carpeta).mkdir(parents=True, exist_ok=True)
    for ruta_relativa, contenido in NOTAS_INICIALES.items():
        ruta = boveda / ruta_relativa
        if not ruta.exists():
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8")
    for nombre, contenido in PLANTILLAS.items():
        ruta = boveda / CARPETA_PLANTILLAS / nombre
        if not ruta.exists():
            ruta.write_text(contenido, encoding="utf-8")
