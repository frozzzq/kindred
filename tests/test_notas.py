import numpy as np
import pytest

from src.engines import embeddings
from src.obsidian import notas
from src.obsidian.notas import (
    agregar_a_nota,
    conectar_notas,
    crear_nota,
    desconectar_notas,
    editar_nota,
    eliminar_nota,
    mover_nota,
    pregunta_eliminar,
    sugerir_conexiones,
)

# Embeddings falsos pero coherentes: una dimensión por tema. Dos textos del mismo tema quedan
# cerca (~1) y de temas distintos lejos (~0), como con el modelo real.
TEMAS = {
    "programacion": ("node", "javascript", "express", "servidor", "backend", "npm", "api"),
    "anime": ("one piece", "luffy", "manga", "anime", "pirata"),
    "jarvis": ("jarvis", "ollama", "asistente", "voz"),
}


def _vector(texto: str) -> np.ndarray:
    texto = texto.lower()
    vector = np.array([sum(texto.count(p) for p in palabras) for palabras in TEMAS.values()] + [0.15], dtype=np.float32)
    return vector / np.linalg.norm(vector)


@pytest.fixture
def boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(embeddings, "embeber", lambda textos: np.array([_vector(t) for t in textos]))
    monkeypatch.setattr(embeddings, "embeber_consulta", lambda consulta: _vector(consulta))
    enviadas = []
    monkeypatch.setattr(notas, "send2trash", enviadas.append)

    def escribir(ruta, contenido=""):
        archivo = tmp_path / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")

    def leer(ruta):
        return (tmp_path / ruta).read_text(encoding="utf-8")

    class Boveda:
        pass

    b = Boveda()
    b.raiz, b.escribir, b.leer, b.enviadas = tmp_path, escribir, leer, enviadas
    return b


# ---------- crear ----------


def test_crear_nota_con_propiedades_y_contenido(boveda):
    resultado = crear_nota("04-Conocimiento/Idea.md", "Una idea nueva.", etiquetas="idea, #prueba")

    contenido = boveda.leer("04-Conocimiento/Idea.md")
    assert contenido.startswith("---\ncreado: ")
    assert "tags: [idea, prueba]" in contenido
    assert contenido.rstrip().endswith("Una idea nueva.")
    assert "creada" in resultado.lower()


def test_crear_nota_sin_carpeta_va_a_conocimiento(boveda):
    crear_nota("Idea suelta", "algo sin tema")

    assert (boveda.raiz / "04-Conocimiento" / "Idea suelta.md").exists()


def test_crear_nota_sin_carpeta_va_junto_a_las_de_su_tema(boveda):
    boveda.escribir("04-Conocimiento/Programación/Node.js.md", "Node es javascript en el servidor, con npm.")
    crear_nota("Semilla", "semilla para que el índice exista")  # indexa la bóveda

    crear_nota("Express", "Express es un framework de node para hacer una api en el servidor.")

    assert (boveda.raiz / "04-Conocimiento" / "Programación" / "Express.md").exists()


def test_crear_nota_no_sobrescribe_ni_duplica_el_nombre(boveda):
    boveda.escribir("03-Proyectos/Jarvis.md", "original")

    misma_ruta = crear_nota("03-Proyectos/Jarvis.md", "nuevo")
    otra_carpeta = crear_nota("04-Conocimiento/Jarvis.md", "nuevo")

    assert boveda.leer("03-Proyectos/Jarvis.md") == "original"
    assert not (boveda.raiz / "04-Conocimiento" / "Jarvis.md").exists()
    assert "ya existe" in misma_ruta.lower() and "ya existe" in otra_carpeta.lower()


@pytest.mark.parametrize("ruta", ["../fuera.md", "00-Sistema/Nota.md"])
def test_crear_nota_rechaza_fuera_de_la_boveda_y_el_sistema(boveda, ruta):
    resultado = crear_nota(ruta, "contenido")

    assert "creada" not in resultado.lower()
    assert not (boveda.raiz.parent / "fuera.md").exists()
    assert not (boveda.raiz / "00-Sistema" / "Nota.md").exists()


