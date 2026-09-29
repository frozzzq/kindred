from datetime import datetime

import pytest

from src.obsidian.vault_writer import (
    agregar_pendiente,
    agregar_recurrente,
    completar_pendiente,
    escribir_nota,
    guardar_contacto,
    recordar_sobre_usuario,
    registrar_interaccion,
    reprogramar_pendiente,
    ruta_log,
)


def test_escribir_nota_crea_carpetas_y_archivo(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    escribir_nota("03-Proyectos/Jarvis.md", "primer contenido", sobrescribir=True)

    ruta = tmp_path / "03-Proyectos" / "Jarvis.md"
    assert ruta.read_text(encoding="utf-8") == "primer contenido"


def test_escribir_nota_agrega_sin_sobrescribir(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    ruta = tmp_path / "nota.md"
    ruta.write_text("linea 1", encoding="utf-8")

    escribir_nota("nota.md", "linea 2")

    assert ruta.read_text(encoding="utf-8") == "linea 1\nlinea 2"


def test_agregar_pendiente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    agregar_pendiente("comprar leche")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "comprar leche" in contenido
    assert contenido.startswith("- [ ]")
    # La fecha es de cuándo se agregó; sin la etiqueta el modelo la leía como vencimiento.
    assert "(agregado " in contenido


def test_agregar_pendiente_no_duplica_el_mismo_pendiente(tmp_path, monkeypatch):
    """Caso real: "comprar croquetas para el perro" se pudo agregar dos veces seguidas."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    agregar_pendiente("Comprar croquetas para el perro")

    resultado = agregar_pendiente("Comprar croquetas para el perro")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert contenido.lower().count("croquetas") == 1
    assert "Ya tenías ese pendiente" in resultado


def test_agregar_pendiente_no_duplica_aunque_este_redactado_distinto(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    agregar_pendiente("Comprar croquetas para el perro")

    agregar_pendiente("comprar las croquetas del perro")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert contenido.lower().count("croquetas") == 1


def test_agregar_pendiente_distinto_si_agrega(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    agregar_pendiente("Comprar croquetas para el perro")

    agregar_pendiente("Llamar al dentista")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "croquetas" in contenido.lower()
    assert "dentista" in contenido.lower()


def test_agregar_pendiente_con_fecha_en_lenguaje_natural(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    resultado = agregar_pendiente("Entregar el reporte", cuando="mañana a las 6pm")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "📅" in contenido and "⏰" in contenido and "18:00" in contenido
    assert "para el" in resultado


def test_agregar_pendiente_cuando_sin_fecha_reconocible_no_agrega_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    agregar_pendiente("Comprar leche", cuando="algo sin fecha ni hora")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "📅" not in contenido


def test_agregar_pendiente_sin_cuando_no_agrega_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    agregar_pendiente("Comprar leche")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "📅" not in contenido


def test_agregar_recurrente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    resultado = agregar_recurrente("Tomar medicina", "diario a las 9pm")

    contenido = (tmp_path / "02-Tareas" / "Recurrentes.md").read_text(encoding="utf-8")
    assert "Tomar medicina" in contenido and "🔁" in contenido and "21:00" in contenido
    assert "agregada" in resultado.lower()


def test_agregar_recurrente_sin_hora_clara_no_agrega_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    resultado = agregar_recurrente("Tomar medicina", "de vez en cuando")

    assert not (tmp_path / "02-Tareas" / "Recurrentes.md").exists()
    assert "no entendí" in resultado.lower()


def test_agregar_recurrente_no_duplica(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    agregar_recurrente("Tomar medicina", "diario a las 9pm")

    resultado = agregar_recurrente("Tomar medicina", "diario a las 9pm")

    contenido = (tmp_path / "02-Tareas" / "Recurrentes.md").read_text(encoding="utf-8")
    assert contenido.lower().count("tomar medicina") == 1
    assert "ya tenías" in resultado.lower()


def _pendientes(tmp_path, *lineas):
    carpeta = tmp_path / "02-Tareas"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "Pendientes.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def test_completar_pendiente_lo_mueve_a_completadas(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)", "- [ ] Comprar leche (agregado x)")

    resultado = completar_pendiente("LECHE")

    pendientes = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    completadas = (tmp_path / "02-Tareas" / "Completadas.md").read_text(encoding="utf-8")
    assert "leche" not in pendientes.lower()
    assert "Comprar pan" in pendientes
    assert completadas.startswith("- [x] Comprar leche")
    assert "completado" in resultado.lower()


def test_completar_pendiente_ignora_acentos(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Llamar al médico (agregado x)")

    resultado = completar_pendiente("medico")

    assert "completado" in resultado.lower()


def test_completar_pendiente_ambiguo_no_toca_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)", "- [ ] Comprar leche (agregado x)")

    resultado = completar_pendiente("comprar")

    pendientes = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "Comprar pan" in pendientes and "Comprar leche" in pendientes
    assert "varios" in resultado
    assert not (tmp_path / "02-Tareas" / "Completadas.md").exists()


def test_completar_pendiente_inexistente(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)")

    assert "No encontré" in completar_pendiente("gasolina")


def test_recordar_sobre_usuario_escribe_en_el_perfil(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    recordar_sobre_usuario("Le gusta el café sin azúcar")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert perfil.startswith("- Le gusta el café sin azúcar")


def test_recordar_sobre_usuario_no_duplica_con_otras_palabras(tmp_path, monkeypatch):
    """Caso real: 'mi nombre es Josue' y 'Su nombre es Josue' quedaron como dos líneas."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    recordar_sobre_usuario("mi nombre es Josue")

    resultado = recordar_sobre_usuario("Su nombre es Josué")
    recordar_sobre_usuario("Se llama Josue")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert len(perfil.strip().splitlines()) == 1  # sigue siendo una sola línea
    assert resultado.startswith("Ya estaba")


def test_recordar_sobre_usuario_si_anota_datos_distintos(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    recordar_sobre_usuario("Se llama Josué")

    recordar_sobre_usuario("Le gusta programar en Python por las noches")

    perfil = (tmp_path / "01-Perfil" / "Yo.md").read_text(encoding="utf-8")
    assert "Python" in perfil and "Josué" in perfil


def test_guardar_contacto(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    guardar_contacto("Ana", "hermana del usuario, vive en Monterrey")

    contactos = (tmp_path / "01-Perfil" / "Contactos.md").read_text(encoding="utf-8")
    assert "**Ana**: hermana del usuario, vive en Monterrey" in contactos


def test_registrar_interaccion(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    registrar_interaccion("hola", "hola, como estas", "ollama")

    contenido = (tmp_path / "00-Sistema" / "Logs" / f"{datetime.now():%Y-%m}.md").read_text(encoding="utf-8")
    assert "hola, como estas" in contenido
    assert "(ollama)" in contenido


def test_el_log_rota_por_mes():
    assert ruta_log(datetime(2026, 9, 29)) == "00-Sistema/Logs/2026-09.md"
    assert ruta_log(datetime(2026, 10, 1)) == "00-Sistema/Logs/2026-10.md"


def test_escribir_nota_rechaza_rutas_fuera_de_la_boveda(tmp_path, monkeypatch):
    boveda = tmp_path / "boveda"
    boveda.mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(boveda))

    with pytest.raises(ValueError):
        escribir_nota("../fuera.md", "x")
    assert not (tmp_path / "fuera.md").exists()


def test_agregar_pendiente_queda_antes_de_la_seccion_relacionado(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Comprar pan (agregado x)", "", "## Relacionado", "- [[Yo]]")

    agregar_pendiente("Llamar al dentista")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert contenido.index("Llamar al dentista") < contenido.index("## Relacionado")


def test_reprogramar_pendiente_cambia_la_fecha_y_conserva_el_resto(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(
        tmp_path,
        "- [ ] Entregar el proyecto 📅 2026-10-02 (agregado 2026-09-28 15:47)",
        "- [ ] Comprar pan (agregado x)",
    )

    resultado = reprogramar_pendiente("proyecto", "el 5 de octubre a las 9am")

    contenido = (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "📅 2026-10-05 ⏰ 2026-10-05 09:00 (agregado 2026-09-28 15:47)" in contenido
    assert "2026-10-02" not in contenido
    assert "Comprar pan" in contenido
    assert "reprogramado" in resultado.lower()


def test_reprogramar_pendiente_sin_fecha_entendible_no_toca_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    _pendientes(tmp_path, "- [ ] Entregar el proyecto 📅 2026-10-02 (agregado x)")

    resultado = reprogramar_pendiente("proyecto", "cuando se pueda")

    assert "2026-10-02" in (tmp_path / "02-Tareas" / "Pendientes.md").read_text(encoding="utf-8")
    assert "no entendí" in resultado.lower()


def test_guardar_contacto_existente_suma_el_detalle_en_vez_de_duplicar(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    guardar_contacto("Ana", "hermana del usuario")

    resultado = guardar_contacto("ana", "vive en Monterrey")

    contactos = (tmp_path / "01-Perfil" / "Contactos.md").read_text(encoding="utf-8")
    assert contactos.count("**Ana**") == 1
    assert "vive en Monterrey" in contactos
    assert "actualizado" in resultado.lower()
