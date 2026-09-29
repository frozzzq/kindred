"""Una bóveda de ejemplo, realista y desechable, para probar a los agentes sin tocar la real.

Las fechas de los pendientes se calculan respecto a hoy (vencido, hoy, viernes), para que las
pruebas signifiquen lo mismo cualquier día que se corran.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.local import carpeta_local


def _proximo_viernes(ahora: datetime) -> datetime:
    return ahora + timedelta(days=(4 - ahora.weekday()) % 7 or 7)


def notas_de_ejemplo(ahora: datetime | None = None) -> dict[str, str]:
    ahora = ahora or datetime.now()
    hace_tres = (ahora - timedelta(days=3)).date().isoformat()
    hoy = ahora.date().isoformat()
    viernes = _proximo_viernes(ahora).date().isoformat()
    return {
        "Inicio.md": "# Inicio\n\n## Áreas\n- [[Programación]]\n- [[Universidad]]\n",
        "01-Perfil/Yo.md": "- Se llama Josué\n- Estudia ingeniería en software en la UAS\n- Le gusta el café sin azúcar\n",
        "01-Perfil/Contactos.md": "- **Camila**: su novia, vive en Los Mochis\n- **Cristiano**: amigo de la infancia, le dicen Güero\n",
        "01-Perfil/Patrones.md": "- Suele pedir sus pendientes por la mañana\n",
        "02-Tareas/Pendientes.md": (
            f"- [ ] Entregar el reporte de bases de datos 📅 {hace_tres} (agregado {hace_tres} 10:00)\n"
            f"- [ ] Llamar a mi mamá 📅 {hoy} ⏰ {hoy} 23:30 (agregado {hoy} 08:00)\n"
            f"- [ ] Entregar el proyecto de Jarvis 📅 {viernes} (agregado {hoy} 08:00)\n"
            f"- [ ] Comprar leche (agregado {hoy} 08:00)\n"
        ),
        "02-Tareas/Recurrentes.md": "- Tomar medicina 🔁 diario 21:00 (agregado 2026-09-28 15:50)\n",
        "02-Tareas/Completadas.md": "- [x] Comprar croquetas (completado 2026-09-28 15:43)\n",
        "03-Proyectos/Jarvis.md": (
            "---\ncreado: 2026-09-20\nestado: activo\n---\n## Objetivo\nAsistente personal de voz, local, con dos "
            "agentes: Crimson (Ollama con qwen3:8b) y Clover (Gemini Flash). Su memoria es esta bóveda de Obsidian.\n\n"
            "## Estado actual\nVoz con faster-whisper y edge-tts, recordatorios con el núcleo, UI en Flet.\n\n"
            "## Próximos pasos\n- Canal de Telegram\n- Llamadas con Twilio\n"
        ),
        "04-Conocimiento/Programación/Programación.md": (
            "---\ntipo: indice\n---\nNotas del área de Programación.\n\n## Notas\n- [[Node.js]]\n- [[Express]]\n- [[Git]]\n"
        ),
        "04-Conocimiento/Programación/Node.js.md": (
            "---\ncreado: 2026-09-10\ntags: [javascript, backend]\n---\n"
            "Node.js es un entorno de ejecución de JavaScript del lado del servidor, construido sobre el motor V8 de Chrome.\n\n"
            "## Event loop\nNode usa un solo hilo con un event loop: las operaciones de entrada/salida (leer archivos, "
            "consultas a la red) no bloquean; se registran callbacks o promesas y el loop sigue atendiendo otras cosas.\n\n"
            "## npm\nnpm es el gestor de paquetes. `npm init` crea el package.json y `npm install` instala dependencias.\n\n"
            "## Módulos\nCommonJS usa require y module.exports; los ES modules usan import/export.\n"
        ),
        "04-Conocimiento/Programación/Express.md": (
            "---\ncreado: 2026-09-12\ntags: [javascript, backend]\n---\n"
            "Express es un framework minimalista de Node.js para crear APIs REST y servidores web.\n\n"
            "## Rutas\n`app.get('/usuarios', handler)` define una ruta. Los parámetros van en req.params.\n\n"
            "## Middleware\nFunciones que reciben (req, res, next) y se ejecutan en orden; sirven para autenticación, "
            "logs o parsear JSON con express.json().\n"
        ),
        "04-Conocimiento/Programación/Git.md": (
            "Git es un sistema de control de versiones. Un commit guarda una foto del proyecto; las ramas (branch) "
            "permiten trabajar en paralelo y luego se unen con merge o rebase.\n"
        ),
        "04-Conocimiento/Universidad/Universidad.md": "---\ntipo: indice\n---\nNotas de la universidad.\n\n## Notas\n- [[Bases de datos]]\n",
        "04-Conocimiento/Universidad/Bases de datos.md": (
            "Materia de bases de datos, tercer semestre.\n\n## Normalización\nLa primera forma normal (1FN) pide valores "
            "atómicos; la segunda (2FN), que no haya dependencias parciales de la llave; la tercera (3FN), que no haya "
            "dependencias transitivas.\n\n## Joins\nINNER JOIN devuelve solo las filas que coinciden en ambas tablas; LEFT "
            "JOIN devuelve todas las de la izquierda aunque no tengan pareja.\n"
        ),
        "04-Conocimiento/Herramientas/Ollama.md": (
            "Ollama es un servidor para correr modelos de lenguaje localmente (qwen3, mistral) en la GPU. Expone una API "
            "HTTP en el puerto 11434 y también sirve modelos de embeddings.\n"
        ),
        "05-Decisiones/Usar Flet para la UI.md": (
            "## Contexto\nNecesitaba una UI de escritorio en Python.\n\n## Decisión y porqué\nFlet: se programa en Python, "
            "se ve moderno y permite dibujar el grafo 3D en un canvas.\n"
        ),
    }


def crear_boveda_de_pruebas(nombre: str = "boveda-pruebas", desde: Path | None = None) -> Path:
    """Crea (desde cero) una bóveda desechable en %LOCALAPPDATA%\\kindred\\<nombre>.

    Con `desde`, copia esa bóveda (por ejemplo la real) en vez de usar las notas de ejemplo.
    """
    destino = carpeta_local() / nombre
    if destino.exists():
        shutil.rmtree(destino)
    if desde is not None:
        shutil.copytree(desde, destino, ignore=shutil.ignore_patterns(".obsidian", ".trash"))
        return destino
    for ruta, contenido in notas_de_ejemplo().items():
        archivo = destino / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")
    return destino
