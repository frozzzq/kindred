"""Memoria de corto plazo: los últimos turnos de la conversación actual.

Sin esto cada mensaje era independiente y el agente no recordaba lo que se
le dijo un mensaje antes. Solo se guardan los textos finales (no las
llamadas a herramientas intermedias) para no llenar el contexto del modelo.
"""

import threading

MAX_MENSAJES = 10  # 5 turnos usuario/agente


class Conversacion:
    def __init__(self, max_mensajes: int = MAX_MENSAJES) -> None:
        self._max = max_mensajes
        self._mensajes: list[dict] = []
        self._bloqueo = threading.Lock()

    def agregar_turno(self, texto_usuario: str, respuesta: str) -> None:
        with self._bloqueo:
            self._mensajes.append({"role": "user", "content": texto_usuario})
            self._mensajes.append({"role": "assistant", "content": respuesta})
            self._mensajes = self._mensajes[-self._max:]

    def mensajes(self) -> list[dict]:
        with self._bloqueo:
            return list(self._mensajes)

    def como_transcripcion(self) -> str:
        """Los turnos recientes como texto, para motores sin historial nativo."""
        nombres = {"user": "Usuario", "assistant": "Tú"}
        return "\n".join(f"{nombres[m['role']]}: {m['content']}" for m in self.mensajes())
