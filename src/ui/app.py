"""UI de escritorio (Flet) para Crimson y Clover.

Cinco secciones, con una barra de navegación a la izquierda:
- Inicio: el agente elegido es el grafo 3D de la bóveda, girando con su color y brillando con su
  voz. Se le habla diciendo su nombre ("Crimson, ...", abre un minuto de conversación sin repetir
  el nombre) o con el micrófono. Se le puede interrumpir diciendo cualquier cosa o tocando el
  micrófono. A la derecha, el panel "Hoy" (pendientes, recurrentes, actividad reciente).
- Chat: la misma conversación por texto; la respuesta de Crimson se escribe mientras se genera.
- Bóveda: estadísticas, búsqueda por tema y conexiones sugeridas.
- Uso: métricas de cada agente (uso, velocidad, cuota de Gemini).
- Ajustes: voces, comportamiento, núcleo, modo seguro y diagnóstico.

La voz se habla en vivo: cada oración suena en cuanto el modelo la termina (src/main.py filtra
antes las que afirmarían un cambio que no se hizo).
"""

import asyncio
import difflib
import os
import threading
import time
from datetime import date

import flet as ft
import sounddevice as sd

from src import ajustes, diagnostico
from src.actions import foco
from src.actions.confirmacion import es_afirmativo
from src.agente.conversacion import Conversacion
from src.agente.saludo import saludo_del_dia
from src.herramientas.catalogo import REGISTRO
from src.herramientas.registro import ContextoEjecucion
from src.main import precalentar, procesar_comando
from src.nucleo import estado, proceso
from src.obsidian import indice
from src.obsidian.grafo import construir_grafo, firma_boveda
from src.obsidian.texto import normalizar
from src.router.intent_router import MOTOR_ACCION, MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor
from src.ui import estilo
from src.ui.grafo3d import GrafoAgente
from src.ui.paletas import PALETAS, Paleta
from src.ui.vista_ajustes import VistaAjustes
from src.ui.vista_boveda import VistaBoveda
from src.ui.vista_hoy import PanelHoy
from src.ui.vista_uso import VistaUso
from src.voice.activacion import VentanaConversacion
from src.voice.escucha_continua import EscuchaContinua
from src.voice.stt import Grabadora, grabar_hasta_silencio, transcribir
from src.voice.tts import MedidorDeVolumen, VozEnVivo, hablar

AGENTES = (MOTOR_OLLAMA, MOTOR_GEMINI)
COLOR_USUARIO = estilo.TEXTO_SUAVE
FONDO = estilo.FONDO
ESTADO_VOZ_REPOSO = "Toca el micrófono para hablar"
SEGUNDOS_AVISO = 4  # cuánto se muestra un aviso ("No te entendí...") antes de volver al estado normal
CUADROS_POR_SEGUNDO = 30
SEGUNDOS_ENTRE_REVISIONES_BOVEDA = 2
SEGUNDOS_ENTRE_ESTADOS = 0.5
SEGUNDOS_ENTRE_INDICADORES = 20
SEGUNDOS_ENTRE_PANELES = 30
CLAVE_SALUDO = "ui.ultimo_saludo"
# Ya no hace falta decir su nombre para interrumpirlo: cualquier frase durante un turno en
# curso corta y se atiende. El riesgo es oír su propio eco por las bocinas; si lo detectado se
# parece demasiado a lo que está diciendo en ese momento, se asume que es eco y se ignora.
# Es una fracción de COBERTURA (cuánto del tramo más largo de lo oído aparece seguido dentro de lo
# que dice), no un ratio() normal: el micrófono suele captar solo una oración suelta de una
# respuesta más larga, y comparar esa oración corta contra el texto completo con ratio() daba una
# similitud baja (0.3-0.4) aunque fuera eco real, porque ratio() penaliza la diferencia de longitud
# entre ambos textos. Sumar todos los bloques que coinciden (en vez de tomar solo el más largo)
# tampoco sirve: dos oraciones cualquiera en español comparten de sobra artículos y preposiciones
# sueltos ("de", "la", "el"...) y esa suma da falsos positivos (0.6-0.85 con frases sin relación).
COBERTURA_MINIMA_ANTES_DE_IGNORAR = 0.7

