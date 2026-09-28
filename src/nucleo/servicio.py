"""El corazón del núcleo: cada 30s revisa recordatorios y briefings, y avisa lo que toque.

Corre como proceso de fondo, independiente de si la UI/voz/CLI están abiertas (Jarvis-Nucleo.bat).
Nunca debe morirse por un fallo puntual (Ollama caído, sin bóveda, sin internet): se registra el
error y se sigue en la siguiente vuelta.
"""

import os
import re
import time as _reloj
from collections.abc import Callable
from datetime import datetime, time

from dotenv import load_dotenv

from src.consola import forzar_utf8
from src.nucleo import avisos, briefing, estado, recordatorios
from src.obsidian.estructura import asegurar_estructura_boveda
from src.obsidian.vault_writer import escribir_nota

INTERVALO_SEGUNDOS = 30
RUTA_HEARTBEAT = "00-Sistema/HEARTBEAT.md"

_HORARIO = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")


def _en_horario_silencio(ahora: datetime) -> bool:
    """True si `ahora` cae dentro de HORARIO_SILENCIO (ej. "23:00-07:00"; puede cruzar medianoche).

    Sin la variable configurada (o con un formato que no se entiende), nunca hay silencio.
    """
    configurado = os.getenv("HORARIO_SILENCIO", "").strip()
    coincidencia = _HORARIO.match(configurado) if configurado else None
    if not coincidencia:
        return False
    inicio = time(int(coincidencia.group(1)), int(coincidencia.group(2)))
    fin = time(int(coincidencia.group(3)), int(coincidencia.group(4)))
    ahora_hora = ahora.time()
    if inicio <= fin:
        return inicio <= ahora_hora < fin
    return ahora_hora >= inicio or ahora_hora < fin  # cruza medianoche (ej. 23:00-07:00)


def _avisar_recordatorios(ahora: datetime) -> int:
    pendientes = recordatorios.pendientes_por_avisar(ahora) + recordatorios.recurrentes_por_avisar(ahora)
    for recordatorio in pendientes:
        avisos.avisar("Recordatorio", recordatorio.tarea)
        estado.marcar_avisado(recordatorio.clave, ahora.isoformat())
    return len(pendientes)


def _revisar_briefing(tipo: str, titulo: str, generar: Callable[[datetime], str], ahora: datetime) -> bool:
    hora_configurada = os.getenv(f"HORA_{tipo.upper()}", "").strip()
    if not hora_configurada or ahora.strftime("%H:%M") < hora_configurada:
        return False
    if estado.briefing_de_hoy(tipo) == ahora.date().isoformat():
        return False
    avisos.avisar(titulo, generar(ahora))
    estado.marcar_briefing(tipo, ahora.date().isoformat())
    return True


def _actualizar_heartbeat(ahora: datetime, avisados: int) -> None:
    contenido = (
        "# Estado del núcleo\n\n"
        f"Última vuelta: {ahora.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Recordatorios avisados en esta vuelta: {avisados}\n"
    )
    try:
        escribir_nota(RUTA_HEARTBEAT, contenido, sobrescribir=True)
    except (RuntimeError, OSError) as error:
        print(f"[núcleo] no se pudo actualizar HEARTBEAT.md: {error}")


def ciclo(ahora: datetime | None = None) -> None:
    """Una vuelta del heartbeat: avisa recordatorios vencidos y, si toca, dispara un briefing."""
    ahora = ahora or datetime.now()
    avisados = 0
    if not _en_horario_silencio(ahora):
        avisados = _avisar_recordatorios(ahora)
        # HORA_BRIEFING/HORA_CIERRE usan el mismo nombre de variable que el tipo guardado en estado.db.
        _revisar_briefing("briefing", "Buenos días", briefing.generar_matutino, ahora)
        _revisar_briefing("cierre", "Cierre del día", briefing.generar_cierre, ahora)
    _actualizar_heartbeat(ahora, avisados)


def main() -> None:
    forzar_utf8()
    load_dotenv(override=True)
    try:
        asegurar_estructura_boveda()
    except RuntimeError as error:
        print(f"[núcleo] no se pudo preparar la bóveda de Obsidian: {error}")

    print("Crimson y Clover (núcleo, Fase 7). Ctrl+C para salir.")
    while True:
        try:
            ciclo()
        except Exception as error:  # noqa: BLE001 - el heartbeat nunca debe morirse por un fallo puntual
            print(f"[núcleo] error en el ciclo: {error}")
        try:
            _reloj.sleep(INTERVALO_SEGUNDOS)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
