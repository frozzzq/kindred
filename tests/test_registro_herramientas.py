from unittest.mock import patch

import pytest

from src.actions.system_control import ResultadoAccion
from src.herramientas.catalogo import REGISTRO, seleccionar_grupos
from src.herramientas.registro import (
    MENSAJE_CANCELADO,
    MENSAJE_MODO_SEGURO,
    ContextoEjecucion,
    Herramienta,
    Registro,
    Riesgo,
)


def _no_debe_confirmar(descripcion):
    raise AssertionError(f"no debía pedir confirmación: {descripcion}")


class Espia:
    """Una herramienta falsa que recuerda con qué se llamó."""

    def __init__(self, resultado="hecho"):
        self.llamadas = []
        self.resultado = resultado

    def __call__(self, **argumentos):
        self.llamadas.append(argumentos)
        return self.resultado


def _registro(riesgo, funcion=None, auditados=None):
    funcion = funcion or Espia()
    herramienta = Herramienta("accion", "Hace algo.", "prueba", funcion, {"objetivo": "Sobre qué."}, riesgo=riesgo)
    auditar = (lambda *args: auditados.append(args)) if auditados is not None else None
    return Registro([herramienta], auditar=auditar), funcion


@pytest.mark.parametrize("riesgo", [Riesgo.LECTURA, Riesgo.BAJO])
def test_lectura_y_bajo_se_ejecutan_sin_confirmar(riesgo):
    registro, funcion = _registro(riesgo)

    resultado = registro.ejecutar("accion", {"objetivo": "x"}, ContextoEjecucion(confirmador=_no_debe_confirmar))

    assert resultado == "hecho"
    assert funcion.llamadas == [{"objetivo": "x"}]


@pytest.mark.parametrize("riesgo", [Riesgo.ALTO, Riesgo.CRITICO])
def test_alto_y_critico_piden_confirmacion(riesgo):
    registro, funcion = _registro(riesgo)
    preguntas = []

    registro.ejecutar("accion", {"objetivo": "x"}, ContextoEjecucion(confirmador=lambda p: preguntas.append(p) or True))

    assert len(preguntas) == 1
    assert funcion.llamadas == [{"objetivo": "x"}]


def test_si_no_se_confirma_no_se_ejecuta():
    registro, funcion = _registro(Riesgo.ALTO)

    resultado = registro.ejecutar("accion", {"objetivo": "x"}, ContextoEjecucion(confirmador=lambda p: False))

    assert resultado == MENSAJE_CANCELADO
    assert funcion.llamadas == []


def test_modo_seguro_bloquea_acciones_pero_no_lecturas():
    registro_bajo, funcion_bajo = _registro(Riesgo.BAJO)
    registro_lectura, funcion_lectura = _registro(Riesgo.LECTURA)
    for registro in (registro_bajo, registro_lectura):
        registro.modo_seguro = True
    contexto = ContextoEjecucion(confirmador=_no_debe_confirmar)

    assert registro_bajo.ejecutar("accion", {"objetivo": "x"}, contexto) == MENSAJE_MODO_SEGURO
    assert registro_lectura.ejecutar("accion", {"objetivo": "x"}, contexto) == "hecho"
    assert funcion_bajo.llamadas == []
    assert funcion_lectura.llamadas == [{"objetivo": "x"}]


def test_el_riesgo_puede_depender_de_los_argumentos():
    funcion = Espia()
    herramienta = Herramienta(
        "click", "Click.", "prueba", funcion, {"texto": "Botón."},
        riesgo=lambda args: Riesgo.ALTO if args["texto"] == "Eliminar" else Riesgo.BAJO,
    )
    registro = Registro([herramienta])
    preguntas = []
    contexto = ContextoEjecucion(confirmador=lambda p: preguntas.append(p) or True)

    registro.ejecutar("click", {"texto": "Guardar"}, contexto)
    registro.ejecutar("click", {"texto": "Eliminar"}, contexto)

    assert len(preguntas) == 1
    assert len(funcion.llamadas) == 2


