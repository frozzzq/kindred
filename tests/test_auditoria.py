from src.herramientas.auditoria import RUTA_REGISTRO_ACCIONES, registrar_accion


def test_registra_la_accion_en_la_boveda(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    registrar_accion("voz", "abrir_aplicacion", {"nombre": "spotify"}, "Abriendo Spotify...\n")

    linea = (tmp_path / RUTA_REGISTRO_ACCIONES).read_text(encoding="utf-8").strip()
    assert "· voz · `abrir_aplicacion` {\"nombre\": \"spotify\"} → Abriendo Spotify..." in linea


def test_sin_boveda_configurada_no_bloquea_la_accion(monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT_PATH", raising=False)

    registrar_accion("texto", "abrir_url", {"url": "youtube.com"}, "ok")  # no lanza
