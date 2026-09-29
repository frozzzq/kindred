"""Punto de entrada CLI: recibe texto, decide motor o acción directa, y
responde con la personalidad del agente, su memoria de la conversación y
herramientas (bóveda de Obsidian y acciones en la PC) con permisos.
"""

import re
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.actions.aplicaciones import reconoce_aplicacion
from src.actions.archivos import es_carpeta_conocida
from src.actions.busqueda_web import construir_contexto_web
from src.actions.confirmacion import Confirmador, confirmar_por_texto
from src.actions.navegador import parece_url
from src.agente.contexto_turno import mensaje_con_contexto
from src.agente.conversacion import Conversacion
from src.agente.metricas import registrar_turno
from src.agente.oraciones import Oracionador
from src.agente.personalidad import construir_prompt_sistema, es_muletilla, quitar_muletilla_final
from src.agente.reflexion import aprender_si_quedo_sin_guardar
from src.engines.gemini_client import conversar_gemini, describir_error, preguntar_gemini
from src.engines.modelos import RespuestaMotor
from src.engines.ollama_client import conversar_ollama
from src.engines.ollama_client import precalentar as precalentar_ollama
from src.herramientas.catalogo import REGISTRO, seleccionar_grupos
from src.herramientas.registro import ContextoEjecucion
from src.obsidian.contexto import evaluar_guardado
from src.obsidian.herramientas import (
    MENSAJE_VERIFICACION,
    MENSAJE_VERIFICACION_PENDIENTE,
    MENSAJE_VERIFICACION_SISTEMA,
    afirma_accion_sin_hacerla,
    afirma_cambio_sin_hacerlo,
    niega_accion_hecha,
    resumen_de_acciones,
    usuario_reporta_tarea_hecha,
)
from src.obsidian.texto import normalizar
from src.obsidian.vault_writer import registrar_interaccion
from src.router.intent_router import (
    MOTOR_ACCION,
    MOTOR_GEMINI,
    MOTOR_GEMINI_FALLO,
    MOTOR_OLLAMA,
    cambio_de_modo_seguro,
    decidir_motor,
    es_busqueda_web,
    es_cierre,
    extraer_nombre_app,
    extraer_texto_a_escribir,
    extraer_texto_click,
    nombre_motor,
    parece_varias_instrucciones,
)

PREFIJO_CARPETA = "carpeta "
# "escribe una nota sobre X" / "escribe en mi bóveda..." es para la bóveda, no para teclear en la ventana activa.
_ES_PARA_LA_BOVEDA = re.compile(r"^(una |un |la |el )?(nota|apunte|resumen)\b|\b(b[oó]veda|obsidian)\b", re.IGNORECASE)

AlOracion = Callable[[str], None]

# Lo que dice Crimson mientras trabaja con una herramienta, para que en voz no haya un silencio de
# varios segundos (generar una nota completa a ~16 tokens/s tarda). Una sola vez por turno.
_RELLENO_LECTURA = ("A ver, déjame revisar.", "Mmm, déjame ver.", "Dame un segundo, lo busco.")
_RELLENO_ESCRITURA = ("Va, dame un segundito.", "Sale, ahorita.", "Va, déjame hacerlo.")
_HERRAMIENTAS_DE_LECTURA = {"leer_nota", "buscar_en_boveda", "listar_notas", "sugerir_conexiones"}
# Una orden de hacer algo ("crea una nota...", "agrega...", "conecta..."): el modelo tarda en escribir la
# llamada con su contenido (~18 s para una nota, medido), así que se contesta de inmediato "Va, dame un
# segundito" en vez de dejar ese silencio. Solo si el mensaje EMPIEZA con la orden.
_PIDE_ACCION = re.compile(
    r"^\s*(oye,?\s+|porfa,?\s+|por favor,?\s+)?(crea|creame|anota|apunta|agrega|agregale|anade|guarda|conecta|enlaza"
    r"|mueve|borra|elimina|edita|actualiza|reprograma|recuerdame|pasa|cambia|organiza|renombra)\b"
)