# ---------- conexiones automáticas ----------


def test_crear_nota_se_conecta_con_su_tema(boveda):
    boveda.escribir("04-Conocimiento/Node.js.md", "Node es javascript en el servidor, con npm y express.")

    resultado = crear_nota("04-Conocimiento/Express.md", "Express: framework de node para una api backend.")

    contenido = boveda.leer("04-Conocimiento/Express.md")
    assert "## Relacionado\n- [[Node.js]]" in contenido
    assert "Node.js" in resultado


def test_crear_nota_sin_tema_en_comun_no_se_conecta_con_nada(boveda):
    """Caso real: una nota de One Piece se conectó con PRUEBAS_MANUALES y Registro-Acciones."""
    boveda.escribir("PRUEBAS_MANUALES.md", "Pruebas manuales: crea una nota sobre la historia y verifica que se conecte.")
    boveda.escribir("00-Sistema/Registro-Acciones.md", "crear_nota historia de one piece manga luffy anime pirata")
    boveda.escribir("04-Conocimiento/Node.js.md", "Node es javascript en el servidor.")

    crear_nota("04-Conocimiento/Historia de One Piece.md", "One Piece es un manga de Luffy, un pirata. Historia del anime.")

    assert "## Relacionado" not in boveda.leer("04-Conocimiento/Historia de One Piece.md")


def test_nunca_conecta_con_listas_de_tareas_ni_notas_del_sistema(boveda):
    boveda.escribir("02-Tareas/Pendientes.md", "- [ ] estudiar node y express para el servidor")
    boveda.escribir("00-Sistema/Logs/2026-09.md", "node express servidor javascript npm api")

    crear_nota("04-Conocimiento/Express.md", "Express: framework de node para una api backend.")

    assert "## Relacionado" not in boveda.leer("04-Conocimiento/Express.md")


def test_notas_de_un_area_van_a_su_indice_y_el_area_a_inicio(boveda):
    boveda.escribir("Inicio.md", "# Inicio\n")

    crear_nota("04-Conocimiento/Programación/Node.js.md", "Node es javascript en el servidor.")

    indice_area = boveda.leer("04-Conocimiento/Programación/Programación.md")
    assert "## Notas\n- [[Node.js]]" in indice_area
    assert "## Áreas\n- [[Programación]]" in boveda.leer("Inicio.md")


# ---------- conectar / desconectar ----------


def test_conectar_por_nombre_con_motivo(boveda):
    boveda.escribir("03-Proyectos/Jarvis.md", "Asistente")
    boveda.escribir("04-Conocimiento/Ollama.md", "Servidor de modelos")

    resultado = conectar_notas("Jarvis", "ollama", motivo="motor local de Crimson")

    assert "- [[Ollama]] — motor local de Crimson" in boveda.leer("03-Proyectos/Jarvis.md")
    assert "Conecté" in resultado


def test_conectar_una_nota_consigo_misma_se_rechaza(boveda):
    """Caso real: tras rechazar crear la misma nota, el modelo la conectó consigo misma."""
    boveda.escribir("03-Proyectos/Jarvis.md", "Asistente")

    resultado = conectar_notas("03-Proyectos/Jarvis.md", "Jarvis")

    assert "misma nota" in resultado
    assert "## Relacionado" not in boveda.leer("03-Proyectos/Jarvis.md")


def test_conectar_no_duplica_y_desconectar_quita(boveda):
    boveda.escribir("a.md", "nota a")
    boveda.escribir("b.md", "nota b")
    conectar_notas("a", "b")

    segunda = conectar_notas("a", "b")
    assert boveda.leer("a.md").count("[[b]]") == 1
    assert "ya estaba conectada" in segunda

    desconectar_notas("a", "b")
    assert "[[b]]" not in boveda.leer("a.md")
    assert "## Relacionado" not in boveda.leer("a.md")