def test_un_error_de_la_herramienta_vuelve_como_texto():
    def falla(objetivo):
        raise OSError("disco lleno")

    registro, _ = _registro(Riesgo.BAJO, funcion=falla)

    resultado = registro.ejecutar("accion", {"objetivo": "x"}, ContextoEjecucion(confirmador=_no_debe_confirmar))

    assert "disco lleno" in resultado


def test_argumentos_equivocados_vuelven_como_texto():
    registro, _ = _registro(Riesgo.BAJO, funcion=lambda objetivo: "hecho")

    resultado = registro.ejecutar("accion", {"otro": "x"}, ContextoEjecucion(confirmador=_no_debe_confirmar))

    assert resultado.startswith("Error al usar accion")


def test_herramienta_desconocida():
    registro, _ = _registro(Riesgo.BAJO)

    assert "no existe" in registro.ejecutar("borrar_todo", {}, ContextoEjecucion(confirmador=_no_debe_confirmar))


def test_se_auditan_las_acciones_y_los_intentos_bloqueados_pero_no_las_lecturas():
    auditados = []
    registro_bajo, _ = _registro(Riesgo.BAJO, auditados=auditados)
    registro_alto, _ = _registro(Riesgo.ALTO, auditados=auditados)
    registro_lectura, _ = _registro(Riesgo.LECTURA, auditados=auditados)
    contexto = ContextoEjecucion(confirmador=lambda p: False, canal="voz")

    registro_bajo.ejecutar("accion", {"objetivo": "a"}, contexto)
    registro_alto.ejecutar("accion", {"objetivo": "b"}, contexto)  # cancelada: también queda registro
    registro_lectura.ejecutar("accion", {"objetivo": "c"}, contexto)

    assert auditados == [
        ("voz", "accion", {"objetivo": "a"}, "hecho"),
        ("voz", "accion", {"objetivo": "b"}, MENSAJE_CANCELADO),
    ]


def test_no_admite_nombres_duplicados():
    herramienta = Herramienta("accion", "Hace algo.", "prueba", Espia())

    with pytest.raises(ValueError):
        Registro([herramienta, herramienta])


def test_esquemas_para_ollama_y_gemini_filtran_por_grupo():
    herramientas = [
        Herramienta("leer", "Lee.", "boveda", Espia(), {"ruta": "Ruta."}),
        Herramienta("abrir", "Abre.", "sistema", Espia(), {"nombre": "Nombre."}),
    ]
    registro = Registro(herramientas)

    ollama = registro.esquemas_ollama({"boveda"})
    gemini = registro.declaraciones_gemini({"sistema"})

    assert [e["function"]["name"] for e in ollama] == ["leer"]
    assert ollama[0]["function"]["parameters"]["required"] == ["ruta"]
    assert gemini == [
        {
            "name": "abrir",
            "description": "Abre.",
            "parameters_json_schema": {
                "type": "object",
                "properties": {"nombre": {"type": "string", "description": "Nombre."}},
                "required": ["nombre"],
            },
        }
    ]


def test_opcionales_no_quedan_en_required_del_esquema():
    herramienta = Herramienta(
        "agregar",
        "Agrega.",
        "boveda",
        Espia(),
        {"tarea": "La tarea.", "cuando": "Cuándo, opcional."},
        opcionales=frozenset({"cuando"}),
    )

    esquema = herramienta.esquema_parametros()

    assert set(esquema["properties"]) == {"tarea", "cuando"}
    assert esquema["required"] == ["tarea"]


# --- catálogo real ---


