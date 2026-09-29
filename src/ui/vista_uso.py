"""Vista "Uso": cuánto se usa cada agente, qué tan rápido responde y cuánta cuota de Gemini queda.

Todo sale de la tabla de turnos de estado.db (src/agente/metricas.py), que se llena en cada mensaje.
"""

import os

import flet as ft

from src.agente import metricas
from src.herramientas.auditoria import ultimas_acciones
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA
from src.ui import estilo
from src.ui.paletas import PALETAS

LIMITE_POR_MINUTO_GEMINI = 15  # plan gratuito de gemini flash-lite (medido: error 429 al pasarlo)
ALTO_GRAFICA = 120
NOMBRES = {MOTOR_OLLAMA: "Crimson", MOTOR_GEMINI: "Clover", MOTOR_ACCION: "Acciones directas"}


def _segundos(ms: int | None) -> str:
    return f"{ms / 1000:.1f} s" if ms else "—"


class VistaUso:
    def __init__(self) -> None:
        self._kpis = ft.Row(spacing=12)
        self._grafica = ft.Row(spacing=10, alignment=ft.MainAxisAlignment.SPACE_AROUND, vertical_alignment=ft.CrossAxisAlignment.END)
        self._herramientas = ft.Column(spacing=8)
        self._acciones = ft.Column(spacing=6)
        leyenda = ft.Row(
            [
                ft.Row([estilo.punto(PALETAS[m].principal), estilo.texto(NOMBRES[m], 12, estilo.TEXTO_SUAVE)], spacing=6, tight=True)
                for m in (MOTOR_OLLAMA, MOTOR_GEMINI, MOTOR_ACCION)
            ],
            spacing=16,
        )
        self.control = ft.Column(
            [
                estilo.texto("Uso de los agentes", 22, peso=ft.FontWeight.W_700),
                self._kpis,
                estilo.tarjeta(ft.Column([estilo.titulo_seccion("Últimos 7 días"), leyenda, self._grafica], spacing=12)),
                ft.Row(
                    [
                        estilo.tarjeta(ft.Column([estilo.titulo_seccion("Herramientas más usadas"), self._herramientas], spacing=10), expand=True),
                        estilo.tarjeta(ft.Column([estilo.titulo_seccion("Últimas acciones"), self._acciones], spacing=10), expand=True),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def refrescar(self) -> None:
        uso = metricas.resumen()
        cuota = int(os.getenv("GEMINI_DAILY_QUOTA", "1000") or 1000)
        hoy_crimson = uso.hoy_por_agente.get(MOTOR_OLLAMA, 0)
        hoy_clover = uso.hoy_por_agente.get(MOTOR_GEMINI, 0)
        usado = uso.llamadas_gemini_hoy
        self._kpis.controls = [
            estilo.kpi("Conversaciones hoy", str(sum(uso.hoy_por_agente.values())), f"Crimson {hoy_crimson} · Clover {hoy_clover}"),
            estilo.kpi(
                "Respuesta promedio",
                _segundos(uso.promedio_ms.get(MOTOR_OLLAMA)),
                f"de Crimson · Clover: {_segundos(uso.promedio_ms.get(MOTOR_GEMINI))}",
                PALETAS[MOTOR_OLLAMA].claro,
            ),
            estilo.tarjeta(
                ft.Column(
                    [
                        estilo.titulo_seccion("Cuota de Gemini hoy"),
                        estilo.texto(f"{usado} / {cuota}", 28, PALETAS[MOTOR_GEMINI].claro, ft.FontWeight.W_700),
                        estilo.barra(usado / cuota if cuota else 0, PALETAS[MOTOR_GEMINI].principal),
                        estilo.texto(f"Además: máximo {LIMITE_POR_MINUTO_GEMINI} solicitudes por minuto", 11, estilo.TEXTO_SUAVE),
                    ],
                    spacing=6,
                ),
                expand=True,
                height=estilo.ALTO_KPI,
            ),
            estilo.kpi("Fallos (7 días)", str(uso.fallos_semana), "respuestas con error", estilo.MAL if uso.fallos_semana else estilo.TEXTO),
        ]

        maximo = max([sum(conteo.values()) for _dia, conteo in uso.por_dia] + [1])
        columnas = []
        for dia, conteo in uso.por_dia:
            bloques = [
                ft.Container(height=max(2, ALTO_GRAFICA * conteo.get(m, 0) / maximo), width=26, bgcolor=PALETAS[m].principal)
                for m in (MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA)
                if conteo.get(m, 0)
            ]
            columnas.append(
                ft.Column(
                    [
                        estilo.texto(str(sum(conteo.values())) if conteo else "", 11, estilo.TEXTO_SUAVE),
                        ft.Container(
                            content=ft.Column(bloques, spacing=1),
                            border_radius=6,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            bgcolor=estilo.SUPERFICIE_ALTA if not bloques else None,
                            height=None if bloques else 2,
                            width=26,
                        ),
                        estilo.texto(dia[8:10] + "/" + dia[5:7], 11, estilo.TEXTO_TENUE),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        self._grafica.controls = columnas

        mas_usada = max([n for _h, n in uso.herramientas_top] + [1])
        self._herramientas.controls = [
            ft.Column([ft.Row([estilo.texto(h, 12), estilo.texto(str(n), 12, estilo.TEXTO_SUAVE)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), estilo.barra(n / mas_usada, PALETAS[MOTOR_OLLAMA].principal, 6)], spacing=4)
            for h, n in uso.herramientas_top
        ] or [estilo.texto("Aún no hay datos.", 12, estilo.TEXTO_SUAVE)]

        self._acciones.controls = [
            estilo.texto(f"{a.momento[5:]} · {a.herramienta} → {a.resultado[:60]}", 12, estilo.TEXTO_SUAVE, max_lines=1)
            for a in ultimas_acciones(8)
        ] or [estilo.texto("Aún no hay acciones.", 12, estilo.TEXTO_SUAVE)]