def test_conectar_con_nota_inexistente_o_del_sistema(boveda):
    boveda.escribir("a.md", "nota a")
    boveda.escribir("00-Sistema/Registro-Acciones.md", "registro")

    assert "No encontré" in conectar_notas("a", "Cosa inventada que no existe")
    assert "uso interno" in conectar_notas("a", "00-Sistema/Registro-Acciones.md")


def test_sugerir_conexiones_muestra_las_parecidas(boveda):
    boveda.escribir("04-Conocimiento/Node.js.md", "Node es javascript en el servidor con npm.")
    boveda.escribir("04-Conocimiento/Express.md", "Express es un framework de node para una api.")
    boveda.escribir("04-Conocimiento/One Piece.md", "Luffy es un pirata del manga One Piece.")
    crear_nota("Semilla", "indexar")

    resultado = sugerir_conexiones("Node.js")

    assert "04-Conocimiento/Express.md" in resultado
    assert "One Piece" not in resultado


# ---------- agregar / editar ----------


def test_agregar_a_nota_queda_antes_de_relacionado(boveda):
    boveda.escribir("04-Conocimiento/Node.js.md", "Intro\n\n## Relacionado\n- [[Express]]\n")

    agregar_a_nota("Node.js", "## Event loop\nAtiende tareas sin bloquear.")

    contenido = boveda.leer("04-Conocimiento/Node.js.md")
    assert contenido.index("Event loop") < contenido.index("## Relacionado")
    assert contenido.startswith("Intro")


@pytest.mark.parametrize("ruta", ["02-Tareas/Pendientes.md", "00-Sistema/HEARTBEAT.md"])
def test_agregar_a_nota_no_toca_tareas_ni_sistema(boveda, ruta):
    boveda.escribir(ruta, "original")

    agregar_a_nota(ruta, "texto")

    assert boveda.leer(ruta) == "original"


def test_editar_nota_conserva_propiedades_y_relacionado_y_respalda(boveda, monkeypatch, tmp_path_factory):
    boveda.escribir("04-Conocimiento/Node.js.md", "---\ncreado: 2026-09-01\n---\nViejo\n\n## Relacionado\n- [[Express]]\n")

    resultado = editar_nota("Node.js", "Nuevo contenido corregido.")

    contenido = boveda.leer("04-Conocimiento/Node.js.md")
    assert contenido.startswith("---\ncreado: 2026-09-01\n---\nNuevo contenido corregido.")
    assert "Viejo" not in contenido
    assert "## Relacionado\n- [[Express]]" in contenido
    assert "respaldada" in resultado
    from src.local import carpeta_local

    respaldos = list((carpeta_local() / "respaldos").rglob("*.md"))
    assert respaldos and "Viejo" in respaldos[0].read_text(encoding="utf-8")


# ---------- mover ----------


def test_mover_nota_a_otra_carpeta_y_renombrar_actualiza_enlaces(boveda):
    boveda.escribir("04-Conocimiento/Node.js.md", "Node")
    boveda.escribir("03-Proyectos/Jarvis.md", "Usa [[Node.js]] y [[Node.js|node]].\n\n## Relacionado\n- [[Node.js]]\n")

    resultado = mover_nota("Node.js", "04-Conocimiento/Programación/Node avanzado.md")

    assert (boveda.raiz / "04-Conocimiento" / "Programación" / "Node avanzado.md").exists()
    assert not (boveda.raiz / "04-Conocimiento" / "Node.js.md").exists()
    jarvis = boveda.leer("03-Proyectos/Jarvis.md")
    assert "[[Node avanzado]]" in jarvis and "[[Node avanzado|node]]" in jarvis and "[[Node.js" not in jarvis
    assert "1 nota" in resultado


def test_mover_nota_solo_a_carpeta_conserva_el_nombre(boveda):
    boveda.escribir("04-Conocimiento/Node.js.md", "Node")

    mover_nota("Node.js", "04-Conocimiento/Programación")

    assert (boveda.raiz / "04-Conocimiento" / "Programación" / "Node.js.md").exists()


