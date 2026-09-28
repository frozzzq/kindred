"""El agente representado como el grafo 3D de la bóveda de Obsidian.

Cada nota es un nodo y cada conexión una línea (ver src/obsidian/grafo.py). El
grafo gira lentamente sobre sí mismo, toma el color del agente y se ilumina
siguiendo el volumen de su voz: entre más fuerte habla, más brilla.
"""

import math

import flet as ft
import flet.canvas as cv
import numpy as np

from src.obsidian.grafo import Arista, Grafo, Nodo
from src.ui.paletas import PALETAS, Paleta

SEGUNDOS_POR_VUELTA = 40
INCLINACION = 0.38  # radianes: se ve un poco desde arriba para que se note la profundidad
DISTANCIA_CAMARA = 3.0  # en radios del grafo; menos = perspectiva más marcada
MARGEN = 45  # px entre el grafo y el borde del lienzo: lo que crece el brillo de un nodo con la voz al máximo
RADIO_NOTA = 4.0
RADIO_CARPETA = 7.0
SEGUNDOS_TRANSICION_COLOR = 0.5
LARGO_MAXIMO_ETIQUETA = 20
PROFUNDIDAD_MAXIMA_ETIQUETA = 0.45  # solo se rotulan las notas del frente, para no encimar texto

# Simulación de fuerzas (al estilo del grafo de Obsidian): los nodos se repelen
# y cada conexión los une como un resorte. Se "enfría" hasta quedarse quieta.
REPULSION = 0.03
ATRACCION_CENTRO = 0.015
RESORTE_ENLACE = (0.35, 1.2)  # (largo en reposo, rigidez)
RESORTE_CARPETA = (0.4, 1.0)
FRICCION = 0.4
VELOCIDAD_MAXIMA = 0.2
ENFRIAMIENTO = 0.02
CALOR_MINIMO = 0.003
CALOR_AL_CAMBIAR = 0.5


class Disposicion3D:
    """Posiciones 3D de los nodos, calculadas por fuerzas."""

    def __init__(self, semilla: int | None = None) -> None:
        self.ids: list[str] = []
        self.pos = np.zeros((0, 3))
        self.extremos = np.zeros((0, 2), dtype=int)  # índices (origen, destino) de cada arista
        self._vel = np.zeros((0, 3))
        self._largos = np.zeros(0)
        self._rigideces = np.zeros(0)
        self._calor = 0.0
        self._azar = np.random.default_rng(semilla)

    def actualizar(self, grafo: Grafo) -> None:
        """Cambia de grafo conservando la posición de los nodos que ya estaban; los nuevos nacen junto a un vecino."""
        anteriores = dict(zip(self.ids, self.pos))
        self.ids = [nodo.id for nodo in grafo.nodos]
        indice = {id_: i for i, id_ in enumerate(self.ids)}
        vecinos: dict[str, list[str]] = {id_: [] for id_ in self.ids}
        for arista in grafo.aristas:
            vecinos[arista.origen].append(arista.destino)
            vecinos[arista.destino].append(arista.origen)

        self.pos = np.array([self._posicion_inicial(id_, anteriores, vecinos[id_]) for id_ in self.ids]).reshape(-1, 3)
        self._vel = np.zeros_like(self.pos)
        self.extremos = np.array([(indice[a.origen], indice[a.destino]) for a in grafo.aristas], dtype=int).reshape(-1, 2)
        resortes = np.array([RESORTE_ENLACE if a.es_enlace else RESORTE_CARPETA for a in grafo.aristas]).reshape(-1, 2)
        self._largos, self._rigideces = resortes[:, 0], resortes[:, 1]

        if anteriores:
            self._calor = CALOR_AL_CAMBIAR
        else:  # la primera vez se muestra ya acomodado, sin la "explosión" inicial
            self._calor = 1.0
            while self.ids and self._calor >= CALOR_MINIMO:
                self.paso()

    def _posicion_inicial(self, id_: str, anteriores: dict, vecinos: list[str]) -> np.ndarray:
        if id_ in anteriores:
            return anteriores[id_]
        conocidos = [anteriores[v] for v in vecinos if v in anteriores]
        if conocidos:
            return conocidos[0] + self._azar.normal(0, 0.15, 3)
        return self._azar.normal(0, 0.5, 3)

    def paso(self) -> None:
        if self._calor < CALOR_MINIMO or not self.ids:
            return
        diferencias = self.pos[:, None, :] - self.pos[None, :, :]
        distancias2 = (diferencias**2).sum(axis=-1) + 1e-3
        fuerza = (REPULSION * diferencias / distancias2[..., None] ** 1.5).sum(axis=1)

        if len(self.extremos):
            i, j = self.extremos[:, 0], self.extremos[:, 1]
            tramo = self.pos[j] - self.pos[i]
            largo = np.linalg.norm(tramo, axis=1) + 1e-6
            tiron = (self._rigideces * (largo - self._largos) / largo)[:, None] * tramo
            np.add.at(fuerza, i, tiron)
            np.add.at(fuerza, j, -tiron)

        fuerza -= ATRACCION_CENTRO * self.pos
        self._vel = (self._vel + fuerza * self._calor) * (1 - FRICCION)
        rapidez = np.linalg.norm(self._vel, axis=1, keepdims=True)
        self._vel *= np.minimum(1.0, VELOCIDAD_MAXIMA / (rapidez + 1e-9))
        self.pos = self.pos + self._vel
        self._calor *= 1 - ENFRIAMIENTO


