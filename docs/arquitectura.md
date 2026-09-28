# Arquitectura de Jarvis

Patrón **canal / cerebro / manos**: los canales reciben y entregan mensajes, el cerebro decide
qué hacer, y las manos ejecutan acciones reales a través de un registro de herramientas con
permisos. La bóveda de Obsidian es la memoria que el usuario también puede leer y editar.

```
                    ┌────────────────────────── CANALES ──────────────────────────┐
                    │  UI Flet   Voz local   CLI   Telegram (F8)   Teléfono (F9)   │
                    └───────────────────────────────┬──────────────────────────────┘
                                                    │ texto + canal (para confirmar)
                                                    ▼
┌─────────────────────────────────── NÚCLEO (siempre activo desde F7) ───────────────────────────────────┐
│                                                                                                         │
│  procesar_comando ──► atajos por palabras clave (cerrar, abrir, click, escribir, modo seguro)           │
│        │                                                                                                │
│        └──► agente con herramientas:  Crimson (Ollama qwen3:8b)  |  Clover (Gemini, function calling)  │
│                                                                                                         │
│  Planificador / heartbeat (F7) ──► recordatorios, briefing, monitores de percances                      │
│  Enrutador de notificaciones (F7–F9) ──► voz · Windows · Telegram · llamada (con escalamiento)          │
│  Estado técnico: SQLite en %LOCALAPPDATA%\kindred\estado.db                                             │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                │ registro.ejecutar(nombre, argumentos, contexto)
                                                ▼
┌──────────────────────── REGISTRO DE HERRAMIENTAS (src/herramientas/) ─────────────────────────┐
│  1. ¿modo seguro? → solo LECTURA                                                               │
│  2. riesgo ALTO/CRITICO → confirmación por el canal activo                                     │
│  3. ejecutar (errores → texto para el agente, nunca excepción)                                  │
│  4. auditoría en 00-Sistema/Registro-Acciones.md                                               │
└──────────────┬──────────────────────┬───────────────────────┬─────────────────────────────────┘
               ▼                      ▼                       ▼
        MANOS (Windows)        MEMORIA (bóveda)         SERVICIOS EXTERNOS
   apps, URLs, carpetas,     pendientes, perfil,      web (Gemini/DuckDuckGo), Gmail y
   clicks, escritura,        contactos, notas         Calendar (F11), WhatsApp (F11),
   archivos, pantalla,                                Twilio + Gemini Live (F9)
   terminal (F10)
```

## Flujo de un comando

1. El canal entrega el texto y un `ContextoEjecucion` (cómo confirmar en ese canal, si hay modo seguro).
2. Si coincide un atajo (ej. "abre spotify"), se ejecuta la herramienta directo vía el registro.
3. Si no, el agente elegido recibe solo los grupos de herramientas relevantes para el mensaje
   (`seleccionar_grupos`) y decide cuáles llamar; cada llamada pasa por `registro.ejecutar`.
4. La respuesta vuelve por el mismo canal (texto, voz, Telegram o la llamada).

## Dónde corre

- **Hoy (F6–F12)**: todo en la PC Windows (Ollama con la RX 7500, UI, bóveda en `C:\kindred`).
- **F13**: el núcleo pasa al servidor Proxmox; la PC queda con un agente "manos" conectado por LAN,
  y la bóveda se sincroniza con Syncthing.
