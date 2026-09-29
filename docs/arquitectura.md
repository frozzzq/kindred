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
3. Si no, se arma el **contexto del turno** (`src/agente/contexto_turno.py`): hora, pendientes
   agrupados por urgencia y las notas relevantes que encuentra el índice semántico. Va pegado al
   mensaje del usuario, no al prompt de sistema, para que Ollama reutilice de caché el prompt y el
   historial.
4. El agente elegido recibe solo los grupos de herramientas relevantes (`seleccionar_grupos`) y
   decide si le basta el contexto o llama herramientas; cada llamada pasa por `registro.ejecutar`.
5. La respuesta de Crimson llega en streaming: cada oración se habla (o se escribe en el chat) en
   cuanto está lista, salvo las que afirmarían un cambio no hecho, que pasan antes por la red de
   honestidad (`_VozHonesta` en `src/main.py`).

## Memoria de la bóveda

```
 notas (.md) ──► índice híbrido (src/obsidian/indice.py, SQLite local por bóveda)
                   ├─ fragmentos por encabezado/párrafo + embeddings (qwen3-embedding en CPU)
                   └─ BM25 por palabras (funciona aunque falte el modelo de embeddings)
        │
        ├─► contexto de cada turno (notas relevantes, sin que el agente tenga que buscarlas)
        ├─► buscar_en_boveda / sugerir_conexiones
        └─► conexiones: mención por título o mejor par de fragmentos ≥ 0.50 (src/obsidian/notas.py)

 núcleo ──► jardinero (cada ~2 min): índice al día + conectar/ordenar notas escritas a mano
        └─► diario (al cierre): 06-Diario/AAAA-MM-DD.md con lo que pasó
```

Categorías (`src/obsidian/estructura.py`): **sistema** (00-Sistema: nunca se busca ni se conecta),
**operativas** (tareas y patrones: se buscan, no se conectan) y **conocimiento** (todo lo demás).

## Dónde corre

- **Hoy (F6–F12)**: todo en la PC Windows (Ollama con la RX 7600 por ROCm, UI, bóveda en `C:\kindred`).
- **F13**: el núcleo pasa al servidor Proxmox; la PC queda con un agente "manos" conectado por LAN,
  y la bóveda se sincroniza con Syncthing.
