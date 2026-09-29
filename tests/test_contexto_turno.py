from datetime import datetime

import pytest

from src.agente.contexto_turno import construir_contexto, mensaje_con_contexto
from src.agente.conversacion import Conversacion
from src.obsidian import indice

AHORA = datetime(2026, 9, 29, 10, 0)  # martes


@pytest.fixture
def boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    def escribir(ruta, contenido):
        archivo = tmp_path / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")

    escribir(
        "02-Tareas/Pendientes.md",
        "- [ ] Entregar el proyecto 📅 2026-09-26 (agregado x)\n"
        "- [ ] Llamar a mamá 📅 2026-09-29 ⏰ 2026-09-29 18:00 (agregado x)\n"
        "- [ ] Comprar leche (agregado x)\n",
    )
    escribir("02-Tareas/Recurrentes.md", "- Tomar medicina 🔁 diario 21:00 (agregado x)\n")
    return escribir


def test_incluye_hora_y_pendientes_descritos_como_se_dicen(boveda):
    contexto = construir_contexto("hola", ahora=AHORA)

    assert "Ahora es martes 29/09/2026, 10:00." in contexto
    assert "- Entregar el proyecto (vencido desde el sábado 26)" in contexto
    assert "- Llamar a mamá (hoy a las 18:00)" in contexto
    assert "- Comprar leche" in contexto
    assert "- Tomar medicina (21:00)" in contexto


def test_incluye_notas_relevantes_marcadas_como_dato(boveda):
    boveda("04-Conocimiento/Node.js.md", "Node usa un event loop para no bloquear el servidor.")
    indice.actualizar()

    contexto = construir_contexto("¿cómo funciona el event loop de node?", ahora=AHORA)

    assert "[04-Conocimiento/Node.js.md]" in contexto
    assert "CONTENIDO GUARDADO POR EL USUARIO" in contexto


def test_el_aviso_proactivo_solo_va_en_el_primer_mensaje(boveda):
    conversacion = Conversacion()

    primero = construir_contexto("hola", conversacion, ahora=AHORA)
    conversacion.agregar_turno("hola", "¡Hola!")
    segundo = construir_contexto("¿y qué más?", conversacion, ahora=AHORA)

    assert "primer mensaje" in primero and "Entregar el proyecto" in primero.split("primer mensaje")[1]
    assert "primer mensaje" not in segundo


def test_el_mensaje_termina_con_lo_que_dijo_el_usuario(boveda):
    assert mensaje_con_contexto("hola", ahora=AHORA).endswith("Mensaje del usuario: hola")


def test_sin_boveda_no_crashea(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    assert "Ahora es" in construir_contexto("hola", ahora=AHORA)


def test_los_pendientes_van_agrupados_por_urgencia(boveda):
    """Con una lista plana, qwen3:8b dijo que un pendiente del viernes estaba "atrasado"."""
    boveda(
        "02-Tareas/Pendientes.md",
        "- [ ] Entregar el reporte 📅 2026-09-26 (agregado x)\n- [ ] Entregar el proyecto 📅 2026-10-02 (agregado x)\n",
    )

    contexto = construir_contexto("hola", ahora=AHORA)

    vencidos = contexto.index("Vencidos (ya se pasó su fecha):")
    proximos = contexto.index("Próximos (todavía a tiempo):")
    assert vencidos < contexto.index("Entregar el reporte") < proximos < contexto.index("Entregar el proyecto")


def test_una_nota_recien_escrita_ya_sirve_para_la_respuesta_de_ese_mismo_momento(boveda):
    """Caso pedido por el usuario: agrega información de Node.js a mano y de inmediato le pregunta."""
    indice.actualizar()  # el índice ya existía, sin la nota nueva
    boveda("04-Conocimiento/Programación/Node.js.md", "Node usa un event loop para no bloquear el servidor.")

    contexto = construir_contexto("¿cómo funciona el event loop de node?", ahora=AHORA)

    assert "Node usa un event loop" in contexto


def test_si_otra_indexacion_larga_esta_en_curso_no_se_queda_esperando(boveda):
    indice._bloqueo.acquire()  # como si la indexación inicial de una bóveda grande estuviera corriendo
    try:
        assert indice.actualizar(esperar=False) is None
        assert "Ahora es" in construir_contexto("hola", ahora=AHORA)  # responde igual, con el índice como está
    finally:
        indice._bloqueo.release()
