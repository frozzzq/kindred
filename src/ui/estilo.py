"""Sistema visual de la UI: colores, tipografía y piezas reutilizables (tarjetas, indicadores, barras).

Todo oscuro y sobrio; el color lo pone el agente activo (carmesí de Crimson, violeta de Clover).
"""

import flet as ft

FONDO = "#0B0E14"
SUPERFICIE = "#121722"
SUPERFICIE_ALTA = "#182031"
BORDE = "#232B3B"
TEXTO = "#E6E9EF"
TEXTO_SUAVE = "#9AA3B5"
TEXTO_TENUE = "#5E6780"
BIEN = "#3DDC97"
AVISO = "#F5B84B"
MAL = "#FF5C7A"
RADIO = 14
ESPACIO = 16


def texto(valor: str = "", tamano: int = 14, color: str = TEXTO, peso=None, **extra) -> ft.Text:
    return ft.Text(valor, size=tamano, color=color, weight=peso, **extra)


def titulo_seccion(valor: str) -> ft.Text:
    return ft.Text(valor.upper(), size=11, color=TEXTO_TENUE, weight=ft.FontWeight.W_600)


def tarjeta(contenido: ft.Control, **extra) -> ft.Container:
    return ft.Container(
        content=contenido,
        bgcolor=SUPERFICIE,
        border=ft.Border.all(1, BORDE),
        border_radius=RADIO,
        padding=extra.pop("padding", ESPACIO),
        **extra,
    )


def punto(color: str, tamano: int = 8) -> ft.Container:
    return ft.Container(width=tamano, height=tamano, border_radius=tamano / 2, bgcolor=color)


def color_estado(ok: bool | None) -> str:
    return {True: BIEN, False: MAL, None: AVISO}[ok]


def indicador(etiqueta: str, ok: bool | None, detalle: str = "") -> ft.Container:
    """Chip de estado: un punto de color y una palabra, con el detalle al pasar el mouse."""
    return ft.Container(
        content=ft.Row([punto(color_estado(ok)), texto(etiqueta, 12, TEXTO_SUAVE)], spacing=6, tight=True),
        padding=ft.Padding(10, 5, 10, 5),
        border_radius=20,
        bgcolor=SUPERFICIE,
        border=ft.Border.all(1, BORDE),
        tooltip=detalle or None,
    )


ALTO_KPI = 124


def kpi(etiqueta: str, valor: str, detalle: str = "", color: str = TEXTO) -> ft.Container:
    return tarjeta(
        ft.Column(
            [titulo_seccion(etiqueta), texto(valor, 28, color, ft.FontWeight.W_700), texto(detalle, 12, TEXTO_SUAVE, max_lines=2)],
            spacing=4,
        ),
        expand=True,
        height=ALTO_KPI,
    )


def barra(fraccion: float, color: str, alto: int = 8) -> ft.ProgressBar:
    return ft.ProgressBar(value=max(0.0, min(1.0, fraccion)), color=color, bgcolor=SUPERFICIE_ALTA, bar_height=alto, border_radius=alto / 2)


def boton(etiqueta: str, al_tocar, icono=None, principal: bool = False, color: str | None = None) -> ft.Control:
    if principal:
        return ft.FilledButton(content=etiqueta, icon=icono, on_click=al_tocar, bgcolor=color)
    return ft.OutlinedButton(content=etiqueta, icon=icono, on_click=al_tocar)
