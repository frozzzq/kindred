"""Evalúa a Crimson y Clover con los modelos reales sobre una bóveda de ejemplo desechable.

Cada escenario manda un mensaje y revisa: qué herramientas usó, qué dijo y qué cambió en la bóveda.
Imprime un reporte con aciertos y tiempos (hasta la primera oración y total). Nunca toca la bóveda
real: trabaja en %LOCALAPPDATA%\\kindred\\boveda-pruebas.

Uso: python -m src.pruebas.evaluar_agentes [crimson|clover|ambos] [--solo NOMBRE]
"""

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src.agente.conversacion import Conversacion
from src.consola import forzar_utf8
from src.obsidian import indice
from src.obsidian.estructura import asegurar_estructura_boveda
from src.obsidian.texto import normalizar
from src.pruebas.boveda_ejemplo import crear_boveda_de_pruebas
from src.router.intent_router import MOTOR_GEMINI, MOTOR_OLLAMA, nombre_motor


PAUSA_GEMINI = 12  # segundos entre escenarios de Clover: cada uno gasta 1 a 3 solicitudes


@dataclass
class Escenario:
    nombre: str
    mensaje: str
    usa: set[str] = field(default_factory=set)  # herramientas que debe llamar
    no_usa: set[str] = field(default_factory=set)
    dice_alguno: tuple[str, ...] = ()  # la respuesta debe mencionar al menos uno
    no_dice: tuple[str, ...] = ()
    verificar: Callable[[Path], str | None] | None = None  # devuelve un error o None
    max_caracteres: int | None = None
    previos: tuple[str, ...] = ()  # mensajes anteriores de la misma conversación


def _existe(ruta: str, contiene: str = "") -> Callable[[Path], str | None]:
    def verificar(boveda: Path) -> str | None:
        coincidencias = list(boveda.glob(ruta))
        if not coincidencias:
            return f"no existe {ruta}"
        if contiene and normalizar(contiene) not in normalizar(coincidencias[0].read_text(encoding="utf-8")):
            return f"{ruta} no contiene '{contiene}'"
        return None

    return verificar


def _no_contiene(ruta: str, texto: str) -> Callable[[Path], str | None]:
    def verificar(boveda: Path) -> str | None:
        contenido = (boveda / ruta).read_text(encoding="utf-8")
        return f"{ruta} todavía contiene '{texto}'" if normalizar(texto) in normalizar(contenido) else None

    return verificar


def _eventualmente(verificacion, segundos: float = 20) -> Callable[[Path], str | None]:
    """Para lo que se guarda en segundo plano (la red que extrae datos personales que el modelo no guardó)."""

    def verificar(boveda: Path) -> str | None:
        limite = time.monotonic() + segundos
        while (error := verificacion(boveda)) and time.monotonic() < limite:
            time.sleep(0.5)
        return error

    return verificar


def _todas(*verificaciones) -> Callable[[Path], str | None]:
    def verificar(boveda: Path) -> str | None:
        for v in verificaciones:
            error = v(boveda)
            if error:
                return error
        return None

    return verificar


ESCENARIOS = (
    Escenario("saludo", "hola, ¿cómo estás?", no_usa={"crear_nota", "agregar_pendiente"}, max_caracteres=280),
    Escenario("pendientes", "¿qué pendientes tengo?", dice_alguno=("leche", "mamá", "reporte", "proyecto"), max_caracteres=600),
    Escenario("vencidos", "¿tengo algo atrasado?", dice_alguno=("reporte", "bases de datos")),
    Escenario("nota directa", "¿qué dicen mis notas sobre el event loop de node?", dice_alguno=("hilo", "bloque", "callback", "promesa")),
    Escenario("paráfrasis", "¿cómo se llamaba el framework que apunté para hacer APIs?", dice_alguno=("express",)),
    Escenario("universidad", "según mis apuntes, ¿qué diferencia hay entre inner join y left join?", dice_alguno=("izquierda", "coinciden")),
    Escenario("perfil", "¿dónde vive mi novia?", dice_alguno=("mochis",)),
    Escenario("no inventar", "¿qué dice mi nota de física cuántica?", no_dice=("entrelazamiento", "superposición"), no_usa={"crear_nota"}),
    Escenario(
        "crear nota",
        "crea una nota sobre TypeScript: es un superconjunto de JavaScript que agrega tipos estáticos y se compila a JavaScript",
        usa={"crear_nota"},
        verificar=_existe("04-Conocimiento/**/TypeScript*.md", "tipos"),
    ),
    Escenario(
        "agregar a nota",
        "agrégale a mi nota de Node.js que el módulo fs sirve para leer y escribir archivos",
        usa={"agregar_a_nota"},
        verificar=_existe("04-Conocimiento/Programación/Node.js.md", "fs"),
    ),
    Escenario(
        "conectar",
        "conecta mi nota de Jarvis con la de Ollama",
        usa={"conectar_notas"},
        verificar=_existe("03-Proyectos/Jarvis.md", "[[Ollama]]"),
    ),
    Escenario(
        "completar",
        "ya llamé a mi mamá",
        usa={"completar_pendiente"},
        verificar=_no_contiene("02-Tareas/Pendientes.md", "Llamar a mi mamá"),
    ),
    Escenario(
        "reprogramar",
        "pásame lo del reporte de bases de datos para mañana a las 5pm",
        usa={"reprogramar_pendiente"},
        verificar=_existe("02-Tareas/Pendientes.md", "17:00"),
    ),
    Escenario(
        "agregar pendiente",
        "recuérdame comprar pilas el sábado a las 10am",
        usa={"agregar_pendiente"},
        verificar=_existe("02-Tareas/Pendientes.md", "pilas"),
    ),
    # Si el modelo no llama recordar_sobre_usuario, la red de seguridad lo guarda en segundo plano.
    Escenario("dato personal", "me encanta el sushi", verificar=_eventualmente(_existe("01-Perfil/Yo.md", "sushi"))),
)


