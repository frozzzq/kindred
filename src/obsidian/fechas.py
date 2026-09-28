"""Fechas y horas en lenguaje natural para pendientes (Fase 7).

Formato guardado, al estilo del plugin Obsidian Tasks: `📅 2026-09-30` (fecha) y opcionalmente
`⏰ 2026-09-30 18:00` (recordatorio a una hora exacta). Un pendiente puede tener fecha sin hora
("el viernes": aparece en el briefing/vencidos, pero no dispara un aviso a una hora concreta) u
hora sin fecha explícita ("a las 6pm": se asume hoy).

dateparser es bueno adivinando fechas relativas, pero en pruebas reales fallaba o daba resultados
sueltos (a veces hasta un año mal) cuando el texto mezclaba una fecha/día con una hora en la misma
frase ("el lunes a las 8am", "el 5 de octubre a las 9am"). Por eso la hora se reconoce aparte con
reglas propias y se le quita al texto antes de buscarle la fecha a dateparser; y una hora ambigua
("a las 8", sin am/pm ni "de la tarde/mañana/noche") no se adivina: mejor un pendiente sin
recordatorio exacto que uno que suene a la hora equivocada.
"""

import re
from datetime import date, datetime, time, timedelta

from dateparser.search import search_dates

from src.obsidian.vault_writer import normalizar

_CONFIGURACION_DATEPARSER = {"PREFER_DATES_FROM": "future"}

# --- hora ---

_HORA_AMPM = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s?m\.?\b", re.IGNORECASE)
_HORA_PERIODO = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*de\s+la\s+(mañana|tarde|noche)\b", re.IGNORECASE)
_HORA_24H = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_MEDIANOCHE = re.compile(r"\bmedianoche\b", re.IGNORECASE)
_MEDIODIA = re.compile(r"\bmediod[ií]a\b", re.IGNORECASE)
# Más amplio que los de arriba: solo para QUITAR del texto antes de buscar la fecha, no para sacar
# la hora de aquí ("a las 8" sin más se incluye para quitarlo, aunque su hora no se use).
_MENCION_DE_HORA = re.compile(
    r"\b\d{1,2}(:\d{2})?\s*[ap]\.?\s?m\.?\b"
    r"|\b\d{1,2}(:\d{2})?\s*de\s+la\s+(mañana|tarde|noche)\b"
    r"|\b([01]?\d|2[0-3]):[0-5]\d\b"
    r"|\ba\s+las?\s+\d{1,2}(:\d{2})?\b"
    r"|\bmedianoche\b|\bmediod[ií]a\b",
    re.IGNORECASE,
)


def _hora_desde_periodo(hora: int, periodo: str) -> int:
    """8 de la mañana -> 8; 8 de la tarde/noche -> 20; 12 de la tarde -> 12 (mediodía); 12 de la
    noche -> 0 (medianoche, la excepción: es la forma común de decirla en español)."""
    periodo = normalizar(periodo)
    if periodo == "manana":
        return hora % 12
    if periodo == "noche" and hora == 12:
        return 0
    return hora % 12 + 12


def extraer_hora(texto: str) -> time | None:
    """Hora explícita del texto, o None si es ambigua (ej. "a las 8" sin am/pm: mejor no adivinar)."""
    if _MEDIANOCHE.search(texto):
        return time(0, 0)
    if _MEDIODIA.search(texto):
        return time(12, 0)
    coincidencia = _HORA_AMPM.search(texto)
    if coincidencia:
        hora, minutos, periodo = int(coincidencia.group(1)), int(coincidencia.group(2) or 0), coincidencia.group(3)
        return time((hora % 12) + (12 if periodo.lower() == "p" else 0), minutos)
    coincidencia = _HORA_PERIODO.search(texto)
    if coincidencia:
        hora, minutos = int(coincidencia.group(1)), int(coincidencia.group(2) or 0)
        return time(_hora_desde_periodo(hora, coincidencia.group(3)), minutos)
    coincidencia = _HORA_24H.search(texto)
    if coincidencia:
        return time(int(coincidencia.group(1)), int(coincidencia.group(2)))
    return None


# --- fecha ---

_EN_HORAS_O_MINUTOS = re.compile(r"\ben\s+(\d+)\s*(hora|hr|minuto|min)s?\b", re.IGNORECASE)
_PASADO_MANANA = re.compile(r"\bpasado\s+ma[ñn]ana\b", re.IGNORECASE)

# Si dateparser encuentra una coincidencia que no contiene ningún dígito, debe ser al menos una de
# estas palabras (si no, es un falso positivo: en pruebas reales, la palabra suelta "hora" se leía
# como "hoy" y le ponía fecha a un pendiente que no la pedía).
_PALABRAS_DE_FECHA = {
    "hoy", "manana", "pasado", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
    "octubre", "noviembre", "diciembre", "semana", "dia", "dias", "proximo", "proxima", "siguiente",
}


def _parece_fecha_real(fragmento: str) -> bool:
    if any(caracter.isdigit() for caracter in fragmento):
        return True
    return any(palabra in normalizar(fragmento).split() for palabra in _PALABRAS_DE_FECHA)


def parsear_fecha_hora(texto: str, ahora: datetime | None = None) -> tuple[date | None, time | None]:
    """Fecha y hora que menciona el texto, en lenguaje natural. (None, None) si no menciona ninguna."""
    ahora = ahora or datetime.now()

    coincidencia = _EN_HORAS_O_MINUTOS.search(texto)
    if coincidencia:
        cantidad, unidad = int(coincidencia.group(1)), coincidencia.group(2).lower()
        delta = timedelta(hours=cantidad) if unidad.startswith(("hora", "hr")) else timedelta(minutes=cantidad)
        objetivo = ahora + delta
        return objetivo.date(), objetivo.time()

    if _PASADO_MANANA.search(texto):
        return (ahora + timedelta(days=2)).date(), extraer_hora(texto)

    hora = extraer_hora(texto)
    texto_sin_hora = _MENCION_DE_HORA.sub(" ", texto)
    try:
        coincidencias = search_dates(
            texto_sin_hora, languages=["es"], settings=_CONFIGURACION_DATEPARSER | {"RELATIVE_BASE": ahora}
        ) or []
    except ValueError:  # dateparser puede fallar con texto muy raro; no es motivo para crashear
        coincidencias = []
    fecha = next((momento.date() for fragmento, momento in coincidencias if _parece_fecha_real(fragmento)), None)

    if fecha is None and hora is not None:
        fecha = ahora.date()  # solo dieron una hora ("a las 6pm"): se asume hoy
    return fecha, hora


# --- guardar y leer los tags ya escritos en una línea de Pendientes.md ---


def formatear_tags(fecha: date, hora: time | None) -> str:
    partes = [f"📅 {fecha.isoformat()}"]
    if hora is not None:
        partes.append(f"⏰ {fecha.isoformat()} {hora.strftime('%H:%M')}")
    return " ".join(partes)


_TAG_FECHA = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
_TAG_HORA = re.compile(r"⏰\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")


def extraer_tags(linea: str) -> tuple[date | None, datetime | None]:
    """Lee los tags 📅/⏰ ya guardados en una línea de Pendientes.md."""
    fecha = None
    coincidencia = _TAG_FECHA.search(linea)
    if coincidencia:
        fecha = date.fromisoformat(coincidencia.group(1))
    hora = None
    coincidencia = _TAG_HORA.search(linea)
    if coincidencia:
        hora = datetime.fromisoformat(f"{coincidencia.group(1)} {coincidencia.group(2)}")
    return fecha, hora
