"""Vista "Bóveda": cómo está la memoria, buscar en ella por tema y revisar conexiones sugeridas.

Las sugerencias se calculan con el mismo criterio que usan los agentes (mención por título o
fragmentos muy parecidos); conectar desde aquí pasa por el registro con permisos (canal "ui").
"""

import os
import threading
from collections.abc import Callable
from pathlib import PurePosixPath
from urllib.parse import quote

import flet as ft

from src.obsidian import indice, notas
from src.obsidian.config import ruta_boveda
from src.obsidian.estructura import CARPETA_CONOCIMIENTO, es_conocimiento
from src.obsidian.grafo import construir_grafo
from src.ui import estilo

MAX_SUGERENCIAS = 8
MAX_NOTAS_REVISADAS = 25


def abrir_en_obsidian(ruta: str | None = None) -> None:
    """Abre la bóveda (o una nota) en Obsidian con su enlace obsidian://."""
    boveda = ruta_boveda()
    url = f"obsidian://open?path={quote(str(boveda / ruta if ruta else boveda))}"
    try:
        os.startfile(url)  # type: ignore[attr-defined]  # solo Windows
    except OSError:
        os.startfile(str(boveda))  # type: ignore[attr-defined]


class VistaBoveda:
    def __init__(self, conectar: Callable[[str, str, str], str], color: Callable[[], str]) -> None:
        self._conectar = conectar
        self._color = color
        self._kpis = ft.Row(spacing=12)
        self._busqueda = ft.TextField(
            hint_text="Busca en tu bóveda por tema, ej. \"cómo funciona el event loop\"",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=12,
            on_submit=self._buscar,
            expand=True,
        )
        self._resultados = ft.Column(spacing=8)
        self._sugerencias = ft.Column(spacing=8)
        self._estado_indice = estilo.texto("", 12, estilo.TEXTO_SUAVE)
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        estilo.texto("Tu bóveda", 22, peso=ft.FontWeight.W_700),
                        ft.Row(
                            [
                                estilo.boton("Reindexar", self._reindexar, ft.Icons.REFRESH),
                                estilo.boton("Abrir en Obsidian", lambda _e: abrir_en_obsidian(), ft.Icons.OPEN_IN_NEW),
                            ],
                            spacing=8,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self._kpis,
                self._estado_indice,
                estilo.tarjeta(ft.Column([estilo.titulo_seccion("Buscar por tema"), self._busqueda, self._resultados], spacing=10)),
                estilo.tarjeta(
                    ft.Column(
                        [
                            estilo.titulo_seccion("Conexiones sugeridas"),
                            estilo.texto(
                                "Notas que se mencionan o tratan lo mismo y todavía no están enlazadas.", 12, estilo.TEXTO_SUAVE
                            ),
                            self._sugerencias,
                        ],
                        spacing=10,
                    )
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # ---------- datos ----------

    def refrescar(self) -> None:
        """Recalcula todo (en el hilo que lo llame: hace lecturas y cálculos, no se llama desde la UI)."""
        try:
            grafo = construir_grafo()
            estado = indice.estado()
        except (RuntimeError, OSError) as error:
            self._kpis.controls = [estilo.kpi("Bóveda", "—", str(error))]
            return
        areas = {PurePosixPath(n.id).parts[1] for n in grafo.nodos if n.id.startswith(CARPETA_CONOCIMIENTO + "/") and len(PurePosixPath(n.id).parts) > 2}
        huerfanas = [r for r in grafo.huerfanas() if es_conocimiento(r)]
        self._kpis.controls = [
            estilo.kpi("Notas", str(grafo.total_notas)),
            estilo.kpi("Conexiones", str(grafo.total_enlaces)),
            estilo.kpi("Sin conectar", str(len(huerfanas)), "notas de conocimiento sin enlaces", estilo.AVISO if huerfanas else estilo.TEXTO),
            estilo.kpi("Áreas", str(len(areas)), ", ".join(sorted(areas))[:40]),
        ]
        modo = "búsqueda por significado" if estado.semantico else "solo por palabras (falta el modelo de embeddings)"
        self._estado_indice.value = f"Índice: {estado.notas} notas, {estado.fragmentos} fragmentos · {modo}"
        self._cargar_sugerencias(grafo, huerfanas)

    def _cargar_sugerencias(self, grafo, huerfanas: list[str]) -> None:
        vistas: set[frozenset] = set()
        filas = []
        otras = [n.id for n in grafo.nodos if not n.es_carpeta and es_conocimiento(n.id) and n.id not in huerfanas]
        # Revisar cada nota lee toda la bóveda (menciones): se limita, empezando por las que no tienen enlaces.
        for ruta in (huerfanas + otras)[:MAX_NOTAS_REVISADAS]:
            for otra, motivo in notas.candidatas(ruta, umbral=notas.UMBRAL_CONEXION_AUTO, k=2):
                par = frozenset((ruta, otra))
                if par in vistas:
                    continue
                vistas.add(par)
                filas.append(self._fila_sugerencia(ruta, otra, motivo))
                if len(filas) >= MAX_SUGERENCIAS:
                    break
            if len(filas) >= MAX_SUGERENCIAS:
                break
        self._sugerencias.controls = filas or [estilo.texto("Nada que sugerir: todo lo relacionado ya está conectado.", 12, estilo.TEXTO_SUAVE)]

    def _fila_sugerencia(self, origen: str, destino: str, motivo: str) -> ft.Control:
        fila = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)

        def conectar(_e):
            resultado = self._conectar(origen, destino, motivo)
            fila.controls = [ft.Icon(ft.Icons.CHECK_CIRCLE, color=estilo.BIEN, size=18), estilo.texto(resultado, 12, estilo.TEXTO_SUAVE, expand=True)]
            fila.update()

        fila.controls = [
            ft.Icon(ft.Icons.LINK, size=18, color=estilo.TEXTO_SUAVE),
            ft.Column(
                [
                    estilo.texto(f"{PurePosixPath(origen).stem}  ↔  {PurePosixPath(destino).stem}", 13, peso=ft.FontWeight.W_600),
                    estilo.texto(motivo, 11, estilo.TEXTO_SUAVE),
                ],
                spacing=0,
                expand=True,
            ),
            ft.TextButton(content="Conectar", icon=ft.Icons.ADD_LINK, on_click=conectar),
        ]
        return fila

    # ---------- eventos ----------

    def _buscar(self, _e) -> None:
        consulta = (self._busqueda.value or "").strip()
        if not consulta:
            return
        self._resultados.controls = [ft.ProgressRing(width=18, height=18, stroke_width=2)]
        self._resultados.update()

        def trabajo():
            indice.actualizar_sin_fallar()
            resultados = indice.buscar(consulta, k=5)
            self._resultados.controls = [self._fila_resultado(r) for r in resultados] or [
                estilo.texto("No encontré nada sobre eso en tu bóveda.", 12, estilo.TEXTO_SUAVE)
            ]
            self._resultados.update()

        threading.Thread(target=trabajo, daemon=True).start()

    def _fila_resultado(self, resultado: indice.Resultado) -> ft.Control:
        porcentaje = f"{round(resultado.similitud * 100)}%" if resultado.similitud is not None else "palabras"
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            estilo.texto(PurePosixPath(resultado.ruta).stem, 14, peso=ft.FontWeight.W_600),
                            estilo.texto(f"{resultado.ruta} · {porcentaje}", 11, estilo.TEXTO_TENUE),
                        ],
                        spacing=10,
                    ),
                    estilo.texto(resultado.texto[:260], 12, estilo.TEXTO_SUAVE, max_lines=3),
                ],
                spacing=2,
            ),
            padding=10,
            border_radius=10,
            bgcolor=estilo.SUPERFICIE_ALTA,
            on_click=lambda _e, ruta=resultado.ruta: abrir_en_obsidian(ruta),
            tooltip="Abrir en Obsidian",
        )

    def _reindexar(self, _e) -> None:
        self._estado_indice.value = "Reindexando..."
        self._estado_indice.update()

        def trabajo():
            indice.actualizar_sin_fallar()
            self.refrescar()
            self.control.update()

        threading.Thread(target=trabajo, daemon=True).start()
