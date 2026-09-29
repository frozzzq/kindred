from src.obsidian.formato import (
    SECCION_NOTAS,
    SECCION_RELACIONADO,
    agregar_item,
    insertar_antes_de_relacionado,
    items_de_seccion,
    propiedades,
    quitar_items,
    separar_frontmatter,
    texto_para_indexar,
)


def test_separar_frontmatter_y_propiedades():
    frontmatter, resto = separar_frontmatter("---\ncreado: 2026-09-29\ntags: [a, b]\n---\nCuerpo\n")

    assert frontmatter == "---\ncreado: 2026-09-29\ntags: [a, b]\n---\n"
    assert resto == "Cuerpo\n"
    assert propiedades(frontmatter) == {"creado": "2026-09-29", "tags": "[a, b]"}
    assert separar_frontmatter("Sin propiedades") == ("", "Sin propiedades")


def test_relacionado_se_crea_al_final_y_se_extiende():
    contenido = agregar_item("Texto", SECCION_RELACIONADO, "[[A]]")
    contenido = agregar_item(contenido, SECCION_RELACIONADO, "[[B]] — motivo")

    assert contenido == "Texto\n\n## Relacionado\n- [[A]]\n- [[B]] — motivo\n"
    assert items_de_seccion(contenido, SECCION_RELACIONADO) == ["[[A]]", "[[B]] — motivo"]


def test_otras_secciones_van_antes_de_relacionado():
    contenido = "Intro\n\n## Relacionado\n- [[A]]\n"

    contenido = agregar_item(contenido, SECCION_NOTAS, "[[Nota]]")

    assert contenido.index("## Notas") < contenido.index("## Relacionado")


def test_insertar_antes_de_relacionado():
    assert insertar_antes_de_relacionado("Intro\n\n## Relacionado\n- [[A]]\n", "Nuevo") == (
        "Intro\n\nNuevo\n\n## Relacionado\n- [[A]]\n"
    )
    assert insertar_antes_de_relacionado("", "Primero") == "Primero\n"


def test_quitar_items_y_la_seccion_si_queda_vacia():
    contenido = "Texto\n\n## Relacionado\n- [[A]]\n- [[B]]\n"

    sin_a, quitados = quitar_items(contenido, SECCION_RELACIONADO, lambda item: "[[A]]" in item)
    vacio, _ = quitar_items(sin_a, SECCION_RELACIONADO, lambda item: True)

    assert quitados == 1 and "[[A]]" not in sin_a and "[[B]]" in sin_a
    assert vacio == "Texto\n"


def test_texto_para_indexar_quita_propiedades_y_relacionado():
    contenido = "---\ncreado: x\n---\nLo importante\n\n## Relacionado\n- [[Otra]]\n"

    assert texto_para_indexar(contenido) == "Lo importante"
