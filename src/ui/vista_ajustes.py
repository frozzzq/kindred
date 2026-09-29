"""Vista "Ajustes": voces, comportamiento, núcleo, modo seguro y diagnóstico.

Lo que se cambia aquí se guarda en %LOCALAPPDATA%\\kindred\\ajustes.json (src/ajustes.py) y aplica
de inmediato: la próxima respuesta ya usa la voz nueva.
"""

import threading
from collections.abc import Callable

import flet as ft

from src import ajustes, diagnostico
from src.herramientas.catalogo import REGISTRO
from src.nucleo import autoarranque, proceso
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor
from src.ui import estilo
from src.ui.paletas import PALETAS
from src.voice.tts import probar_voz

FRASE_DE_PRUEBA = {
    MOTOR_OLLAMA: "¡Hola! Soy Crimson. ¿Te leo tus pendientes de hoy?",
    MOTOR_GEMINI: "Buenas. Soy Clover. Todo en orden por aquí.",
}


class VistaAjustes:
    def __init__(self, al_cambiar_activacion: Callable[[bool], None], confirmar: Callable[[str], bool]) -> None:
        self._al_cambiar_activacion = al_cambiar_activacion
        self._confirmar = confirmar
        self._estado_nucleo = estilo.texto("", 13, estilo.TEXTO_SUAVE)
        self._diagnostico = ft.Column(spacing=6)
        self._modo_seguro = ft.Switch(label="Modo seguro (solo consultar, sin acciones)", value=REGISTRO.modo_seguro, on_change=self._cambiar_modo_seguro)
        self.control = ft.Column(
            [
                estilo.texto("Ajustes", 22, peso=ft.FontWeight.W_700),
                estilo.tarjeta(ft.Column([estilo.titulo_seccion("Voces"), self._fila_voz(MOTOR_OLLAMA), ft.Divider(color=estilo.BORDE), self._fila_voz(MOTOR_GEMINI)], spacing=10)),
                estilo.tarjeta(
                    ft.Column(
                        [
                            estilo.titulo_seccion("Comportamiento"),
                            self._interruptor("Escuchar siempre: activar diciendo \"Crimson\" o \"Clover\"", "activar_por_nombre", self._al_cambiar_activacion),
                            self._interruptor("Saludarme al abrir (una vez al día, con lo que tengo pendiente)", "saludo_al_abrir"),
                            self._interruptor("Iniciar el núcleo de recordatorios al abrir la app", "iniciar_nucleo"),
                            self._modo_seguro,
                        ],
                        spacing=4,
                    )
                ),
                estilo.tarjeta(
                    ft.Column(
                        [
                            estilo.titulo_seccion("Núcleo (recordatorios, briefing, diario y orden de la bóveda)"),
                            self._estado_nucleo,
                            ft.Row(
                                [
                                    estilo.boton("Iniciar", self._iniciar_nucleo, ft.Icons.PLAY_ARROW_ROUNDED, principal=True),
                                    estilo.boton("Detener", self._detener_nucleo, ft.Icons.STOP_ROUNDED),
                                    estilo.boton("Arrancar con Windows", self._autoarranque, ft.Icons.ROCKET_LAUNCH_OUTLINED),
                                ],
                                spacing=8,
                                wrap=True,
                            ),
                        ],
                        spacing=10,
                    )
                ),
                estilo.tarjeta(
                    ft.Column(
                        [
                            ft.Row(
                                [estilo.titulo_seccion("Diagnóstico"), estilo.boton("Revisar todo", self._revisar, ft.Icons.SCIENCE_OUTLINED)],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            self._diagnostico,
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

    # ---------- construcción ----------

    def _fila_voz(self, motor: str) -> ft.Control:
        sufijo = "ollama" if motor == MOTOR_OLLAMA else "gemini"
        voz_actual = ajustes.voz_de(motor)
        opciones = [ft.DropdownOption(key=voz, text=nombre) for voz, (nombre, _genero) in ajustes.VOCES.items()]
        if voz_actual not in ajustes.VOCES:
            opciones.insert(0, ft.DropdownOption(key=voz_actual, text=voz_actual))
        selector = ft.Dropdown(
            value=voz_actual,
            options=opciones,
            width=340,
            on_select=lambda e: ajustes.guardar({f"voz_{sufijo}": e.control.value}),
        )
        velocidad = ft.Slider(
            value=ajustes.velocidad_de(motor),
            min=-15,
            max=25,
            divisions=8,
            label="{value}%",
            active_color=PALETAS[motor].principal,
            on_change_end=lambda e: ajustes.guardar({f"velocidad_{sufijo}": int(e.control.value)}),
            expand=True,
        )

        def probar(_e):
            threading.Thread(
                target=probar_voz, args=(selector.value, FRASE_DE_PRUEBA[motor], int(velocidad.value)), daemon=True
            ).start()

        return ft.Column(
            [
                ft.Row([estilo.punto(PALETAS[motor].principal, 10), estilo.texto(nombre_motor(motor), 15, peso=ft.FontWeight.W_600)], spacing=8),
                ft.Row(
                    [selector, ft.IconButton(icon=ft.Icons.VOLUME_UP_ROUNDED, tooltip="Escuchar", on_click=probar)],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([estilo.texto("Velocidad", 12, estilo.TEXTO_SUAVE), velocidad], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            spacing=6,
        )

    def _interruptor(self, etiqueta: str, clave: str, al_cambiar: Callable[[bool], None] | None = None) -> ft.Switch:
        def cambiar(e):
            ajustes.guardar({clave: bool(e.control.value)})
            if al_cambiar:
                al_cambiar(bool(e.control.value))

        return ft.Switch(label=etiqueta, value=bool(ajustes.obtener(clave)), on_change=cambiar)

    # ---------- datos ----------

    def refrescar(self) -> None:
        if proceso.esta_vivo():
            self._estado_nucleo.value = f"Corriendo · última vuelta hace {int(proceso.segundos_desde_ultima_vuelta() or 0)} s"
            self._estado_nucleo.color = estilo.BIEN
        else:
            self._estado_nucleo.value = "Detenido: no llegarán recordatorios ni el briefing."
            self._estado_nucleo.color = estilo.AVISO
        self._modo_seguro.value = REGISTRO.modo_seguro

    # ---------- eventos ----------

    def _cambiar_modo_seguro(self, e) -> None:
        REGISTRO.modo_seguro = bool(e.control.value)

    def _accion_nucleo(self, accion: Callable[[], str]) -> None:
        self._estado_nucleo.value = accion()
        self._estado_nucleo.update()

    def _iniciar_nucleo(self, _e) -> None:
        self._accion_nucleo(proceso.iniciar)

    def _detener_nucleo(self, _e) -> None:
        self._accion_nucleo(proceso.detener)

    def _autoarranque(self, _e) -> None:
        def trabajo():
            if self._confirmar("¿Registro el núcleo para que arranque solo cada vez que inicies sesión en Windows?"):
                self._accion_nucleo(autoarranque.registrar_tarea_programada)

        threading.Thread(target=trabajo, daemon=True).start()

    def _revisar(self, _e) -> None:
        self._diagnostico.controls = [ft.ProgressRing(width=18, height=18, stroke_width=2)]
        self._diagnostico.update()

        def trabajo():
            filas = []
            for chequeo in diagnostico.todos(con_audio=True):
                filas.append(
                    ft.Row(
                        [
                            estilo.punto(estilo.color_estado(chequeo.ok)),
                            estilo.texto(chequeo.nombre, 13, peso=ft.FontWeight.W_600, width=190),
                            ft.Column(
                                [estilo.texto(chequeo.detalle, 12, estilo.TEXTO_SUAVE)]
                                + ([estilo.texto(f"→ {chequeo.solucion}", 11, estilo.AVISO)] if chequeo.solucion and chequeo.ok is not True else []),
                                spacing=0,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                )
            self._diagnostico.controls = filas
            self._diagnostico.update()

        threading.Thread(target=trabajo, daemon=True).start()
