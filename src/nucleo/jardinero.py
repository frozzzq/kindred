"""El jardinero de la bóveda: la mantiene al día sin que nadie se lo pida.

En cada vuelta del núcleo:
- actualiza el índice semántico (notas nuevas o editadas a mano en Obsidian ya se pueden buscar);
- a las notas de conocimiento que cambiaron las acomoda en el índice de su área y las conecta con
  las de su mismo tema (mismo criterio que al crearlas: mención por título o fragmento muy parecido).

Solo toca notas que llevan MINUTOS_QUIETA sin cambios, para no escribir en una nota que el usuario
está editando en ese momento en Obsidian.
"""

import json
import time
from pathlib import PurePosixPath

from src.nucleo import estado
from src.obsidian import indice, notas
from src.obsidian.config import ruta_boveda
from src.obsidian.estructura import es_conocimiento
from src.obsidian.vault_reader import listar_rutas_relativas

MINUTOS_QUIETA = 10
CLAVE_REVISADAS = "jardinero.revisadas"  # ruta → fecha de modificación ya revisada


def cuidar(ahora: float | None = None) -> list[str]:
    """Una vuelta del jardinero. Devuelve lo que hizo, en líneas cortas (para el registro del núcleo)."""
    ahora = ahora or time.time()
    hecho = []
    resumen = indice.actualizar_sin_fallar()
    if resumen and (resumen.procesadas or resumen.borradas):
        hecho.append(f"índice: {resumen.procesadas} nota(s) al día, {resumen.borradas} quitada(s)")

    revisadas: dict[str, float] = json.loads(estado.leer_valor(CLAVE_REVISADAS) or "{}")
    boveda = ruta_boveda()
    for ruta in listar_rutas_relativas():
        if not es_conocimiento(ruta):
            continue
        try:
            modificada = (boveda / ruta).stat().st_mtime
        except OSError:
            continue
        if revisadas.get(ruta) == modificada or ahora - modificada < MINUTOS_QUIETA * 60:
            continue
        notas.registrar_en_indice(ruta)
        conectadas = notas.auto_conectar(ruta)
        if conectadas:
            hecho.append(f"conecté {PurePosixPath(ruta).stem} con {', '.join(conectadas)}")
        try:
            revisadas[ruta] = (boveda / ruta).stat().st_mtime
        except OSError:
            revisadas.pop(ruta, None)
    existentes = set(listar_rutas_relativas())
    estado.guardar_valor(CLAVE_REVISADAS, json.dumps({r: m for r, m in revisadas.items() if r in existentes}))
    return hecho
