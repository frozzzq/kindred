"""UI de escritorio (Flet) para Jarvis.

Dos apartados en páginas separadas:
- Voz: el agente elegido se representa como un orbe animado en el centro;
  un micrófono debajo se toca para empezar a grabar y otra vez para terminar.
  Cuando el agente habla, el orbe brilla con su color.
- Chat: conversación por texto.

El agente se elige a mano arriba (compartido por ambos apartados): Crimson
fuerza Ollama, Clover fuerza Gemini y Jarvis deja que el router decida.
Reutiliza procesar_comando y los módulos de voice/ sin adaptarlos.
"""

import asyncio
import threading
from dataclasses import dataclass

import flet as ft

from src.main import procesar_comando
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor
from src.voice.stt import Grabadora, transcribir
from src.voice.tts import hablar


@dataclass(frozen=True)
class Paleta:
    principal: str
    oscuro: str
    claro: str


# Jarvis se identifica con MOTOR_ACCION: es el orquestador (router automático
# y acciones del sistema), no un motor de IA en sí.
PALETAS = {
    MOTOR_OLLAMA: Paleta(principal="#DC143C", oscuro="#4A0717", claro="#FF7A8F"),  # Crimson: carmesí elegante
    MOTOR_GEMINI: Paleta(principal="#9D4EDD", oscuro="#240046", claro="#E0AAFF"),  # Clover: violeta oscuro brillante
    MOTOR_ACCION: Paleta(principal="#00B4FF", oscuro="#001F3F", claro="#8BE9FF"),  # Jarvis: azul futurista
}
AGENTES = (MOTOR_OLLAMA, MOTOR_GEMINI, MOTOR_ACCION)
COLOR_USUARIO = ft.Colors.BLUE_GREY_200
FONDO = "#0B0E14"
ESTADO_VOZ_REPOSO = "Toca el micrófono para hablar"

# Recorrido del foco de luz dentro del orbe, para que se sienta "vivo".
CENTROS_DE_LUZ = (
    ft.Alignment(-0.35, -0.35),
    ft.Alignment(0.3, -0.25),
    ft.Alignment(0.25, 0.3),
    ft.Alignment(-0.3, 0.25),
)


class Orbe:
    """Círculo que representa al agente: respira en reposo y brilla al hablar."""

    TAMANO = 210

    def __init__(self, motor: str) -> None:
        self.motor = motor
        self.hablando_como: str | None = None
        self.escuchando = False
        self._paso = 0
        self.control = ft.Container(
            width=self.TAMANO,
            height=self.TAMANO,
            shape=ft.BoxShape.CIRCLE,
            scale=1.0,
        )
        self._aplicar()

    @property
    def intervalo(self) -> float:
        """Segundos entre pasos de la animación: más rápido al hablar/escuchar."""
        if self.hablando_como:
            return 0.45
        if self.escuchando:
            return 0.8
        return 1.4

    def _aplicar(self) -> None:
        paleta = PALETAS[self.hablando_como or self.motor]
        hablando = self.hablando_como is not None
        duracion = int(self.intervalo * 1000)

        self.control.animate = ft.Animation(duracion, ft.AnimationCurve.EASE_IN_OUT)
        self.control.animate_scale = ft.Animation(duracion, ft.AnimationCurve.EASE_IN_OUT)
        self.control.gradient = ft.RadialGradient(
            colors=[paleta.claro, paleta.principal, paleta.oscuro],
            stops=[0.0, 0.5, 1.0],
            center=CENTROS_DE_LUZ[self._paso % len(CENTROS_DE_LUZ)],
            radius=0.9,
        )
        self.control.shadow = ft.BoxShadow(
            spread_radius=22 if hablando else 4,
            blur_radius=90 if hablando else 40,
            color=ft.Colors.with_opacity(0.9 if hablando else 0.4, paleta.principal),
        )

    def cambiar_agente(self, motor: str) -> None:
        self.motor = motor
        self._aplicar()

    def empezar_a_hablar(self, motor: str) -> None:
        self.hablando_como = motor
        self._aplicar()

    def dejar_de_hablar(self) -> None:
        self.hablando_como = None
        self._aplicar()

    def latido(self) -> None:
        """Un paso de la animación continua (movimiento de la luz + respiración)."""
        self._paso += 1
        if self.hablando_como:
            amplitud = 0.09
        elif self.escuchando:
            amplitud = 0.06
        else:
            amplitud = 0.035
        self.control.scale = 1 + amplitud if self._paso % 2 else 1.0
        self._aplicar()


class JarvisApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.agente = MOTOR_ACCION
        self.grabadora = Grabadora()
        self.ocupado = False

        self.orbe = Orbe(self.agente)
        self.nombre_agente = ft.Text(size=26, weight=ft.FontWeight.BOLD)
        self.estado_voz = ft.Text(size=14, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER)
        self.icono_micro = ft.Icon(ft.Icons.MIC, size=34, color=ft.Colors.WHITE)
        self.boton_micro = ft.Container(
            content=self.icono_micro,
            width=76,
            height=76,
            shape=ft.BoxShape.CIRCLE,
            alignment=ft.Alignment(0, 0),
            on_click=self.tocar_microfono,
            animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            tooltip="Toca para hablar, toca otra vez para terminar",
        )
        self.ultimo_usuario = ft.Text(size=13, color=COLOR_USUARIO, text_align=ft.TextAlign.CENTER)
        self.ultima_respuesta = ft.Text(size=13, text_align=ft.TextAlign.CENTER, selectable=True)

        self.historial = ft.ListView(expand=True, spacing=12, auto_scroll=True)
        self.campo_texto = ft.TextField(hint_text="Escribe un mensaje...", expand=True, on_submit=self.enviar_texto)
        self.estado_chat = ft.Text("", italic=True, color=ft.Colors.GREY_500)

        self.vista_voz = self._construir_vista_voz()
        self.vista_chat = self._construir_vista_chat()
        self.vista_chat.visible = False

    # ---------- construcción ----------

    def _construir_selector(self) -> ft.SegmentedButton:
        return ft.SegmentedButton(
            segments=[ft.Segment(value=motor, label=nombre_motor(motor)) for motor in AGENTES],
            selected=[self.agente],
            allow_empty_selection=False,
            on_change=self.cambiar_agente,
        )

    def _construir_vista_voz(self) -> ft.Column:
        return ft.Column(
            [
                ft.Container(expand=True),
                ft.Container(content=self.orbe.control, padding=40, alignment=ft.Alignment(0, 0)),
                self.nombre_agente,
                self.estado_voz,
                ft.Container(height=10),
                self.boton_micro,
                ft.Container(height=10),
                ft.Container(
                    content=ft.Column([self.ultimo_usuario, self.ultima_respuesta], spacing=6, scroll=ft.ScrollMode.AUTO),
                    height=120,
                    padding=ft.Padding(20, 0, 20, 0),
                ),
                ft.Container(expand=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

    def _construir_vista_chat(self) -> ft.Column:
        return ft.Column(
            [
                self.historial,
                self.estado_chat,
                ft.Row([self.campo_texto, ft.IconButton(icon=ft.Icons.SEND, tooltip="Enviar", on_click=self.enviar_texto)]),
            ],
            expand=True,
        )

    def montar(self) -> None:
        page = self.page
        page.title = "Jarvis"
        page.window.width = 480
        page.window.height = 780
        page.window.min_width = 400
        page.window.min_height = 620
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = FONDO
        page.padding = 16

        page.navigation_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.GRAPHIC_EQ, label="Voz"),
                ft.NavigationBarDestination(icon=ft.Icons.CHAT_BUBBLE_OUTLINE, label="Chat"),
            ],
            selected_index=0,
            on_change=self.cambiar_apartado,
        )
        page.add(
            ft.Row([self._construir_selector()], alignment=ft.MainAxisAlignment.CENTER),
            ft.Stack([self.vista_voz, self.vista_chat], expand=True),
        )
        self._refrescar_agente()
        self.estado_voz.value = ESTADO_VOZ_REPOSO
        page.update()
        page.run_task(self._animar)

    # ---------- estado visual ----------

    def _paleta_actual(self) -> Paleta:
        return PALETAS[self.agente]

    def _refrescar_agente(self) -> None:
        paleta = self._paleta_actual()
        self.nombre_agente.value = nombre_motor(self.agente)
        self.nombre_agente.color = paleta.principal
        if not self.grabadora.grabando:
            self.boton_micro.bgcolor = paleta.principal
        self.orbe.cambiar_agente(self.agente)

    async def _animar(self) -> None:
        while True:
            self.orbe.latido()
            self.orbe.control.update()
            await asyncio.sleep(self.orbe.intervalo)

    # ---------- eventos ----------

    def cambiar_apartado(self, e) -> None:
        en_voz = e.control.selected_index == 0
        self.vista_voz.visible = en_voz
        self.vista_chat.visible = not en_voz
        self.page.update()

    def cambiar_agente(self, e) -> None:
        self.agente = e.control.selected[0]
        self._refrescar_agente()
        self.page.update()

    def _motor_forzado(self) -> str | None:
        return None if self.agente == MOTOR_ACCION else self.agente

    def _motor_mostrado(self, motor: str) -> str:
        """A qué agente atribuirle la respuesta para mostrar/hablar.

        Las acciones directas (abrir apps) no las contesta ningún motor de
        IA, así que internamente siempre llegan como MOTOR_ACCION. Si el
        usuario tenía un agente específico seleccionado (Crimson/Clover),
        se lo atribuimos a ese agente en vez de saltar a Jarvis — le habló
        a ese agente, y ese agente debe confirmarle (con su voz y color
        incluidos). Con Jarvis (automático) seleccionado, sí se queda
        como Jarvis.
        """
        if motor == MOTOR_ACCION and self.agente != MOTOR_ACCION:
            return self.agente
        return motor

    def confirmador_ui(self, descripcion: str) -> bool:
        """Confirmación por diálogo (misma idea que confirmar_por_texto/voz, pero en UI)."""
        resultado = {"valor": False}
        evento = threading.Event()

        def responder(valor: bool):
            def manejador(e):
                resultado["valor"] = valor
                self.page.pop_dialog()
                evento.set()

            return manejador

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Confirmar acción"),
                content=ft.Text(descripcion),
                actions=[
                    ft.TextButton("Sí", on_click=responder(True)),
                    ft.TextButton("No", on_click=responder(False)),
                ],
            )
        )
        self.page.update()
        evento.wait()
        return resultado["valor"]

    def _agregar_al_historial(self, nombre: str, texto: str, color: str) -> None:
        self.historial.controls.append(
            ft.Container(
                content=ft.Column(
                    [ft.Text(nombre, weight=ft.FontWeight.BOLD, color=color, size=12), ft.Text(texto, selectable=True)],
                    spacing=2,
                ),
                bgcolor=ft.Colors.with_opacity(0.1, color),
                border_radius=10,
                padding=10,
            )
        )

    # --- voz ---

    def tocar_microfono(self, e) -> None:
        if self.ocupado:
            return
        if not self.grabadora.grabando:
            self.grabadora.iniciar()
            self.orbe.escuchando = True
            self.icono_micro.icon = ft.Icons.STOP_ROUNDED
            self.boton_micro.bgcolor = ft.Colors.RED_700
            self.estado_voz.value = "Escuchando... toca otra vez para terminar"
            self.page.update()
            return

        audio = self.grabadora.detener()
        self.orbe.escuchando = False
        self.ocupado = True
        self.icono_micro.icon = ft.Icons.MIC
        self.boton_micro.bgcolor = ft.Colors.GREY_700
        self.estado_voz.value = "Transcribiendo..."
        self.page.update()
        threading.Thread(target=self._procesar_voz, args=(audio,), daemon=True).start()

    def _procesar_voz(self, audio) -> None:
        aviso = None
        try:
            texto = transcribir(audio)
            if not texto:
                aviso = "No te entendí, intenta de nuevo"
                return

            self.ultimo_usuario.value = f"Tú: {texto}"
            self.ultima_respuesta.value = ""
            self.estado_voz.value = "Pensando..."
            self._agregar_al_historial("Tú", texto, COLOR_USUARIO)
            self.page.update()

            respuesta = procesar_comando(texto, confirmador=self.confirmador_ui, motor_forzado=self._motor_forzado())

            motor_mostrado = self._motor_mostrado(respuesta.motor)
            paleta = PALETAS.get(motor_mostrado, self._paleta_actual())
            nombre = nombre_motor(motor_mostrado)
            self.ultima_respuesta.value = f"{nombre}: {respuesta.texto}"
            self.ultima_respuesta.color = paleta.claro
            self.estado_voz.value = f"{nombre} está hablando..."
            self._agregar_al_historial(nombre, respuesta.texto, paleta.principal)
            self.orbe.empezar_a_hablar(motor_mostrado)
            self.page.update()

            hablar(respuesta.texto, motor=motor_mostrado)
        finally:
            self.orbe.dejar_de_hablar()
            self.ocupado = False
            self.boton_micro.bgcolor = self._paleta_actual().principal
            self.estado_voz.value = aviso or ESTADO_VOZ_REPOSO
            self.page.update()

    # --- chat ---

    def enviar_texto(self, e) -> None:
        texto = self.campo_texto.value.strip()
        if not texto:
            return
        self.campo_texto.value = ""
        self._agregar_al_historial("Tú", texto, COLOR_USUARIO)
        self.estado_chat.value = "Pensando..."
        self.page.update()
        threading.Thread(target=self._procesar_chat, args=(texto,), daemon=True).start()

    def _procesar_chat(self, texto: str) -> None:
        try:
            respuesta = procesar_comando(texto, confirmador=self.confirmador_ui, motor_forzado=self._motor_forzado())
            motor_mostrado = self._motor_mostrado(respuesta.motor)
            paleta = PALETAS.get(motor_mostrado, self._paleta_actual())
            self._agregar_al_historial(nombre_motor(motor_mostrado), respuesta.texto, paleta.principal)
        finally:
            self.estado_chat.value = ""
            self.page.update()


def construir_app(page: ft.Page) -> None:
    JarvisApp(page).montar()
