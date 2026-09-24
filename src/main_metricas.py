"""Punto de entrada: imprime un reporte de métricas de uso (Fase 5)."""

from dotenv import load_dotenv

from src.consola import forzar_utf8
from src.obsidian.metricas import calcular_metricas
from src.router.intent_router import MOTOR_GEMINI_FALLO


def main() -> None:
    forzar_utf8()
    load_dotenv(override=True)
    metricas = calcular_metricas()

    if metricas.total_resueltas == 0:
        print("Todavía no hay interacciones registradas en la bóveda.")
        return

    print(f"Interacciones resueltas: {metricas.total_resueltas}\n")
    for motor, cantidad in sorted(metricas.conteo_por_motor.items(), key=lambda item: -item[1]):
        if motor == MOTOR_GEMINI_FALLO:
            continue
        print(f"  {motor:12s} {cantidad:4d}  ({metricas.porcentaje(motor)}%)")

    tasa = metricas.tasa_exito_gemini()
    if tasa is not None:
        fallos = metricas.conteo_por_motor.get(MOTOR_GEMINI_FALLO, 0)
        print(f"\nTasa de éxito de Gemini: {tasa}% ({fallos} fallo(s) registrado(s))")


if __name__ == "__main__":
    main()