def test_mover_no_sobrescribe_ni_mueve_notas_base(boveda):
    boveda.escribir("a.md", "a")
    boveda.escribir("b.md", "b")
    boveda.escribir("02-Tareas/Pendientes.md", "- [ ] x")

    assert "Ya existe" in mover_nota("a", "b")
    assert "estructura base" in mover_nota("Pendientes", "04-Conocimiento")
    assert boveda.leer("a.md") == "a"


# ---------- eliminar ----------


def test_eliminar_manda_a_la_papelera_y_limpia_enlaces(boveda):
    boveda.escribir("04-Conocimiento/Vieja.md", "vieja")
    boveda.escribir("04-Conocimiento/Otra.md", "otra\n\n## Relacionado\n- [[Vieja]]\n- [[Otra más]]\n")

    resultado = eliminar_nota("Vieja")

    assert boveda.enviadas == [str(boveda.raiz / "04-Conocimiento" / "Vieja.md")]
    otra = boveda.leer("04-Conocimiento/Otra.md")
    assert "[[Vieja]]" not in otra and "[[Otra más]]" in otra
    assert "papelera" in resultado.lower()


def test_eliminar_solo_por_nombre_exacto_y_nunca_notas_base(boveda):
    boveda.escribir("04-Conocimiento/Proyecto X.md", "x")
    boveda.escribir("01-Perfil/Yo.md", "yo")

    assert "No encontré" in eliminar_nota("Proyecto Y")
    assert "estructura base" in eliminar_nota("Yo")
    assert boveda.enviadas == []


def test_la_pregunta_de_eliminar_muestra_la_ruta_real(boveda):
    boveda.escribir("04-Conocimiento/Vieja.md", "vieja")

    assert pregunta_eliminar({"ruta": "vieja"}) == "¿Confirmas que elimine la nota '04-Conocimiento/Vieja.md'? Se irá a la papelera."


def test_una_mencion_por_titulo_conecta_aunque_el_texto_no_se_parezca(boveda):
    """Como las "menciones sin enlazar" de Obsidian: si una nota nombra a otra, se relacionan de verdad."""
    boveda.escribir("04-Conocimiento/Herramientas/Ollama.md", "Servidor de modelos locales.")

    resultado = crear_nota("03-Proyectos/Casa inteligente.md", "Quiero controlar las luces usando Ollama en la PC.")

    assert "[[Ollama]]" in boveda.leer("03-Proyectos/Casa inteligente.md")
    assert "Ollama" in resultado


def test_una_mencion_como_parte_de_otra_palabra_no_cuenta(boveda):
    boveda.escribir("04-Conocimiento/Git.md", "Control de versiones del backend en el servidor.")

    crear_nota("04-Conocimiento/Arte.md", "El manga y el arte digital de un pirata.")

    assert "[[Git]]" not in boveda.leer("04-Conocimiento/Arte.md")


def test_sugerir_explica_el_motivo_y_omite_las_ya_conectadas(boveda):
    boveda.escribir("04-Conocimiento/Herramientas/Ollama.md", "Servidor de modelos.")
    boveda.escribir("04-Conocimiento/Node.js.md", "Node es javascript en el servidor con npm.")
    boveda.escribir("04-Conocimiento/Express.md", "Express es un framework de node para una api.\n\n## Relacionado\n- [[Node.js]]\n")
    boveda.escribir("03-Proyectos/Jarvis.md", "Asistente que corre en Ollama con javascript en el servidor y npm.")

    resultado = sugerir_conexiones("Jarvis")

    assert "Ollama.md (menciona «Ollama»)" in resultado
    assert "Jarvis.md («Jarvis» la menciona)" in sugerir_conexiones("Ollama")
    assert "Node.js.md (" in resultado and "% parecida)" in resultado
    # Express ya enlaza a Node.js: no se sugiere de nuevo en ninguna de las dos direcciones.
    assert "Node.js.md (" not in sugerir_conexiones("Express")
    assert "Express.md (" not in sugerir_conexiones("Node.js")