def _corregir_respuesta_ollama(
    texto: str, mensajes: list[dict], herramientas: list[dict], ejecutar, respuesta: RespuestaMotor
) -> RespuestaMotor:
    """Corrige dos formas conocidas en las que Crimson no dice la verdad sobre lo que hizo (ver
    src/obsidian/herramientas.py): afirmar un cambio/acción que no hizo, o negar uno que sí hizo.
    """
    if not respuesta.exito:
        return respuesta

    usadas = respuesta.herramientas_usadas or []
    if niega_accion_hecha(respuesta.texto, usadas):
        # Ya se hizo de verdad (herramientas_usadas lo prueba): reintentar con el modelo podría
        # repetir la acción (ej. abrir la misma app otra vez). Mejor corregirlo con lo que la
        # herramienta ya confirmó, sin volver a preguntarle.
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
        return respuesta

    mensaje_verificacion = None
    if afirma_cambio_sin_hacerlo(respuesta.texto, usadas):
        mensaje_verificacion = MENSAJE_VERIFICACION
    elif afirma_accion_sin_hacerla(respuesta.texto, usadas):
        mensaje_verificacion = MENSAJE_VERIFICACION_SISTEMA
    elif usuario_reporta_tarea_hecha(texto) and "completar_pendiente" not in usadas:
        # El usuario contó que ya hizo algo, pero el modelo solo charló sin revisar si era un
        # pendiente (no afirmó ningún cambio, así que afirma_cambio_sin_hacerlo no lo detecta).
        mensaje_verificacion = MENSAJE_VERIFICACION_PENDIENTE
    if not mensaje_verificacion:
        return respuesta

    llamadas_previas = respuesta.llamadas_modelo
    mensajes = mensajes + [
        {"role": "assistant", "content": respuesta.texto},
        {"role": "user", "content": mensaje_verificacion},
    ]
    respuesta = conversar_ollama(mensajes, herramientas=herramientas, ejecutar=ejecutar)
    respuesta.herramientas_usadas = usadas + (respuesta.herramientas_usadas or [])
    respuesta.llamadas_modelo += llamadas_previas
    if not respuesta.exito:
        return respuesta

    usadas = respuesta.herramientas_usadas
    if niega_accion_hecha(respuesta.texto, usadas):
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
    elif afirma_cambio_sin_hacerlo(respuesta.texto, usadas) or afirma_accion_sin_hacerla(respuesta.texto, usadas):
        # Mejor admitirlo que decirle al usuario que algo quedó hecho cuando no.
        respuesta.texto = "No logré hacer eso. ¿Me lo repites, por favor?"
    return respuesta


def _corregir_respuesta_gemini(
    prompt: str, herramientas: list[dict], ejecutar, instruccion: str, respuesta: RespuestaMotor
) -> RespuestaMotor:
    """La misma red de honestidad que Crimson, para Clover.

    Hacía falta: en la evaluación, Clover respondió "Hecho. Ya vinculé la nota de Jarvis con la de
    Ollama" sin haber llamado conectar_notas. No se revisa "el usuario reporta una tarea hecha" como
    en Crimson: costaría otra solicitud de Gemini (cuota de 15 por minuto) casi siempre en vano.
    """
    if not respuesta.exito:
        return respuesta
    usadas = respuesta.herramientas_usadas or []
    if niega_accion_hecha(respuesta.texto, usadas):
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
        return respuesta
    if afirma_cambio_sin_hacerlo(respuesta.texto, usadas):
        verificacion = MENSAJE_VERIFICACION
    elif afirma_accion_sin_hacerla(respuesta.texto, usadas):
        verificacion = MENSAJE_VERIFICACION_SISTEMA
    else:
        return respuesta

    llamadas_previas = respuesta.llamadas_modelo
    reintento = f'{prompt}\n\nTu respuesta anterior fue: "{respuesta.texto}"\n\n{verificacion}'
    respuesta = conversar_gemini(reintento, herramientas=herramientas, ejecutar=ejecutar, instruccion_sistema=instruccion)
    respuesta.herramientas_usadas = usadas + (respuesta.herramientas_usadas or [])
    respuesta.llamadas_modelo += llamadas_previas
    if not respuesta.exito:
        return respuesta
    usadas = respuesta.herramientas_usadas
    if niega_accion_hecha(respuesta.texto, usadas):
        respuesta.texto = resumen_de_acciones(usadas, respuesta.resultados_herramientas)
    elif afirma_cambio_sin_hacerlo(respuesta.texto, usadas) or afirma_accion_sin_hacerla(respuesta.texto, usadas):
        respuesta.texto = "No logré hacer eso. ¿Me lo repites, por favor?"
    return respuesta