@dataclass
class Resultado:
    escenario: Escenario
    exito: bool
    errores: list[str]
    texto: str
    herramientas: list[str]
    ms_total: int
    ms_primera_oracion: int | None


def _correr(escenario: Escenario, motor: str, boveda: Path) -> Resultado:
    from src.main import procesar_comando

    conversacion = Conversacion()
    for previo in escenario.previos:
        procesar_comando(previo, confirmador=lambda _p: True, motor_forzado=motor, conversacion=conversacion)

    usadas: list[str] = []
    from src.herramientas.catalogo import REGISTRO

    ejecutar_original = REGISTRO.ejecutar

    def espiar(nombre, argumentos, contexto):
        usadas.append(nombre)
        return ejecutar_original(nombre, argumentos, contexto)

    REGISTRO.ejecutar = espiar
    primera: list[float] = []
    inicio = time.perf_counter()
    try:
        respuesta = procesar_comando(
            escenario.mensaje,
            confirmador=lambda _p: True,
            motor_forzado=motor,
            conversacion=conversacion,
            canal="prueba",
            al_oracion=lambda _o: primera.append(time.perf_counter()) if not primera else None,
        )
    finally:
        REGISTRO.ejecutar = ejecutar_original
    total = int((time.perf_counter() - inicio) * 1000)

    errores = []
    texto = normalizar(respuesta.texto)
    if faltan := escenario.usa - set(usadas):
        errores.append(f"no usó {', '.join(sorted(faltan))}")
    if sobran := escenario.no_usa & set(usadas):
        errores.append(f"usó {', '.join(sorted(sobran))}")
    if escenario.dice_alguno and not any(normalizar(p) in texto for p in escenario.dice_alguno):
        errores.append(f"no mencionó {' / '.join(escenario.dice_alguno)}")
    for prohibido in escenario.no_dice:
        if normalizar(prohibido) in texto:
            errores.append(f"dijo '{prohibido}'")
    if escenario.max_caracteres and len(respuesta.texto) > escenario.max_caracteres:
        errores.append(f"respuesta larga ({len(respuesta.texto)} caracteres)")
    if escenario.verificar:
        error = escenario.verificar(boveda)
        if error:
            errores.append(error)
    return Resultado(
        escenario, not errores, errores, respuesta.texto, usadas, total,
        int((primera[0] - inicio) * 1000) if primera else None,
    )


def evaluar(motores: list[str], solo: str | None = None) -> list[tuple[str, Resultado]]:
    resultados = []
    for motor in motores:
        boveda = crear_boveda_de_pruebas()
        os.environ["OBSIDIAN_VAULT_PATH"] = str(boveda)
        asegurar_estructura_boveda()
        print(f"\n=== {nombre_motor(motor)} · indexando la bóveda de pruebas...", flush=True)
        indice.actualizar()
        if motor == MOTOR_OLLAMA:
            from src.main import precalentar

            precalentar()
        for escenario in ESCENARIOS:
            if solo and solo.lower() not in escenario.nombre.lower():
                continue
            if motor == MOTOR_GEMINI and resultados:
                time.sleep(PAUSA_GEMINI)  # el plan gratis de Gemini permite 15 solicitudes por minuto
            resultado = _correr(escenario, motor, boveda)
            marca = "✓" if resultado.exito else "✗"
            primera = f"{resultado.ms_primera_oracion / 1000:.1f}s" if resultado.ms_primera_oracion else "  —  "
            print(
                f"{marca} {escenario.nombre:18s} {resultado.ms_total / 1000:5.1f}s (1ª oración {primera}) "
                f"[{', '.join(resultado.herramientas) or 'sin herramientas'}]",
                flush=True,
            )
            print(f"    → {resultado.texto[:220]}")
            for error in resultado.errores:
                print(f"    ! {error}")
            resultados.append((motor, resultado))
    return resultados


def main() -> None:
    forzar_utf8()
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
    # Todo lo de la evaluación (bóveda, índice, métricas, cursores) en su propia carpeta: sus turnos
    # de prueba no deben aparecer en el panel de Uso ni tocar el estado real.
    os.environ["LOCALAPPDATA"] = str(Path(os.getenv("LOCALAPPDATA", Path.home())) / "kindred" / "evaluacion")
    argumentos = sys.argv[1:]
    solo = None
    if "--solo" in argumentos:
        solo = argumentos[argumentos.index("--solo") + 1]
    quien = next((a for a in argumentos if a in ("crimson", "clover", "ambos")), "ambos")
    motores = {"crimson": [MOTOR_OLLAMA], "clover": [MOTOR_GEMINI], "ambos": [MOTOR_OLLAMA, MOTOR_GEMINI]}[quien]
    resultados = evaluar(motores, solo)
    print()
    for motor in motores:
        propios = [r for m, r in resultados if m == motor]
        if not propios:
            continue
        bien = sum(r.exito for r in propios)
        promedio = sum(r.ms_total for r in propios) / len(propios) / 1000
        primeras = [r.ms_primera_oracion for r in propios if r.ms_primera_oracion]
        texto_primera = f", 1ª oración en {sum(primeras) / len(primeras) / 1000:.1f}s" if primeras else ""
        print(f"{nombre_motor(motor)}: {bien}/{len(propios)} escenarios bien · promedio {promedio:.1f}s{texto_primera}")


if __name__ == "__main__":
    main()
