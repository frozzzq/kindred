"""Panel "Hoy": lo que el usuario tiene pendiente, de un vistazo, y lo último que hicieron los agentes.

Se pueden marcar pendientes como hechos desde aquí: pasa por el mismo registro con permisos que usan
los agentes (queda en Registro-Acciones.md, canal "ui").
"""

from collections.abc import Callable
from datetime import datetime, timedelta

import flet as ft

from src.herramientas.auditoria import ultimas_acciones
from src.obsidian.tareas import DIAS, cuando, leer_pendientes, ordenar, recurrentes_de_hoy
from src.ui import estilo

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
ICONO_HERRAMIENTA = {
    "crear_nota": ft.Icons.NOTE_ADD_OUTLINED,
    "agregar_a_nota": ft.Icons.EDIT_NOTE,
    "editar_nota": ft.Icons.EDIT_NOTE,
    "conectar_notas": ft.Icons.ADD_LINK,
    "eliminar_nota": ft.Icons.DELETE_OUTLINE,
    "agregar_pendiente": ft.Icons.SCHEDULE,
    "completar_pendiente": ft.Icons.CHECK_CIRCLE_OUTLINE,
    "reprogramar_pendiente": ft.Icons.EVENT_REPEAT,
}


class PanelHoy:
    def __init__(self, completar: Callable[[str], str]) -> None:
        self._completar = completar
        self._fecha = estilo.texto(tamano=15, peso=ft.FontWeight.W_600)
        self._lista = ft.Column(spacing=4)
        self._actividad = ft.Column(spacing=8)
        self.control = ft.Column(
            [
                estilo.tarjeta(ft.Column([self._fecha, ft.Container(height=4), self._lista], spacing=6)),
                estilo.tarjeta(ft.Column([estilo.titulo_seccion("Actividad reciente"), self._actividad], spacing=10)),
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _fila_pendiente(self, tarea: str, detalle: str, color: str, completable: bool = True) -> ft.Control:
        def marcar(_e):
            self._completar(tarea)
            self.refrescar()

        return ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.RADIO_BUTTON_UNCHECKED if completable else ft.Icons.EVENT_REPEAT,
                    icon_color=color,
                    icon_size=18,
                    tooltip="Marcar como hecho" if completable else "Tarea recurrente",
                    on_click=marcar if completable else None,
                ),
                ft.Column(
                    [estilo.texto(tarea, 13), estilo.texto(detalle, 11, estilo.TEXTO_SUAVE)] if detalle else [estilo.texto(tarea, 13)],
                    spacing=0,
                    expand=True,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def refrescar(self, ahora: datetime | None = None) -> None:
        ahora = ahora or datetime.now()
        self._fecha.value = f"Hoy · {DIAS[ahora.weekday()]} {ahora.day} de {MESES[ahora.month - 1]}"
        pendientes = ordenar(leer_pendientes())
        vencidos = [p for p in pendientes if p.vencido(ahora)]
        de_hoy = [p for p in pendientes if p.es_de_hoy(ahora) and not p.vencido(ahora)]
        limite = (ahora + timedelta(days=7)).date()
        proximos = [
            p for p in pendientes
            if not p.vencido(ahora) and not p.es_de_hoy(ahora) and (p.hora or p.fecha) and (p.hora.date() if p.hora else p.fecha) <= limite
        ]
        sin_fecha = [p for p in pendientes if p.fecha is None and p.hora is None]
        recurrentes = recurrentes_de_hoy(ahora)

        filas: list[ft.Control] = []

        def grupo(nombre: str, elementos: list, color: str) -> None:
            if elementos:
                filas.append(ft.Container(estilo.titulo_seccion(nombre), padding=ft.Padding(0, 8, 0, 0)))
                filas.extend(self._fila_pendiente(p.tarea, cuando(p, ahora), color) for p in elementos)

        grupo("Vencidos", vencidos, estilo.MAL)
        grupo("Para hoy", de_hoy, estilo.AVISO)
        if recurrentes:
            filas.append(ft.Container(estilo.titulo_seccion("Recurrentes de hoy"), padding=ft.Padding(0, 8, 0, 0)))
            filas.extend(self._fila_pendiente(tarea, f"a las {hora}", estilo.TEXTO_SUAVE, completable=False) for tarea, hora in recurrentes)
        grupo("Esta semana", proximos, estilo.BIEN)
        grupo("Sin fecha", sin_fecha[:5], estilo.TEXTO_SUAVE)
        if not filas:
            filas.append(estilo.texto("Nada pendiente. Día libre.", 13, estilo.TEXTO_SUAVE))
        self._lista.controls = filas

        acciones = ultimas_acciones(6)
        self._actividad.controls = [
            ft.Row(
                [
                    ft.Icon(ICONO_HERRAMIENTA.get(a.herramienta, ft.Icons.BOLT), size=16, color=estilo.TEXTO_SUAVE),
                    ft.Column(
                        [
                            estilo.texto(a.resultado[:70], 12, max_lines=2),
                            estilo.texto(f"{a.momento[11:]} · {a.canal} · {a.herramienta}", 10, estilo.TEXTO_TENUE),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
            for a in acciones
        ] or [estilo.texto("Todavía no hay acciones registradas.", 12, estilo.TEXTO_SUAVE)]
