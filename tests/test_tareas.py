from datetime import date, datetime

import pytest

from src.obsidian.tareas import Pendiente, cuando, leer_pendientes, proximos

AHORA = datetime(2026, 9, 29, 10, 0)  # martes


@pytest.mark.parametrize(
    "pendiente, esperado",
    [
        (Pendiente("a", date(2026, 9, 26), None), "vencido desde el sábado 26"),
        (Pendiente("a", date(2026, 9, 29), datetime(2026, 9, 29, 8, 0)), "vencido, era hoy a las 08:00"),
        (Pendiente("a", date(2026, 9, 29), datetime(2026, 9, 29, 18, 0)), "hoy a las 18:00"),
        (Pendiente("a", date(2026, 9, 30), None), "mañana"),
        (Pendiente("a", date(2026, 10, 2), datetime(2026, 10, 2, 9, 0)), "el viernes a las 09:00"),
        (Pendiente("a", date(2026, 10, 20), None), "el martes 20/10"),
        (Pendiente("a", None, None), ""),
    ],
)
def test_cuando_lo_dice_como_una_persona(pendiente, esperado):
    assert cuando(pendiente, AHORA) == esperado


def test_leer_pendientes_y_proximos(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    (tmp_path / "02-Tareas").mkdir()
    (tmp_path / "02-Tareas" / "Pendientes.md").write_text(
        "- [ ] Llamar a mamá 📅 2026-09-29 ⏰ 2026-09-29 18:00 (agregado x)\n"
        "- [ ] Comprar leche (agregado 2026-09-28 10:00)\n"
        "texto suelto que no es tarea\n",
        encoding="utf-8",
    )

    pendientes = leer_pendientes()

    assert [p.tarea for p in pendientes] == ["Llamar a mamá", "Comprar leche"]
    assert [p.tarea for p in proximos(AHORA)] == ["Llamar a mamá"]