@patch("src.herramientas.auditoria.escribir_nota")
@patch("src.herramientas.catalogo.hacer_click")
def test_catalogo_click_riesgoso_pide_confirmacion_y_neutro_no(mock_click, _mock_auditoria):
    mock_click.return_value = ResultadoAccion(exito=True, mensaje="ok")
    preguntas = []
    contexto = ContextoEjecucion(confirmador=lambda p: preguntas.append(p) or True)

    REGISTRO.ejecutar("hacer_click", {"texto": "Guardar"}, contexto)
    REGISTRO.ejecutar("hacer_click", {"texto": "Eliminar"}, contexto)

    assert preguntas == ["¿Confirmas que haga click en 'Eliminar'?"]
    assert mock_click.call_count == 2


def test_catalogo_agregar_pendiente_tiene_cuando_como_opcional():
    esquemas = {e["function"]["name"]: e["function"] for e in REGISTRO.esquemas_ollama({"boveda"})}

    parametros = esquemas["agregar_pendiente"]["parameters"]
    assert set(parametros["properties"]) == {"tarea", "cuando"}
    assert parametros["required"] == ["tarea"]


def test_catalogo_tiene_agregar_recurrente():
    assert "agregar_recurrente" in REGISTRO.nombres()
    esquemas = {e["function"]["name"]: e["function"] for e in REGISTRO.esquemas_ollama({"boveda"})}
    assert set(esquemas["agregar_recurrente"]["parameters"]["required"]) == {"tarea", "frecuencia"}


def test_catalogo_tiene_las_herramientas_nuevas_de_boveda():
    assert {"crear_nota", "conectar_notas", "eliminar_nota"} <= REGISTRO.nombres()


def test_catalogo_eliminar_nota_pide_confirmacion_y_no_borra_si_se_cancela(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "nota.md").write_text("contenido", encoding="utf-8")
    preguntas = []
    contexto = ContextoEjecucion(confirmador=lambda p: preguntas.append(p) or False)

    resultado = REGISTRO.ejecutar("eliminar_nota", {"ruta": "nota.md"}, contexto)

    assert preguntas == ["¿Confirmas que elimine la nota 'nota.md'? Se irá a la papelera."]
    assert resultado == MENSAJE_CANCELADO
    assert (tmp_path / "nota.md").exists()


def test_seleccionar_grupos_agrega_pantalla_solo_si_hace_falta():
    assert seleccionar_grupos("¿qué pendientes tengo?") == {"boveda", "sistema", "notas"}
    assert "pantalla" in seleccionar_grupos("abre el bloc de notas y escribe hola")
    assert "pantalla" in seleccionar_grupos("presiona el botón Aceptar")
    assert "pantalla" not in seleccionar_grupos("describe mi proyecto")


def test_el_modelo_local_solo_recibe_herramientas_de_notas_si_habla_de_notas():
    """Con 8 herramientas de gestión de notas de más, qwen3:8b se confunde; solo van cuando hacen falta."""
    assert "notas" not in seleccionar_grupos("¿qué pendientes tengo?", modelo_local=True)
    assert "notas" not in seleccionar_grupos("ya llamé al dentista", modelo_local=True)
    assert "notas" in seleccionar_grupos("crea una nota sobre node.js", modelo_local=True)
    assert "notas" in seleccionar_grupos("conecta mi nota de Jarvis con la de Ollama", modelo_local=True)
    assert "notas" in seleccionar_grupos("borra la nota vieja", modelo_local=True)


def test_el_modelo_local_solo_recibe_sistema_si_se_pide_abrir_algo():
    """Con herramientas de sistema de más, qwen3:8b dejaba de leer la bóveda."""
    assert seleccionar_grupos("¿qué pendientes tengo?", modelo_local=True) == {"boveda"}
    assert seleccionar_grupos("¿qué tengo que entregar en abril?", modelo_local=True) == {"boveda"}
    assert "sistema" in seleccionar_grupos("abre spotify y dime mis pendientes", modelo_local=True)
    assert "sistema" in seleccionar_grupos("ábreme la carpeta de descargas", modelo_local=True)
    assert "sistema" in seleccionar_grupos("pon el video de youtube.com/watch?v=abc", modelo_local=True)