@dataclass
class Respuesta:
    """Respuesta del asistente junto con el motor que realmente la generó.

    El motor real puede diferir del elegido por el router si hubo fallback
    (ej. el router eligió Gemini pero falló y respondió Ollama). Se necesita
    saber cuál respondió de verdad para, por ejemplo, elegir la voz correcta.

    cerrar=True indica que el usuario pidió cerrar la aplicación (y lo
    confirmó): quien llame a procesar_comando debe terminar el programa (o
    cerrar la ventana) después de mostrar/decir esta respuesta.

    por_decir es lo que falta decir en voz alta: si la respuesta se fue hablando en vivo
    (al_oracion), solo lo que no se alcanzó a entregar; si no, el texto completo.
    """

    texto: str
    motor: str
    cerrar: bool = False
    por_decir: str | None = None

    def __post_init__(self) -> None:
        if self.por_decir is None:
            self.por_decir = self.texto


def _compacto(texto: str) -> str:
    return " ".join(texto.split())


class _VozHonesta:
    """Entrega oraciones a medida que llegan, pero retiene las que afirman o niegan un cambio sin
    respaldo de una herramienta: esas pasan por la corrección de _corregir_respuesta_ollama antes
    de decirse. Una vez que retiene una, retiene todo lo que sigue (para no decir cosas sueltas)."""

    def __init__(self, al_oracion: AlOracion) -> None:
        self._al_oracion = al_oracion
        self._usadas: list[str] = []
        self._retenida = False
        self._relleno_dicho = False
        self.dicho: list[str] = []
        self._oracionador = Oracionador(self._decidir)

    def relleno(self, herramienta: str) -> None:
        """Una frase corta mientras trabaja ("A ver, déjame revisar."); no cuenta como parte de la respuesta."""
        if self._relleno_dicho or self.dicho:
            return
        self._relleno_dicho = True
        opciones = _RELLENO_LECTURA if herramienta in _HERRAMIENTAS_DE_LECTURA else _RELLENO_ESCRITURA
        self._al_oracion(opciones[len(herramienta) % len(opciones)])

    def fragmento(self, texto: str, usadas: list[str]) -> None:
        self._usadas = usadas
        self._oracionador.agregar(texto)

    def terminar(self) -> None:
        self._oracionador.terminar()

    def _decidir(self, oracion: str) -> None:
        if self._retenida or es_muletilla(oracion):
            return
        usadas = list(self._usadas)
        if (
            afirma_cambio_sin_hacerlo(oracion, usadas)
            or afirma_accion_sin_hacerla(oracion, usadas)
            or niega_accion_hecha(oracion, usadas)
        ):
            self._retenida = True
            return
        self.dicho.append(oracion)
        self._al_oracion(oracion)

    def por_decir(self, texto_final: str) -> str:
        """Lo que falta decir del texto final. Si no coincide con lo ya dicho (fue corregido), todo."""
        final = _compacto(texto_final)
        if not self.dicho:
            return final
        dicho = _compacto(quitar_muletilla_final(" ".join(self.dicho)))
        if final.startswith(dicho):
            return final[len(dicho):].strip()
        if dicho.startswith(final):
            return ""
        return final


def _responder(
    texto: str,
    respuesta: str,
    motor: str,
    conversacion: Conversacion,
    herramientas_usadas: list[str] | None = None,
    cerrar: bool = False,
    por_decir: str | None = None,
) -> Respuesta:
    respuesta = quitar_muletilla_final(respuesta)
    if por_decir is not None:
        por_decir = quitar_muletilla_final(por_decir) if por_decir else ""
    evaluar_guardado(texto, respuesta, motor)
    if motor != MOTOR_ACCION:
        aprender_si_quedo_sin_guardar(texto, herramientas_usadas or [])
    conversacion.agregar_turno(texto, respuesta)
    return Respuesta(texto=respuesta, motor=motor, cerrar=cerrar, por_decir=por_decir)


def _medido(canal: str, inicio: float, respuesta: Respuesta, motor_respuesta: RespuestaMotor | None = None) -> Respuesta:
    registrar_turno(
        agente=respuesta.motor,
        canal=canal,
        milisegundos=int((time.perf_counter() - inicio) * 1000),
        herramientas=(motor_respuesta.herramientas_usadas if motor_respuesta else []) or [],
        llamadas_modelo=motor_respuesta.llamadas_modelo if motor_respuesta else 0,
        exito=not respuesta.texto.startswith("[error]"),
    )
    return respuesta