SUGERENCIAS_CHAT = (
    "¿Qué tengo para hoy?",
    "¿Tengo algo atrasado?",
    "Resúmeme lo que tengo apuntado de programación",
    "¿Qué notas debería conectar?",
)

SECCIONES = (
    ("Inicio", ft.Icons.GRAPHIC_EQ),
    ("Chat", ft.Icons.CHAT_BUBBLE_OUTLINE),
    ("Bóveda", ft.Icons.HUB_OUTLINED),
    ("Uso", ft.Icons.INSIGHTS),
    ("Ajustes", ft.Icons.TUNE),
)


def es_boveda_de_pruebas() -> bool:
    return "boveda-pruebas" in os.getenv("OBSIDIAN_VAULT_PATH", "")


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
        # Lo que el agente está diciendo en este instante (para distinguir una interrupción
        # real de que se escuche a sí mismo por las bocinas); vacío cuando no habla.
        self._texto_hablando = ""
        self.medidor = MedidorDeVolumen()
        self._firma_boveda: tuple | None = None
        self._seccion = 0

        self.grafo = GrafoAgente(self.agente)
        self.selector = self._construir_selector()
        self.selector_chat = self._construir_selector()
        self.nombre_agente = ft.Text(size=28, weight=ft.FontWeight.W_700)
        self.estado_voz = ft.Text(size=14, color=estilo.TEXTO_SUAVE, text_align=ft.TextAlign.CENTER)
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
            label="Escuchar siempre (activar diciendo su nombre)",
            value=bool(ajustes.obtener("activar_por_nombre")),
            on_change=self.cambiar_activacion_por_nombre,
        )
        self.ultimo_usuario = ft.Text(size=13, color=COLOR_USUARIO, text_align=ft.TextAlign.CENTER)
        self.ultima_respuesta = ft.Text(size=14, text_align=ft.TextAlign.CENTER, selectable=True)
        self.indicadores = ft.Row(spacing=8, wrap=True)

        self.historial = ft.ListView(expand=True, spacing=12, auto_scroll=True, padding=ft.Padding(4, 8, 4, 8))
        self.campo_texto = ft.TextField(
            hint_text="Escríbele a tu agente...", expand=True, on_submit=self.enviar_texto, border_radius=14, shift_enter=True
        )
        self._bienvenida = self._construir_bienvenida()
        self.historial.controls.append(self._bienvenida)
        self.estado_chat = ft.Text("", italic=True, color=estilo.TEXTO_TENUE, size=12)

        self.panel_hoy = PanelHoy(completar=self._completar_desde_ui)
        self.vista_boveda = VistaBoveda(conectar=self._conectar_desde_ui, color=lambda: self._paleta_actual().principal)
        self.vista_uso = VistaUso()
        self.vista_ajustes = VistaAjustes(al_cambiar_activacion=self._activacion_desde_ajustes, confirmar=self.confirmador_ui)

        self.vista_voz = self._construir_vista_voz()
        self.vista_chat = self._construir_vista_chat()
        self._vistas = [self.vista_voz, self.vista_chat, self.vista_boveda.control, self.vista_uso.control, self.vista_ajustes.control]
        for i, vista in enumerate(self._vistas):
            vista.visible = i == 0

    # ---------- construcción ----------

    def _construir_selector(self) -> ft.SegmentedButton:
        return ft.SegmentedButton(
            segments=[ft.Segment(value=motor, label=nombre_motor(motor)) for motor in AGENTES],
            selected=[self.agente],
            allow_empty_selection=False,
            on_change=self.cambiar_agente,
        )

    def _construir_vista_voz(self) -> ft.Control:
        encabezado = [self.selector, self.indicadores]
        if es_boveda_de_pruebas():
            encabezado.append(estilo.indicador("MODO PRUEBAS", None, os.getenv("OBSIDIAN_VAULT_PATH", "")))
        agente = ft.Column(
            [
                ft.Row(encabezado, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                ft.Container(content=self.grafo.control, expand=True),
                self.nombre_agente,
                self.estado_voz,
                ft.Container(height=8),
                self.boton_micro,
                self.interruptor_nombre,
                ft.Container(
                    content=ft.Column([self.ultimo_usuario, self.ultima_respuesta], spacing=6, scroll=ft.ScrollMode.AUTO),
                    height=110,
                    padding=ft.Padding(24, 0, 24, 0),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
        return ft.Row([agente, ft.Container(content=self.panel_hoy.control, width=350)], spacing=16, expand=True)

    def _construir_bienvenida(self) -> ft.Control:
        def sugerir(texto: str):
            def al_tocar(_e):
                self.campo_texto.value = texto
                self.enviar_texto(None)

            return al_tocar

        return ft.Container(
            content=ft.Column(
                [
                    estilo.texto("¿En qué te ayudo?", 20, peso=ft.FontWeight.W_700),
                    estilo.texto("Pregúntale lo que sea: sabe lo que tienes en tu bóveda y tus pendientes.", 13, estilo.TEXTO_SUAVE),
                    ft.Row(
                        [ft.OutlinedButton(content=s, on_click=sugerir(s)) for s in SUGERENCIAS_CHAT],
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=ft.Padding(24, 80, 24, 24),
        )

    def _construir_vista_chat(self) -> ft.Control:
        return ft.Column(
            [
                ft.Row([estilo.texto("Chat", 22, peso=ft.FontWeight.W_700), self.selector_chat], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                estilo.tarjeta(self.historial, expand=True, padding=8),
                self.estado_chat,
                ft.Row(
                    [
                        self.campo_texto,
                        ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="Enviar", on_click=self.enviar_texto, icon_size=26),
                    ]
                ),
            ],
            expand=True,
        )

    def montar(self) -> None:
        # Para que "escribe X"/"haz click en Y" apunten a la ventana de antes (ej. el Bloc de
        # notas) y no a esta misma UI, que le acaba de robar el foco al hablarle/escribirle.
        foco.iniciar_rastreo()

        page = self.page
        page.title = "Crimson y Clover" + (" · MODO PRUEBAS" if es_boveda_de_pruebas() else "")
        page.window.width = 1240
        page.window.height = 820
        page.window.min_width = 980
        page.window.min_height = 660
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed=PALETAS[MOTOR_OLLAMA].principal)
        page.bgcolor = FONDO
        page.padding = 0

        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=84,
            bgcolor=estilo.SUPERFICIE,
            leading=ft.Container(
                content=ft.Text("C&C", size=16, weight=ft.FontWeight.W_800, color=PALETAS[MOTOR_OLLAMA].claro),
                padding=ft.Padding(0, 18, 0, 18),
            ),
            destinations=[ft.NavigationRailDestination(icon=icono, label=nombre) for nombre, icono in SECCIONES],
            on_change=self.cambiar_apartado,
        )
        page.add(
            ft.Row(
                [
                    self.rail,
                    ft.Container(content=ft.Stack(self._vistas, expand=True), expand=True, padding=ft.Padding(20, 16, 20, 16)),
                ],
                spacing=0,
                expand=True,
            )
        )
        self._refrescar_agente()
        if self.interruptor_nombre.value:
            self._iniciar_escucha()
        self.estado_voz.value = self._texto_estado()
        page.update()
        page.run_task(self._animar)
        threading.Thread(target=self._al_arrancar, daemon=True).start()

    def _al_arrancar(self) -> None:
        """Trabajo lento de arranque, fuera del hilo de la UI."""
        precalentar()  # carga qwen3 y su prompt: el primer mensaje ya no paga ~35 s de recarga
        indice.actualizar_sin_fallar()
        if ajustes.obtener("iniciar_nucleo") and not proceso.esta_vivo() and not es_boveda_de_pruebas():
            proceso.iniciar()
        self._refrescar_paneles()
        self._saludar_si_toca()

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
        self.selector_chat.selected = [motor]
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
        proximos_indicadores = anterior + 2
        proximos_paneles = anterior + SEGUNDOS_ENTRE_PANELES
        while True:
            ahora = time.monotonic()
            proximo_cuadro = max(proximo_cuadro + 1 / CUADROS_POR_SEGUNDO, ahora)
            if ahora >= proxima_revision:
                await self._revisar_boveda()
                proxima_revision = ahora + SEGUNDOS_ENTRE_REVISIONES_BOVEDA
            if ahora >= proximos_indicadores:
                proximos_indicadores = ahora + SEGUNDOS_ENTRE_INDICADORES
                asyncio.get_running_loop().run_in_executor(None, self._refrescar_indicadores)
            if ahora >= proximos_paneles:
                proximos_paneles = ahora + SEGUNDOS_ENTRE_PANELES
                asyncio.get_running_loop().run_in_executor(None, self._refrescar_paneles)
            self.grafo.escuchando = self.grabadora.grabando or (self.escucha.activa and self.ventana.abierta)
            self.grafo.avanzar(ahora - anterior, self.medidor.nivel)
            anterior = ahora
            if self._seccion == 0:
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

    def _refrescar_indicadores(self) -> None:
        """Chips de estado de arriba: modelos, núcleo y memoria. Chequeos baratos (sin audio)."""
        try:
            chequeos = {c.nombre: c for c in diagnostico.revisar_ollama()}
            chequeos["Gemini"] = diagnostico.revisar_gemini()
            chequeos["Núcleo"] = diagnostico.revisar_nucleo()
            chequeos["Índice"] = diagnostico.revisar_indice()
        except Exception:  # noqa: BLE001 - un indicador fallido no debe tumbar la UI
            return
        crimson = chequeos.get("Modelo de Crimson") or chequeos.get("Ollama")
        self.indicadores.controls = [
            estilo.indicador("Crimson", crimson.ok, crimson.detalle),
            estilo.indicador("Clover", chequeos["Gemini"].ok, chequeos["Gemini"].detalle),
            estilo.indicador("Núcleo", chequeos["Núcleo"].ok, chequeos["Núcleo"].detalle),
            estilo.indicador("Memoria", chequeos["Índice"].ok, chequeos["Índice"].detalle),
        ]
        self._actualizar(self.indicadores)

    def _refrescar_paneles(self) -> None:
        """Recalcula el panel Hoy y la sección visible (lee la bóveda; nunca en el hilo de la UI)."""
        try:
            self.panel_hoy.refrescar()
            self._actualizar(self.panel_hoy.control)
            vista = {2: self.vista_boveda, 3: self.vista_uso, 4: self.vista_ajustes}.get(self._seccion)
            if vista is not None:
                vista.refrescar()
                self._actualizar(vista.control)
        except (RuntimeError, OSError, ValueError) as error:
            print(f"[aviso] No se pudo actualizar un panel: {error}")

    def _actualizar(self, control: ft.Control) -> None:
        try:
            control.update()
        except (AssertionError, RuntimeError):
            pass  # el control todavía no está en la página (pasa al arrancar)

    # ---------- acciones desde la UI (pasan por el registro con permisos) ----------

    def _contexto_ui(self) -> ContextoEjecucion:
        return ContextoEjecucion(confirmador=self.confirmador_ui, canal="ui")

    def _completar_desde_ui(self, tarea: str) -> str:
        return REGISTRO.ejecutar("completar_pendiente", {"descripcion": tarea}, self._contexto_ui())

    def _conectar_desde_ui(self, origen: str, destino: str, motivo: str) -> str:
        return REGISTRO.ejecutar("conectar_notas", {"origen": origen, "destino": destino, "motivo": motivo}, self._contexto_ui())

    # ---------- eventos ----------

    def cambiar_apartado(self, e) -> None:
        self._mostrar_seccion(e.control.selected_index)

    def ir_a(self, nombre: str) -> None:
        """Abre una sección por nombre ("inicio", "chat", "boveda", "uso", "ajustes")."""
        nombres = [normalizar(n) for n, _icono in SECCIONES]
        if normalizar(nombre) in nombres:
            self.rail.selected_index = nombres.index(normalizar(nombre))
            self._mostrar_seccion(self.rail.selected_index)

    def _mostrar_seccion(self, indice_seccion: int) -> None:
        self._seccion = indice_seccion
        for i, vista in enumerate(self._vistas):
            vista.visible = i == self._seccion
        self.page.update()
        threading.Thread(target=self._refrescar_paneles, daemon=True).start()

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
        ajustes.guardar({"activar_por_nombre": bool(self.interruptor_nombre.value)})
        self._aplicar_activacion(bool(self.interruptor_nombre.value))

    def _activacion_desde_ajustes(self, activa: bool) -> None:
        self.interruptor_nombre.value = activa
        self._aplicar_activacion(activa)

    def _aplicar_activacion(self, activa: bool) -> None:
        if activa:
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
        """Confirmación por diálogo (para el chat y los botones de la UI)."""
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

    def _burbuja(self, nombre: str, texto: str, color: str, es_usuario: bool = False) -> tuple[ft.Control, ft.Text]:
        cuerpo = ft.Text(texto, selectable=True, size=14, color=estilo.TEXTO)
        burbuja = ft.Container(
            content=ft.Column([ft.Text(nombre, weight=ft.FontWeight.W_700, color=color, size=12), cuerpo], spacing=4),
            bgcolor=estilo.SUPERFICIE_ALTA if es_usuario else ft.Colors.with_opacity(0.10, color),
            border=None if es_usuario else ft.Border.only(left=ft.BorderSide(3, color)),
            border_radius=12,
            padding=12,
            width=560,
        )
        fila = ft.Row([burbuja], alignment=ft.MainAxisAlignment.END if es_usuario else ft.MainAxisAlignment.START)
        return fila, cuerpo

    def _agregar_al_historial(self, nombre: str, texto: str, color: str) -> ft.Text:
        if self._bienvenida in self.historial.controls:
            self.historial.controls.remove(self._bienvenida)
        fila, cuerpo = self._burbuja(nombre, texto, color, es_usuario=nombre == "Tú")
        self.historial.controls.append(fila)
        return cuerpo

    def _saludar_si_toca(self) -> None:
        """Una vez al día, al abrir: lo que tiene para hoy, con la voz del agente."""
        hoy = date.today().isoformat()
        if not ajustes.obtener("saludo_al_abrir") or estado.leer_valor(CLAVE_SALUDO) == hoy:
            return
        estado.guardar_valor(CLAVE_SALUDO, hoy)
        texto = saludo_del_dia(self.agente)
        with self._turno:
            paleta = self._paleta_actual()
            self.ultima_respuesta.value = f"{nombre_motor(self.agente)}: {texto}"
            self.ultima_respuesta.color = paleta.claro
            self._agregar_al_historial(nombre_motor(self.agente), texto, paleta.principal)
            self.grafo.empezar_a_hablar(self.agente)
            self._actualizar(self.page)
            self._texto_hablando = texto
            try:
                hablar(texto, motor=self.agente, medidor=self.medidor, detener=self._interrumpir)
            finally:
                self._texto_hablando = ""
                self.grafo.dejar_de_hablar()

    # --- voz ---

    def _es_su_propio_eco(self, texto: str) -> bool:
        """¿Lo detectado se parece demasiado a lo que el agente está diciendo en este instante?

        Sin cancelación de eco de hardware, el micrófono puede captar su
        propia voz por las bocinas. No hace falta el nombre para
        interrumpirlo, así que esta es la única defensa contra contestarse
        a sí mismo en bucle: si no está hablando (_texto_hablando vacío) o
        lo dicho no se parece a lo que dice, se asume que es real.
        """
        if not self._texto_hablando:
            return False
        oido = normalizar(texto)
        if not oido:
            return False
        dicho = normalizar(self._texto_hablando)
        # Cobertura del tramo contiguo más largo, no ratio(): lo oído suele ser solo una oración de
        # una respuesta más larga, y esa oración aparece como un fragmento seguido dentro de ella.
        bloque = difflib.SequenceMatcher(None, oido, dicho, autojunk=False).find_longest_match()
        cobertura = bloque.size / len(oido)
        return cobertura >= COBERTURA_MINIMA_ANTES_DE_IGNORAR

    def _al_escuchar_frase(self, audio) -> None:
        """Llega una frase de la escucha continua (incluso mientras el agente habla, para poder
        interrumpirlo diciendo lo que sea): ¿le hablaban al asistente o sigue abierta la ventana?"""
        if self.grabadora.grabando:
            return  # el micrófono manual ya se está encargando de esto
        texto = transcribir(audio, filtrar_ruido=True)
        if not texto:
            return
        if not self._turno.acquire(blocking=False):
            if self._es_su_propio_eco(texto):
                return  # probablemente se escuchó a sí mismo: se ignora para no contestarse en bucle
            self._interrumpir.set()  # hay un turno en curso: cortarlo y atender esto en su lugar
            self._turno.acquire()  # espera a que el turno interrumpido suelte el lock de verdad
        try:
            agente, mensaje = self.ventana.procesar(texto)
            if agente is None:
                return  # no le hablaban al asistente
            if agente != self.agente:
                self._seleccionar_agente(agente)
            if agente == MOTOR_OLLAMA:
                threading.Thread(target=precalentar, daemon=True).start()
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

        La respuesta se habla en vivo: cada oración suena en cuanto el modelo la termina. La
        escucha sigue activa mientras piensa y habla, así que se le puede interrumpir diciendo
        cualquier cosa (ver _al_escuchar_frase); por eso se lleva registro de _texto_hablando,
        para distinguir su propio eco de una interrupción real.
        """
        self.ocupado = True
        self._interrumpir.clear()
        self._texto_hablando = ""
        voz: VozEnVivo | None = None
        try:
            self.ultimo_usuario.value = f"Tú: {texto}"
            self.ultima_respuesta.value = ""
            self.estado_voz.value = "Pensando..."
            self._agregar_al_historial("Tú", texto, COLOR_USUARIO)
            self.page.update()

            def al_oracion(oracion: str) -> None:
                nonlocal voz
                if voz is None:
                    voz = VozEnVivo(MOTOR_OLLAMA, self.medidor, self._interrumpir)
                    self.grafo.empezar_a_hablar(MOTOR_OLLAMA)
                    self.estado_voz.value = f"{nombre_motor(MOTOR_OLLAMA)} está hablando..."
                self._texto_hablando = f"{self._texto_hablando} {oracion}".strip()
                self.ultima_respuesta.value = f"{nombre_motor(MOTOR_OLLAMA)}: {self._texto_hablando}"
                self.ultima_respuesta.color = PALETAS[MOTOR_OLLAMA].claro
                self._actualizar(self.page)
                voz.decir(oracion)

            respuesta = procesar_comando(
                texto,
                confirmador=self.confirmador_voz,
                motor_forzado=self._motor_forzado(),
                conversacion=self.conversacion,
                canal="voz",
                al_oracion=al_oracion,
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

            self._texto_hablando = respuesta.texto
            if voz is None:
                voz = VozEnVivo(motor_mostrado, self.medidor, self._interrumpir)
            if respuesta.por_decir:
                voz.decir(respuesta.por_decir)
            voz.terminar()
            voz.esperar()
            voz = None
            if respuesta.cerrar:
                self.page.run_task(self.page.window.close)
        finally:
            if voz is not None:
                voz.terminar()
            self._texto_hablando = ""
            self._terminar_turno_de_voz()
            threading.Thread(target=self._refrescar_paneles, daemon=True).start()

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
        texto = (self.campo_texto.value or "").strip()
        if not texto:
            return
        self.campo_texto.value = ""
        self._agregar_al_historial("Tú", texto, COLOR_USUARIO)
        self.estado_chat.value = f"{nombre_motor(self.agente)} está pensando..."
        self.page.update()
        threading.Thread(target=self._procesar_chat, args=(texto,), daemon=True).start()

    def _procesar_chat(self, texto: str) -> None:
        with self._turno:
            self.ocupado = True
            cuerpo: ft.Text | None = None
            try:
                def al_oracion(oracion: str) -> None:
                    nonlocal cuerpo
                    if cuerpo is None:
                        cuerpo = self._agregar_al_historial(nombre_motor(MOTOR_OLLAMA), "", PALETAS[MOTOR_OLLAMA].principal)
                    cuerpo.value = f"{cuerpo.value} {oracion}".strip()
                    self._actualizar(self.page)

                respuesta = procesar_comando(
                    texto,
                    confirmador=self.confirmador_ui,
                    motor_forzado=self._motor_forzado(),
                    conversacion=self.conversacion,
                    canal="chat",
                    al_oracion=al_oracion,
                )
                motor_mostrado = self._motor_mostrado(respuesta.motor)
                paleta = PALETAS.get(motor_mostrado, self._paleta_actual())
                if cuerpo is not None and motor_mostrado == MOTOR_OLLAMA:
                    cuerpo.value = respuesta.texto  # el texto final (ya corregido si hizo falta)
                else:
                    self._agregar_al_historial(nombre_motor(motor_mostrado), respuesta.texto, paleta.principal)
                if respuesta.cerrar:
                    self.page.run_task(self.page.window.close)
            finally:
                self.ocupado = False
                self.estado_chat.value = ""
                self.page.update()
                threading.Thread(target=self._refrescar_paneles, daemon=True).start()


def construir_app(page: ft.Page) -> None:
    JarvisApp(page).montar()
