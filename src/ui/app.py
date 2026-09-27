"""UI de escritorio (Flet) para Jarvis.

Dos apartados en páginas separadas:
- Voz: el agente elegido se representa como el grafo 3D de la bóveda de
  Obsidian (notas y sus conexiones), girando y con el color del agente. Se
  actualiza solo cuando cambia la bóveda, y brilla al ritmo del volumen de
  la voz del agente. Se le habla llamándolo por su nombre ("Crimson, ...")
  — eso abre una ventana de conversación de un minuto en la que ya no hace
  falta repetir el nombre — o con el micrófono (tocar para empezar, tocar
  para terminar). Se le puede interrumpir a medio hablar (llamándolo de
  nuevo, o tocando el micrófono) para decirle otra cosa, y se le puede
  pedir que cierre la aplicación (con confirmación de por medio).
- Chat: conversación por texto.

El agente se elige a mano arriba o diciendo su nombre: Crimson fuerza
Ollama y Clover fuerza Gemini.
"""

import asyncio
import threading
import time

import flet as ft
import sounddevice as sd

from src.actions.confirmacion import es_afirmativo
from src.agente.conversacion import Conversacion
from src.main import procesar_comando
from src.obsidian.grafo import construir_grafo, firma_boveda
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor
from src.ui.grafo3d import GrafoAgente
from src.ui.paletas import PALETAS, Paleta
from src.voice.activacion import VentanaConversacion, detectar_nombre
from src.voice.escucha_continua import EscuchaContinua
from src.voice.stt import Grabadora, grabar_hasta_silencio, transcribir
from src.voice.tts import MedidorDeVolumen, hablar

AGENTES = (MOTOR_OLLAMA, MOTOR_GEMINI)
COLOR_USUARIO = ft.Colors.BLUE_GREY_200
FONDO = "#0B0E14"
ESTADO_VOZ_REPOSO = "Toca el micrófono para hablar"
SEGUNDOS_AVISO = 4  # cuánto se muestra un aviso ("No te entendí...") antes de volver al estado normal
CUADROS_POR_SEGUNDO = 30
SEGUNDOS_ENTRE_REVISIONES_BOVEDA = 2
SEGUNDOS_ENTRE_ESTADOS = 0.5


class JarvisApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.agente = MOTOR_OLLAMA
        self.grabadora = Grabadora()
        # Una sola conversación compartida por Voz y Chat: son la misma charla.
        self.conversacion = Conversacion()
        self.ocupado = False
        self.ventana = VentanaConversacion()
        self.escucha = EscuchaContinua(self._al_escuchar_frase)
        # Las frases llegan en hilos separados; se atienden de una en una.
        self._turno = threading.Lock()
        self._aviso: str | None = None
        self._aviso_hasta = 0.0
        # Se activa para cortar al agente a medio hablar (interrupción).
        self._interrumpir = threading.Event()
        self.medidor = MedidorDeVolumen()
        self._firma_boveda: tuple | None = None

        self.grafo = GrafoAgente(self.agente)
        self.selector = self._construir_selector()
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
        self.interruptor_nombre = ft.Switch(
            label="Activar diciendo su nombre",
            value=True,
            on_change=self.cambiar_activacion_por_nombre,
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
                ft.Container(content=self.grafo.control, expand=True),
                self.nombre_agente,
                self.estado_voz,
                ft.Container(height=10),
                self.boton_micro,
                self.interruptor_nombre,
                ft.Container(
                    content=ft.Column([self.ultimo_usuario, self.ultima_respuesta], spacing=6, scroll=ft.ScrollMode.AUTO),
                    height=120,
                    padding=ft.Padding(20, 0, 20, 0),
                ),
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
        page.window.height = 900
        page.window.min_width = 400
        page.window.min_height = 660
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
            ft.Row([self.selector], alignment=ft.MainAxisAlignment.CENTER),
            ft.Stack([self.vista_voz, self.vista_chat], expand=True),
        )
        self._refrescar_agente()
        if self.interruptor_nombre.value:
            self._iniciar_escucha()
        self.estado_voz.value = self._texto_estado()
        page.update()
        page.run_task(self._animar)

    # ---------- estado visual ----------

    def _paleta_actual(self) -> Paleta:
        return PALETAS[self.agente]

    def _refrescar_agente(self) -> None:
        paleta = self._paleta_actual()
        self.nombre_agente.value = nombre_motor(self.agente)
        self.nombre_agente.color = paleta.principal
        self.interruptor_nombre.active_color = paleta.principal
        if not self.grabadora.grabando:
            self.boton_micro.bgcolor = paleta.principal
        self.grafo.cambiar_agente(self.agente)

    def _seleccionar_agente(self, motor: str) -> None:
        self.agente = motor
        self.selector.selected = [motor]
        self.ventana.agente = motor
        self._refrescar_agente()

    def _avisar(self, mensaje: str) -> None:
        """Muestra un aviso pasajero en el estado de voz (luego vuelve al estado normal)."""
        self._aviso = mensaje
        self._aviso_hasta = time.monotonic() + SEGUNDOS_AVISO

    def _texto_estado(self) -> str:
        if self._aviso and time.monotonic() < self._aviso_hasta:
            return self._aviso
        nombre = nombre_motor(self.agente)
        if self.escucha.activa and self.ventana.abierta:
            return f"{nombre} te escucha · {int(self.ventana.segundos_restantes())} s"
        if self.escucha.activa:
            return f'Di "{nombre}" o toca el micrófono'
        return ESTADO_VOZ_REPOSO

    async def _animar(self) -> None:
        anterior = time.monotonic()
        proxima_revision = proximo_estado = proximo_cuadro = anterior
        while True:
            ahora = time.monotonic()
            proximo_cuadro = max(proximo_cuadro + 1 / CUADROS_POR_SEGUNDO, ahora)
            if ahora >= proxima_revision:
                await self._revisar_boveda()
                proxima_revision = ahora + SEGUNDOS_ENTRE_REVISIONES_BOVEDA
            self.grafo.escuchando = self.grabadora.grabando or (self.escucha.activa and self.ventana.abierta)
            self.grafo.avanzar(ahora - anterior, self.medidor.nivel)
            anterior = ahora
            self.grafo.control.update()
            if ahora >= proximo_estado and not self.ocupado and not self.grabadora.grabando:
                self.estado_voz.value = self._texto_estado()
                self.estado_voz.update()
                proximo_estado = ahora + SEGUNDOS_ENTRE_ESTADOS
            await asyncio.sleep(max(0.0, proximo_cuadro - time.monotonic()))

    async def _revisar_boveda(self) -> None:
        """Si cambió alguna nota (nueva, editada o borrada), rehace el grafo."""
        try:
            firma = await asyncio.to_thread(firma_boveda)
            if firma == self._firma_boveda:
                return
            grafo = await asyncio.to_thread(construir_grafo)
        except (RuntimeError, OSError):
            return  # bóveda sin configurar, o una nota cambió justo mientras se leía: se reintenta en la próxima revisión
        self._firma_boveda = firma
        # En otro hilo: la primera vez acomoda el grafo entero y no debe congelar la ventana.
        await asyncio.to_thread(self.grafo.mostrar_grafo, grafo)

    # ---------- eventos ----------

    def cambiar_apartado(self, e) -> None:
        en_voz = e.control.selected_index == 0
        self.vista_voz.visible = en_voz
        self.vista_chat.visible = not en_voz
        self.page.update()

    def cambiar_agente(self, e) -> None:
        self._seleccionar_agente(e.control.selected[0])
        self.page.update()

    def _iniciar_escucha(self) -> None:
        try:
            self.escucha.iniciar()
        except sd.PortAudioError as error:
            self.interruptor_nombre.value = False
            self._avisar(f"No pude abrir el micrófono: {error}")

    def cambiar_activacion_por_nombre(self, e) -> None:
        if self.interruptor_nombre.value:
            self._iniciar_escucha()
        else:
            self.escucha.detener()
            self.ventana.cerrar()
        self.estado_voz.value = self._texto_estado()
        self.page.update()

    def _motor_forzado(self) -> str:
        """Siempre hay un agente elegido (Crimson u Clover): nunca se deja que el router decida solo."""
        return self.agente

    def _motor_mostrado(self, motor: str) -> str:
        """A qué agente atribuirle la respuesta para mostrar/hablar.

        Las acciones directas (abrir apps) no las contesta ningún motor de
        IA, así que internamente siempre llegan como MOTOR_ACCION. Se le
        atribuyen al agente seleccionado (Crimson/Clover) — le habló a ese
        agente, y ese agente debe confirmarle (con su voz y color incluidos).
        """
        if motor == MOTOR_ACCION:
            return self.agente
        return motor

    def confirmador_ui(self, descripcion: str) -> bool:
        """Confirmación por diálogo (para el chat)."""
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

    def confirmador_voz(self, descripcion: str) -> bool:
        """Confirmación hablada (para el apartado de voz): pregunta y escucha "sí" o "no"."""
        self.estado_voz.value = f"{descripcion} Di sí o no."
        self.page.update()
        hablar(f"{descripcion} Di sí o no.", motor=self._motor_mostrado(MOTOR_ACCION), medidor=self.medidor)
        respuesta = transcribir(grabar_hasta_silencio(), filtrar_ruido=True)
        return es_afirmativo(respuesta)

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

    def _al_escuchar_frase(self, audio) -> None:
        """Llega una frase de la escucha continua (incluso mientras el agente habla, para poder
        interrumpirlo llamándolo de nuevo): ¿llamaron al agente o sigue abierta la ventana?"""
        if self.grabadora.grabando:
            return  # el micrófono manual ya se está encargando de esto
        texto = transcribir(audio, filtrar_ruido=True)
        if not texto:
            return
        motor_nombrado, _resto = detectar_nombre(texto)
        if not self._turno.acquire(blocking=False):
            if motor_nombrado is None:
                return  # turno en curso y no lo llamaron por su nombre: probablemente es su propio eco
            self._interrumpir.set()  # lo volvieron a llamar a medio hablar: cortarlo y atenderlo
            self._turno.acquire()  # espera a que el turno interrumpido suelte el lock de verdad
        try:
            agente, mensaje = self.ventana.procesar(texto)
            if agente is None:
                return  # no le hablaban al asistente
            if agente != self.agente:
                self._seleccionar_agente(agente)
            if not mensaje:
                self.estado_voz.value = self._texto_estado()
                self.page.update()
                return  # solo lo llamaron por su nombre: queda escuchando
            self._atender_voz(mensaje)
        finally:
            self._turno.release()

    def tocar_microfono(self, e) -> None:
        if not self.grabadora.grabando:
            if self.ocupado:
                self._interrumpir.set()  # corta al agente a medio hablar/pensar
            self.escucha.pausar()
            self.grabadora.iniciar()
            self.icono_micro.icon = ft.Icons.STOP_ROUNDED
            self.boton_micro.bgcolor = ft.Colors.RED_700
            self.estado_voz.value = "Escuchando... toca otra vez para terminar"
            self.page.update()
            return

        audio = self.grabadora.detener()
        self.ocupado = True
        self.icono_micro.icon = ft.Icons.MIC
        self.boton_micro.bgcolor = ft.Colors.GREY_700
        self.estado_voz.value = "Transcribiendo..."
        self.page.update()
        threading.Thread(target=self._procesar_grabacion, args=(audio,), daemon=True).start()

    def _procesar_grabacion(self, audio) -> None:
        with self._turno:
            texto = transcribir(audio)
            if texto:
                self._atender_voz(texto)
                return
            self._avisar("No te entendí, intenta de nuevo")
            self._terminar_turno_de_voz()

    def _atender_voz(self, texto: str) -> None:
        """Responde a lo dicho por voz (por el micrófono o llamando al agente por su nombre).

        La escucha sigue activa mientras piensa y habla, así que se le
        puede volver a llamar por su nombre para interrumpirlo y decirle
        otra cosa (ver _al_escuchar_frase). El costo es que puede oír su
        propio eco: por eso una frase sin su nombre durante un turno en
        curso se ignora en vez de contestarse a sí mismo en bucle.
        """
        self.ocupado = True
        self._interrumpir.clear()
        try:
            self.ultimo_usuario.value = f"Tú: {texto}"
            self.ultima_respuesta.value = ""
            self.estado_voz.value = "Pensando..."
            self._agregar_al_historial("Tú", texto, COLOR_USUARIO)
            self.page.update()

            respuesta = procesar_comando(
                texto,
                confirmador=self.confirmador_voz,
                motor_forzado=self._motor_forzado(),
                conversacion=self.conversacion,
            )

            motor_mostrado = self._motor_mostrado(respuesta.motor)
            paleta = PALETAS.get(motor_mostrado, self._paleta_actual())
            nombre = nombre_motor(motor_mostrado)
            self.ultima_respuesta.value = f"{nombre}: {respuesta.texto}"
            self.ultima_respuesta.color = paleta.claro
            self.estado_voz.value = f"{nombre} está hablando..."
            self._agregar_al_historial(nombre, respuesta.texto, paleta.principal)
            self.grafo.empezar_a_hablar(motor_mostrado)
            self.page.update()

            hablar(respuesta.texto, motor=motor_mostrado, medidor=self.medidor, detener=self._interrumpir)
            if respuesta.cerrar:
                self.page.run_task(self.page.window.close)
        finally:
            self._terminar_turno_de_voz()

    def _terminar_turno_de_voz(self) -> None:
        self.grafo.dejar_de_hablar()
        self.ocupado = False
        self.boton_micro.bgcolor = self._paleta_actual().principal
        if self.escucha.activa:
            # El minuto cuenta desde que el agente terminó de hablar, no desde que se le preguntó.
            self.ventana.agente = self.agente
            self.ventana.extender()
            self.escucha.reanudar()
        self.estado_voz.value = self._texto_estado()
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
        with self._turno:
            self.ocupado = True
            try:
                respuesta = procesar_comando(
                    texto,
                    confirmador=self.confirmador_ui,
                    motor_forzado=self._motor_forzado(),
                    conversacion=self.conversacion,
                )
                motor_mostrado = self._motor_mostrado(respuesta.motor)
                paleta = PALETAS.get(motor_mostrado, self._paleta_actual())
                self._agregar_al_historial(nombre_motor(motor_mostrado), respuesta.texto, paleta.principal)
                if respuesta.cerrar:
                    self.page.run_task(self.page.window.close)
            finally:
                self.ocupado = False
                self.estado_chat.value = ""
                self.page.update()


def construir_app(page: ft.Page) -> None:
    JarvisApp(page).montar()