def proyectar(pos: np.ndarray, angulo: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Gira los puntos (normalizados a radio ~1) y los proyecta en perspectiva.

    Devuelve x, y en pantalla (en radios, centrados en 0), la escala de
    perspectiva de cada punto y su profundidad (0 = cerca, 1 = lejos).
    """
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    x, z = x * math.cos(angulo) + z * math.sin(angulo), -x * math.sin(angulo) + z * math.cos(angulo)
    y, z = y * math.cos(INCLINACION) - z * math.sin(INCLINACION), y * math.sin(INCLINACION) + z * math.cos(INCLINACION)
    perspectiva = DISTANCIA_CAMARA / (DISTANCIA_CAMARA + z)
    return x * perspectiva, y * perspectiva, perspectiva, np.clip((z + 1) / 2, 0.0, 1.0)


BLANCO = np.array([255.0, 255.0, 255.0])
MEZCLA_BRILLO_HOLOGRAMA = 0.2  # cuánto se acerca el color al blanco puro, para un brillo más intenso


def _rgb(color: str) -> np.ndarray:
    return np.array([int(color[i : i + 2], 16) for i in (1, 3, 5)], dtype=float)


def _recortar(nombre: str) -> str:
    return nombre if len(nombre) <= LARGO_MAXIMO_ETIQUETA else nombre[: LARGO_MAXIMO_ETIQUETA - 1] + "…"


def _color(rgb: np.ndarray, opacidad: float) -> str:
    r, g, b = np.clip(rgb, 0, 255).round().astype(int)
    return ft.Colors.with_opacity(float(np.clip(opacidad, 0.0, 1.0)), f"#{r:02x}{g:02x}{b:02x}")


class GrafoAgente:
    """El "cuerpo" del agente en la UI: toma su color, reacciona al escuchar y brilla con su voz."""

    def __init__(self, motor: str, semilla: int | None = None) -> None:
        self.motor = motor
        self.hablando_como: str | None = None
        self.escuchando = False
        self.disposicion = Disposicion3D(semilla)
        self.nivel = 0.0  # volumen suavizado de la voz, 0 a 1
        self._nodos: tuple[Nodo, ...] = ()
        self._aristas: tuple[Arista, ...] = ()
        self._angulo = 0.0
        self._tiempo = 0.0
        self._radio_vista = 1.0
        self._principal = _rgb(self.paleta.principal)
        self._claro = _rgb(self.paleta.claro)
        self._ancho, self._alto = 440.0, 440.0
        self._aura = cv.Circle(0, 0, 0)
        self._lineas: list[cv.Line] = []
        self._halos: list[cv.Circle] = []
        self._nucleos: list[cv.Circle] = []
        self._etiquetas: list[cv.Text] = []
        self.control = cv.Canvas(shapes=[self._aura], expand=True, on_resize=self._al_redimensionar, resize_interval=100)

    @property
    def paleta(self) -> Paleta:
        return PALETAS[self.hablando_como or self.motor]

    def cambiar_agente(self, motor: str) -> None:
        self.motor = motor

    def empezar_a_hablar(self, motor: str) -> None:
        self.hablando_como = motor

    def dejar_de_hablar(self) -> None:
        self.hablando_como = None

    def mostrar_grafo(self, grafo: Grafo) -> None:
        self._nodos, self._aristas = grafo.nodos, grafo.aristas
        self.disposicion.actualizar(grafo)
        self._lineas = [cv.Line(0, 0, 0, 0) for _ in self._aristas]
        self._halos = [cv.Circle(0, 0, 0) for _ in self._nodos]
        self._nucleos = [cv.Circle(0, 0, 0) for _ in self._nodos]
        self._etiquetas = [cv.Text(0, 0, _recortar(nodo.nombre), alignment=ft.Alignment(0, -1)) for nodo in self._nodos]
        self.control.shapes = [self._aura, *self._lineas, *self._halos, *self._nucleos, *self._etiquetas]
        self._dibujar()

    def _al_redimensionar(self, e: cv.CanvasResizeEvent) -> None:
        self._ancho, self._alto = e.width, e.height

    def avanzar(self, dt: float, nivel_voz: float) -> None:
        """Un cuadro de la animación: gira, sigue el volumen de la voz y se redibuja."""
        self._tiempo += dt
        self._angulo = (self._angulo + dt * 2 * math.pi / SEGUNDOS_POR_VUELTA) % (2 * math.pi)
        objetivo = min(max(nivel_voz, 0.0), 1.0)
        rapidez = 25.0 if objetivo > self.nivel else 6.0  # sube de golpe con cada sílaba, baja suave
        self.nivel += (objetivo - self.nivel) * (1 - math.exp(-rapidez * dt))
        mezcla = 1 - math.exp(-dt * 6 / SEGUNDOS_TRANSICION_COLOR)
        self._principal += (_rgb(self.paleta.principal) - self._principal) * mezcla
        self._claro += (_rgb(self.paleta.claro) - self._claro) * mezcla
        self.disposicion.paso()
        self._dibujar()

    def _brillo_base(self) -> float:
        if self.hablando_como or self.escuchando:
            return 0.35
        return 0.18 + 0.06 * math.sin(self._tiempo * 2 * math.pi / 4)  # en reposo "respira"

    def _dibujar(self) -> None:
        cx, cy = self._ancho / 2, self._alto / 2
        lado = max(min(self._ancho, self._alto) / 2 - MARGEN, 40) * (1 + 0.04 * self.nivel)
        brillo = self._brillo_base() + 0.5 * self.nivel
        principal, claro = self._principal, self._claro

        # El aura se desvanece justo en el borde del lienzo: si fuera más grande se vería cortada en recto.
        radio_aura = min(self._ancho, self._alto) / 2
        self._aura.x, self._aura.y, self._aura.radius = cx, cy, radio_aura
        self._aura.paint = ft.Paint(
            gradient=ft.PaintRadialGradient(
                center=ft.Offset(cx, cy),
                radius=radio_aura,
                colors=[_color(principal, 0.04 + 0.22 * brillo), _color(principal, 0.0)],
            )
        )
        if not self._nodos:
            return

        pos = self.disposicion.pos - self.disposicion.pos.mean(axis=0)
        radio = max(float(np.linalg.norm(pos, axis=1).max()), 0.3)
        self._radio_vista += (radio - self._radio_vista) * 0.1  # sin saltos de zoom cuando entra una nota
        x, y, perspectiva, profundidad = proyectar(pos / self._radio_vista, self._angulo)
        sx, sy = cx + x * lado, cy + y * lado
        cercania = 1 - 0.6 * profundidad  # lo lejano se ve más tenue

        for linea, arista, (i, j) in zip(self._lineas, self._aristas, self.disposicion.extremos):
            opacidad = (0.65 + 0.2 * self.nivel if arista.es_enlace else 0.32 + 0.25 * self.nivel) * (cercania[i] + cercania[j]) / 2
            color_linea = claro if arista.es_enlace else principal
            color_linea = color_linea + (BLANCO - color_linea) * MEZCLA_BRILLO_HOLOGRAMA
            linea.x1, linea.y1, linea.x2, linea.y2 = sx[i], sy[i], sx[j], sy[j]
            linea.paint = ft.Paint(
                color=_color(color_linea, opacidad),
                stroke_width=1.4 if arista.es_enlace else 0.9,
                blend_mode=ft.BlendMode.PLUS,
            )

        encendido = 0.35 + 0.65 * self.nivel
        for i, nodo in enumerate(self._nodos):
            radio_nodo = (RADIO_CARPETA if nodo.es_carpeta else RADIO_NOTA) * perspectiva[i]
            radio_halo = radio_nodo * (2.5 + 2.5 * self.nivel)
            halo, nucleo, etiqueta = self._halos[i], self._nucleos[i], self._etiquetas[i]

            halo.x, halo.y, halo.radius = sx[i], sy[i], radio_halo
            halo.paint = ft.Paint(
                gradient=ft.PaintRadialGradient(
                    center=ft.Offset(sx[i], sy[i]),
                    radius=radio_halo,
                    colors=[_color(principal, brillo * cercania[i]), _color(principal, 0.0)],
                ),
                blend_mode=ft.BlendMode.PLUS,
            )

            # Núcleo tipo holograma: un gradiente translúcido (no un disco sólido), con blanco
            # mezclado para que se vea más brillante y "proyectado" que un color plano.
            color_nucleo = claro if nodo.es_carpeta else principal + (claro - principal) * encendido
            color_nucleo = color_nucleo + (BLANCO - color_nucleo) * MEZCLA_BRILLO_HOLOGRAMA
            radio_nucleo = radio_nodo * 1.4
            opacidad_nucleo = (0.32 + 0.28 * cercania[i]) * (0.8 + 0.2 * encendido)
            nucleo.x, nucleo.y, nucleo.radius = sx[i], sy[i], radio_nucleo
            nucleo.paint = ft.Paint(
                gradient=ft.PaintRadialGradient(
                    center=ft.Offset(sx[i], sy[i]),
                    radius=radio_nucleo,
                    colors=[_color(BLANCO, opacidad_nucleo), _color(color_nucleo, opacidad_nucleo * 0.5), _color(color_nucleo, 0.0)],
                    color_stops=[0.0, 0.5, 1.0],
                ),
                blend_mode=ft.BlendMode.PLUS,
            )

            if nodo.es_carpeta:
                opacidad_etiqueta = 0.8 * cercania[i]
            else:
                opacidad_etiqueta = 0.6 * max(0.0, 1 - profundidad[i] / PROFUNDIDAD_MAXIMA_ETIQUETA)
            etiqueta.x, etiqueta.y = sx[i], sy[i] + radio_nodo + 3
            etiqueta.style = ft.TextStyle(
                size=11 if nodo.es_carpeta else 10,
                weight=ft.FontWeight.BOLD if nodo.es_carpeta else None,
                color=_color(claro, opacidad_etiqueta),
            )
