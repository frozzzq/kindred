"""Parte en oraciones un texto que llega a pedazos (streaming), para ir hablándolo sin esperar el final.

Cada oración se sintetiza por separado, así que trozos muy cortos suenan entrecortados: se juntan
hasta un mínimo de caracteres, salvo la primera, que sale en cuanto está completa para empezar a
hablar lo antes posible.
"""

import re
from collections.abc import Callable

_FIN = re.compile(r"[.!?…]+[\"'»)]*\s+|\n+")
MINIMO_PRIMERA = 2
MINIMO_SIGUIENTES = 40


class Oracionador:
    def __init__(self, al_oracion: Callable[[str], None]) -> None:
        self._al_oracion = al_oracion
        self._pendiente = ""
        self._emitidas = 0

    def agregar(self, fragmento: str) -> None:
        self._pendiente += fragmento
        inicio = 0
        for coincidencia in _FIN.finditer(self._pendiente):
            candidato = self._pendiente[: coincidencia.end()].strip()
            minimo = MINIMO_PRIMERA if self._emitidas == 0 else MINIMO_SIGUIENTES
            if len(candidato) >= minimo:
                inicio = coincidencia.end()
                self._emitir(candidato)
                break
        if inicio:
            self._pendiente = self._pendiente[inicio:]
            self.agregar("")

    def terminar(self) -> None:
        if self._pendiente.strip():
            self._emitir(self._pendiente.strip())
        self._pendiente = ""

    def _emitir(self, oracion: str) -> None:
        self._emitidas += 1
        self._al_oracion(oracion)