def procesar_comando(
    texto: str,
    confirmador: Confirmador = confirmar_por_texto,
    motor_forzado: str | None = None,
    conversacion: Conversacion | None = None,
    canal: str = "texto",
    al_oracion: AlOracion | None = None,
) -> Respuesta:
    """Decide qué hacer con el texto: acción directa, o que un agente responda con herramientas.

    motor_forzado (MOTOR_OLLAMA/MOTOR_GEMINI) salta el router, para cuando el
    usuario elige el agente a mano; None deja que el router decida. Los
    atajos (abrir, escribir, click) se detectan igual en cualquier caso.
    conversacion guarda los turnos previos; sin ella, cada mensaje es independiente.
    canal ("texto", "voz", "chat"...) queda en el registro de acciones.
    al_oracion recibe la respuesta oración por oración mientras se genera (para hablarla en vivo).
    Toda acción, venga de un atajo o de un agente, pasa por REGISTRO.ejecutar
    (modo seguro, confirmación de lo irreversible y auditoría).
    """
    inicio = time.perf_counter()
    conversacion = conversacion or Conversacion()
    contexto = ContextoEjecucion(confirmador=confirmador, canal=canal)

    def accion(nombre: str, argumentos: dict) -> Respuesta:
        respuesta = _responder(texto, REGISTRO.ejecutar(nombre, argumentos, contexto), MOTOR_ACCION, conversacion)
        return _medido(canal, inicio, respuesta)

    modo_seguro = cambio_de_modo_seguro(texto)
    if modo_seguro is not None:
        REGISTRO.modo_seguro = modo_seguro
        mensaje = (
            "Modo seguro activado: solo consultaré, no haré acciones hasta que digas \"sal del modo seguro\"."
            if modo_seguro
            else "Modo seguro desactivado: puedo volver a hacer acciones."
        )
        return _responder(texto, mensaje, MOTOR_ACCION, conversacion)

    if es_cierre(texto):
        if confirmador("¿Confirmas que quieres que cierre la aplicación?"):
            return _responder(texto, "De acuerdo, hasta luego.", MOTOR_ACCION, conversacion, cerrar=True)
        return _responder(texto, "Cancelado, sigo aquí.", MOTOR_ACCION, conversacion)

    # Atajo solo para instrucciones simples ("abre spotify"); "abre spotify y pon mi playlist" o
    # "abre mis pendientes" (no es una app) los resuelve el agente con sus herramientas.
    objetivo = extraer_nombre_app(texto)
    if objetivo and not parece_varias_instrucciones(objetivo):
        if objetivo.startswith(PREFIJO_CARPETA):
            return accion("abrir_carpeta", {"nombre": objetivo[len(PREFIJO_CARPETA):]})
        if parece_url(objetivo):
            return accion("abrir_url", {"url": objetivo})
        # Antes de intentar como app: "mis documentos" o "el escritorio" se confundían con apps de
        # nombre parecido ("Documentación de Referencia", "Conexión a Escritorio remoto").
        if es_carpeta_conocida(objetivo):
            return accion("abrir_carpeta", {"nombre": objetivo})
        if reconoce_aplicacion(objetivo):
            return accion("abrir_aplicacion", {"nombre": objetivo})

    # Guardado igual que arriba: "escribe hola mundo" es dictado literal, pero "escribe un correo
    # para mi jefe pidiendo permiso" o "escribe una nota sobre X" no son algo para teclear tal cual
    # en la ventana activa; eso lo resuelve el agente.
    texto_a_escribir = extraer_texto_a_escribir(texto)
    if (
        texto_a_escribir is not None
        and not parece_varias_instrucciones(texto_a_escribir)
        and not _ES_PARA_LA_BOVEDA.search(texto_a_escribir)
    ):
        return accion("escribir_texto", {"texto": texto_a_escribir})

    texto_click = extraer_texto_click(texto)
    if texto_click is not None:
        return accion("hacer_click", {"texto": texto_click})

    motor = motor_forzado or decidir_motor(texto)
    mensaje_usuario = mensaje_con_contexto(texto, conversacion)

    if motor == MOTOR_GEMINI:
        # Clover recibe su personalidad y perfil en el prompt de sistema, y el historial como texto.
        historial = conversacion.como_transcripcion()
        prompt = f"Conversación reciente:\n{historial}\n\n{mensaje_usuario}" if historial else mensaje_usuario
        if es_busqueda_web(texto):
            # El grounding con Google Search va sin herramientas propias.
            respuesta = preguntar_gemini(
                prompt,
                usar_busqueda_web=True,
                instruccion_sistema=construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=False),
            )
        else:
            herramientas_gemini = REGISTRO.declaraciones_gemini(seleccionar_grupos(texto))
            instruccion = construir_prompt_sistema(MOTOR_GEMINI, con_herramientas=True)
            respuesta = conversar_gemini(
                prompt, herramientas=herramientas_gemini, ejecutar=REGISTRO.ejecutor(contexto), instruccion_sistema=instruccion
            )
            respuesta = _corregir_respuesta_gemini(prompt, herramientas_gemini, REGISTRO.ejecutor(contexto), instruccion, respuesta)
        if respuesta.exito:
            final = _responder(texto, respuesta.texto, MOTOR_GEMINI, conversacion, respuesta.herramientas_usadas)
            return _medido(canal, inicio, final, respuesta)
        if respuesta.herramientas_usadas:
            # Ya hizo acciones antes de fallar: pasarle el mensaje a Ollama podría repetirlas. Se
            # cuenta lo que sí se hizo (según las herramientas), sin leerle al usuario el error crudo.
            hecho = resumen_de_acciones(respuesta.herramientas_usadas, respuesta.resultados_herramientas)
            final = _responder(
                texto,
                f"{hecho} No alcancé a terminar todo: {describir_error(respuesta.error)}.",
                MOTOR_GEMINI,
                conversacion,
                respuesta.herramientas_usadas,
            )
            return _medido(canal, inicio, final, respuesta)
        print(f"[aviso] Clover no respondió ({describir_error(respuesta.error)}); contesta Crimson.")
        try:
            registrar_interaccion(texto, f"[fallo] {respuesta.error}", MOTOR_GEMINI_FALLO)
        except RuntimeError:
            pass  # sin bóveda configurada: no bloquea el flujo, solo no queda métrica de este fallo

    if es_busqueda_web(texto):
        # Ollama no tiene acceso a internet nativo (a diferencia de Gemini,
        # que usa su propio grounding); le damos resultados reales como
        # contexto auxiliar, típico cuando Gemini falló y cayó aquí.
        contexto_web = construir_contexto_web(texto)
        if contexto_web:
            mensaje_usuario = f"{mensaje_usuario}\n\n{contexto_web}"

    mensajes = [
        {"role": "system", "content": construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)},
        *conversacion.mensajes(),
        {"role": "user", "content": mensaje_usuario},
    ]
    herramientas = REGISTRO.esquemas_ollama(seleccionar_grupos(texto, modelo_local=True))
    ejecutar = REGISTRO.ejecutor(contexto)
    # Si el usuario cuenta que ya hizo algo, es probable que haya que corregir la respuesta
    # (completar el pendiente): mejor no empezar a hablarla antes de saberlo.
    voz = _VozHonesta(al_oracion) if al_oracion is not None and not usuario_reporta_tarea_hecha(texto) else None
    if voz is not None and _PIDE_ACCION.search(normalizar(texto)):
        voz.relleno("crear_nota")
    respuesta = conversar_ollama(
        mensajes,
        herramientas=herramientas,
        ejecutar=ejecutar,
        al_texto=voz.fragmento if voz else None,
        al_usar_herramienta=voz.relleno if voz else None,
    )
    if voz is not None:
        voz.terminar()
    respuesta = _corregir_respuesta_ollama(texto, mensajes, herramientas, ejecutar, respuesta)
    if respuesta.exito:
        por_decir = voz.por_decir(quitar_muletilla_final(respuesta.texto)) if voz else None
        final = _responder(
            texto, respuesta.texto, MOTOR_OLLAMA, conversacion, respuesta.herramientas_usadas, por_decir=por_decir
        )
        return _medido(canal, inicio, final, respuesta)
    final = Respuesta(texto=f"[error] Ollama también falló: {respuesta.error}", motor=MOTOR_OLLAMA)
    return _medido(canal, inicio, final, respuesta)


def precalentar() -> bool:
    """Deja a Crimson listo: modelo cargado y su prompt de sistema ya procesado (en caché de Ollama).

    Llamarlo en segundo plano al abrir la app o en cuanto el usuario empieza a hablar.
    """
    mensajes = [
        {"role": "system", "content": construir_prompt_sistema(MOTOR_OLLAMA, con_herramientas=True)},
        {"role": "user", "content": "hola"},
    ]
    return precalentar_ollama(mensajes, REGISTRO.esquemas_ollama(seleccionar_grupos("", modelo_local=True)))


def main() -> None:
    from src.arranque import preparar  # import local: arranque carga el .env, no hace falta al importar main

    preparar(sys.argv[1:])
    threading.Thread(target=precalentar, daemon=True).start()
    conversacion = Conversacion()
    print("Crimson y Clover (CLI de texto). Escribe 'salir' para terminar.")
    while True:
        try:
            texto = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue
        if texto.lower() in {"salir", "exit", "quit"}:
            break
        respuesta = procesar_comando(texto, conversacion=conversacion)
        print(f"{nombre_motor(respuesta.motor)}: {respuesta.texto}")
        if respuesta.cerrar:
            break


if __name__ == "__main__":
    main()
