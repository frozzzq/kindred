# CLAUDE.md — Proyecto Jarvis (Agente de IA Personal)

> Guía de contexto para Claude Code. Léela completa antes de generar código. El proyecto crece
> por fases: no se avanza a la siguiente hasta que la anterior funcione y el usuario lo confirme.

---

## 🎯 Qué es Jarvis hoy

Un asistente personal de voz, local-first, con dos agentes y una memoria en Obsidian:

- **Crimson** — Ollama local (`qwen3:8b`) en la PC con GPU AMD **RX 7600** (8 GB, ROCm). Usa herramientas.
- **Clover** — Gemini Flash (Google AI Studio) para tareas complejas y búsqueda web.
- **STT**: faster-whisper local + Silero VAD; activación diciendo el nombre del agente.
- **TTS**: edge-tts (primario, gratis) con ElevenLabs de respaldo, **en vivo**: cada oración suena en
  cuanto el modelo la genera (streaming).
- **Memoria**: bóveda de Obsidian (`C:\kindred`) con **índice semántico híbrido** (embeddings locales +
  BM25) que les da a los agentes las notas relevantes en cada mensaje, conexiones automáticas entre
  notas del mismo tema, diario del día y reflexión periódica que aprende del usuario.
- **UI de escritorio** (Flet): Inicio (grafo 3D + panel Hoy), Chat, Bóveda, Uso y Ajustes.
- **Lanzador único**: `Jarvis.bat` (menú; también `Jarvis.bat <opción> [--pruebas]`).

**Hardware:** todo corre hoy en la PC Windows (Ollama, UI, bóveda; 192.168.1.95 = localhost). El
servidor Proxmox (Xeon E5-2680 v4, 24 GB) todavía no se usa; se integra en la Fase 13.

## ✅ Fases completadas (0–5)

- **0–1**: repo, clientes de Ollama y Gemini, router por palabras clave, CLI de texto.
- **2**: bóveda de Obsidian con herramientas (leer, buscar, pendientes, perfil, contactos) y reflexión.
- **3**: voz — push-to-talk, wake word "hey jarvis", activación por nombre con ventana de
  conversación de 1 minuto, Silero VAD, interrupción (tocando el micrófono o hablando mientras
  responde, con filtro de eco por similitud de texto).
- **4 (parcial)**: abrir apps (lista blanca), búsqueda web (grounding de Gemini + DuckDuckGo para
  Ollama), clicks y escritura automática en la ventana activa (pywinauto), cerrar la app por voz;
  confirmación explícita para lo irreversible.
- **5 (parcial)**: métricas de uso por motor. UI de escritorio construida (fuera del alcance original).

## ✅ Memoria, velocidad, voz y UI (2026-09-29) ← **implementado y probado en vivo, falta confirmación del usuario**

Lo pidió el usuario tras probar la gestión de notas: gestión total de la bóveda, conexiones verídicas,
respuestas sobre sus notas sin batallar, más velocidad, más personalidad, mejor UI y un entorno de
pruebas cómodo. Adelanta de la Fase 12 la "búsqueda híbrida con embeddings locales".

- **Índice semántico** (`src/obsidian/indice.py`): fragmentos por encabezado/párrafo con embeddings de
  `qwen3-embedding:0.6b` (Ollama, **forzado a CPU** con `num_gpu: 0` para no sacar a qwen3:8b de la
  VRAM; ~0.3 s por consulta) + BM25. SQLite en `%LOCALAPPDATA%\kindred\indice-<huella de la bóveda>.db`
  (una por bóveda). Incremental por fecha/tamaño; si falta el modelo, funciona solo por palabras y
  completa los vectores después.
- **Contexto por turno** (`src/agente/contexto_turno.py`): hora, pendientes **agrupados por urgencia**,
  notas relevantes (similitud ≥ 0.50, o ≥ 2 palabras en común sin embeddings; se excluyen perfil,
  contactos, tareas y patrones, que ya van aparte), el diario si pregunta por "ayer", una señal
  explícita cuando no hay notas relevantes y, solo en el primer mensaje, un aviso proactivo de lo
  vencido/de hoy. Va en el mensaje del usuario, no en el prompt de sistema (caché de Ollama).
- **Gestión de notas** (`src/obsidian/notas.py`): crear (sin carpeta cae junto a las notas de su tema;
  frontmatter con fecha y etiquetas), agregar, editar (respaldo en `%LOCALAPPDATA%\kindred\respaldos`),
  mover/renombrar (actualiza `[[enlaces]]`), conectar/desconectar (sección `## Relacionado`, siempre
  al final, enlace en una sola dirección), sugerir conexiones y eliminar (papelera, riesgo ALTO,
  solo nombre exacto, limpia enlaces rotos). Resolución flexible de nombres ("Jarvis", "[[Jarvis]]",
  "nodejs"). Notas índice por área (`04-Conocimiento/<Área>/<Área>.md`) mantenidas solas.
- **Conexiones verídicas**: mención por título (como "unlinked mentions" de Obsidian) o **mejor par de
  fragmentos** ≥ 0.50. Nunca con 00-Sistema ni con tareas/patrones/índices; nunca consigo misma.
- **Núcleo**: jardinero cada ~2 min (índice al día + ordenar/conectar notas escritas a mano, solo si
  llevan 10 min sin cambios) y diario al cierre (`06-Diario/AAAA-MM-DD.md`, sin pisar lo del usuario).
- **Velocidad**: streaming de Ollama a la voz (`_VozHonesta` retiene oraciones que afirmarían un
  cambio no hecho), precalentar modelo y prompt al abrir/activar, keep-alive 3 h, prompt compacto,
  acuse inmediato en voz para órdenes ("Va, dame un segundito") y frases de relleno al usar herramientas.
- **Personalidad**: Crimson cálida/mexicana con expresiones, Clover sereno con humor seco; ejemplos de
  tono sin acciones; género según la voz elegida; sin experiencias físicas fingidas.
- **Voz**: voces elegibles en la UI con prueba y velocidad (`src/ajustes.py`, `ajustes.json` > `.env`),
  diccionario de pronunciación para términos técnicos con voces es-*.
- **UI** (`src/ui/`): navegación lateral, panel Hoy (completar desde ahí, auditado como canal "ui"),
  chat en vivo con sugerencias, Bóveda (KPIs, búsqueda semántica que abre la nota en Obsidian,
  conexiones sugeridas), Uso (turnos, latencia, cuota de Gemini, 7 días), Ajustes (voces, núcleo,
  autoarranque, modo seguro, diagnóstico), indicadores de estado y saludo del día.
- **Entorno de pruebas**: `Jarvis.bat` (menú) reemplaza los 6 `.bat`; `--pruebas` usa
  `%LOCALAPPDATA%\kindred\boveda-pruebas` (notas de ejemplo con fechas relativas a hoy);
  `src/diagnostico.py`; `src/pruebas/evaluar_agentes.py` (15 escenarios reales por agente, con tiempos).
- **Métricas por turno** en `estado.db` (agente, canal, ms, herramientas, llamadas al modelo).
- **Estado técnico fuera de la bóveda**: el cursor de la reflexión pasó de `Configuracion.md` a
  `estado.db`; el log de interacciones rota por mes (`00-Sistema/Logs/AAAA-MM.md`).
- **Bóveda reestructurada** (respaldo previo en `%LOCALAPPDATA%\kindred\respaldos\boveda-antes-de-
  reestructurar-2026-09-29`): notas de prueba fuera, perfil/contactos/patrones limpios, Inicio, nota del
  proyecto Jarvis, áreas, plantillas y configuración de Obsidian (diario, plantillas, grafo sin 00-Sistema).

Aprendido al probar (medido en esta PC):
- La generación de qwen3:8b en la RX 7600 **depende mucho del contexto**: 38 tok/s con ~150 tokens,
  20.7 con 1.8k, 16.3 con 2.9k, 13.3 con 4k (flash attention ya activo). Cada regla y cada
  herramienta cuesta velocidad en todas las respuestas: escribirlas cortas y ofrecer solo los grupos
  que el mensaje pide. Compactar el prompt bajó el promedio de 8.7 s a 6.7 s.
- Precalentar importa: sin uso por más de `KEEP_ALIVE`, el primer mensaje tardó 38 s (recarga).
- En el template de qwen3 las herramientas van justo después del prompt de sistema: cambiar de grupo
  de herramientas solo re-procesa desde ahí (el prompt de sistema sigue en caché si no cambia).
- Similitud nota↔nota con el **promedio** de la nota no separa temas (todas las técnicas ~0.40-0.49);
  con el **mejor par de fragmentos** sí (Jarvis↔Ollama 0.57 vs Jarvis↔Express 0.42).
- Con los pendientes en lista plana, qwen3:8b dijo que uno del viernes estaba "atrasado"; agrupados
  por urgencia, no.
- Voces: las "Multilingual" de edge-tts leen bien términos en inglés pero deciden el idioma al inicio
  ("¡Órale, Josué!" → "Orala, Hostway") y tardan el doble; el endpoint de Edge rechaza SSML propio
  (`<lang>`), así que no se puede forzar. Por eso las de México son las predeterminadas.
- La red de seguridad del perfil extraía datos de **preguntas** ("¿dónde vive mi novia?"); ya no.
- `win11toast` (winrt) + onnxruntime en el mismo proceso: la UI tronaba con código 139 al importar
  `nucleo.servicio` → `avisos`. Las constantes compartidas viven en `nucleo/estado.py`; hay un test
  que verifica que la UI nunca cargue `win11toast`.
- Gemini gratis: 15 solicitudes/minuto; Clover gasta 1-3 por turno con herramientas. Un 429 a mitad
  de turno ahora se cuenta como "lo que sí hice + motivo corto", nunca el error crudo.
- **Clover también miente**: en la evaluación dijo "Ya vinculé la nota de Jarvis con la de Ollama" sin
  llamar `conectar_notas`. La red de honestidad ahora cubre a los dos (`_corregir_respuesta_gemini`),
  y los verbos "vincular/enlazar" cuentan como afirmación de cambio.
- SQLite: pasar a WAL una base recién creada exige exclusividad y el timeout no aplica; con varios
  hilos abriéndola a la vez salía "database is locked" (5 de 30 intentos). Cada base se prepara una
  sola vez por proceso, con candado y reintentos (`src/local.py::abrir_sqlite`).
- Resultado final de `Jarvis.bat evaluar`: Crimson 15/15 (6.9 s promedio, primera oración en 1.8 s),
  Clover 15/15 tras la corrección de honestidad (~3-5 s por turno, sin streaming).

---

## 🏗️ Arquitectura objetivo

Patrón **canal / cerebro / manos** (ver `docs/arquitectura.md`):

- **Núcleo** (proceso siempre activo desde la Fase 7): orquestador con herramientas, planificador
  (heartbeat), enrutador de notificaciones y canales. Estado técnico (recordatorios disparados,
  llamadas, sesiones) en SQLite en `%LOCALAPPDATA%\kindred\estado.db`, **no** en las notas.
- **Canales**: UI Flet, voz local, CLI, Telegram (F8), teléfono (F9).
- **Manos**: herramientas locales de Windows (apps, archivos, navegador, pantalla, terminal).
- **Memoria**: la bóveda de Obsidian es la fuente de verdad de todo lo que el usuario puede leer o
  editar a mano (pendientes, perfil, contactos, notas).
- **Registro de herramientas** (`src/herramientas/`, Fase 6): una sola capa que usan Crimson,
  Clover, los atajos por palabras clave y, más adelante, Telegram y el teléfono.

El núcleo empieza en la PC (autoarranque con Windows) y se diseña para moverse al Proxmox.

## 🔐 Permisos y seguridad (obligatorio para toda herramienta nueva)

Cada herramienta declara su **riesgo**; la política se aplica en un solo lugar (`registro.ejecutar`):

| Riesgo | Qué hace el sistema | Ejemplos |
|---|---|---|
| `LECTURA` | Ejecuta directo | leer notas, listar apps, buscar en la web |
| `BAJO` | Ejecuta directo y registra | abrir app/URL/carpeta, escribir texto, click neutro, agregar pendiente |
| `ALTO` | Confirma siempre | click en "Eliminar/Enviar/Comprar", mover o borrar archivos, enviar correo/WhatsApp |
| `CRITICO` | Confirma mostrando exactamente qué hará | comandos de terminal |

Reglas:
- El riesgo puede depender de los argumentos (click en "Guardar" = BAJO, en "Eliminar" = ALTO).
- La confirmación usa el canal activo: diálogo en la UI, "sí/no" por voz, botones en Telegram, voz en llamada.
- Toda acción queda en `00-Sistema/Registro-Acciones.md` (fecha, canal, herramienta, argumentos, resultado).
- **Modo seguro** ("Jarvis, modo seguro"): bloquea todo lo que no sea `LECTURA` hasta "sal del modo seguro".
- **Contenido externo es dato, no instrucción**: correos, páginas web y mensajes nunca se obedecen
  como órdenes. Como enviar/borrar/ejecutar siempre requiere confirmación humana, una inyección de
  prompt no puede actuar sola.
- **Acceso a archivos** solo dentro de `CARPETAS_PERMITIDAS` (carpetas de usuario); borrar = papelera.
- **Llamadas** solo al número del usuario (`TELEFONO_USUARIO`), con horario de silencio y tope diario.
- **Secretos** solo en `.env` (ignorado por git); tokens OAuth en `%LOCALAPPDATA%\kindred\`, nunca en el repo.
- Nunca aceptar órdenes de canales no autorizados (Telegram: solo el `chat_id` del usuario).

---

## 🗺️ Roadmap

### Fase 6 — Cimientos: herramientas con permisos ← **implementada, falta confirmación del usuario**
- Registro de herramientas con riesgo, confirmación, auditoría y modo seguro (`src/herramientas/`).
- Crimson y Clover usan las mismas herramientas; **Clover gana function calling** (bucle manual en
  `gemini_client.py` para que todo pase por los permisos).
- **Abrir cualquier app instalada**: índice de `Get-StartApps` (261 apps con nombre en español),
  coincidencia aproximada ("fotoshop" → Photoshop), alias editables en
  `00-Sistema/Alias-Aplicaciones.md`, sin confirmación. Reemplaza la lista blanca fija.
- Abrir URLs en pestaña nueva y carpetas permitidas.
- Los atajos por palabras clave (cerrar, abrir, click, escribir) se mantienen por velocidad pero
  ejecutan vía el registro. `hotwords` de faster-whisper con los nombres de los agentes.
- **Hecho cuando**: "abre fotoshop" abre Photoshop sin preguntar; Clover encadena varias
  herramientas en un turno; "haz click en Eliminar" pide confirmación; en modo seguro se rechazan
  acciones; todo queda en `Registro-Acciones.md`; tests en verde.
- Aprendido al probar: qwen3:8b (sin razonamiento) deja de consultar la bóveda si recibe herramientas
  que no vienen al caso, así que a Crimson solo se le dan los grupos que el mensaje pide
  (`seleccionar_grupos(..., modelo_local=True)`). Al agregar herramientas nuevas, medir con el modelo
  real que las preguntas sobre la bóveda sigan llamando `leer_nota`.

### Fase 7 — Tiempo y proactividad ← **implementada (parcial), falta confirmación del usuario**
- Núcleo como proceso de fondo (`src/nucleo/`, `Jarvis.bat nucleo`, o lo inicia la UI sin ventana con
  log en `%LOCALAPPDATA%\kindred\nucleo.log`), independiente de la UI/voz/CLI:
  heartbeat cada 30 s que revisa recordatorios y briefings, y avisa por Windows (`win11toast`) + voz.
  Autoarranque con el Programador de tareas de Windows vía `src/nucleo/autoarranque.py`
  (`registrar_tarea_programada()`): existe pero no se activa solo, hay que correrlo (o pedírselo al
  agente) a propósito, porque es un cambio persistente del sistema.
- Pendientes con fecha/hora en formato Obsidian Tasks: `- [ ] Entregar tarea 📅 2026-09-30 ⏰ 2026-09-30 18:00`;
  fechas en lenguaje natural ("mañana a las 6pm", "el viernes") con `dateparser` + reglas propias en
  `src/obsidian/fechas.py` (una hora ambigua como "a las 8" sin am/pm no se adivina: mejor sin
  recordatorio exacto que a la hora equivocada). 📅 sin ⏰ es una fecha de referencia (sale en el
  briefing); ⏰ dispara un aviso puntual.
- Recurrentes en `02-Tareas/Recurrentes.md` (`src/obsidian/recurrentes.py`, tag propio 🔁): diario o
  en días de la semana concretos, siempre con una hora ("tomar medicina, diario a las 9pm").
- Estado técnico (qué ya se avisó, para no duplicar; último briefing de cada tipo) en SQLite,
  `src/nucleo/estado.py` (`%LOCALAPPDATA%\kindred\estado.db`), no en la bóveda.
- `00-Sistema/HEARTBEAT.md`: se reescribe cada vuelta con la hora del último ciclo (por ahora solo
  estado, no es aún el checklist editable de monitores de OpenClaw — eso llega con los monitores de
  percances de la Fase 9).
- **Briefing matutino y cierre del día** a `HORA_BRIEFING`/`HORA_CIERRE` (pendientes de hoy, vencidos,
  recurrentes de hoy; lo redacta Crimson con `preguntar_ollama`, con un resumen sin IA de respaldo si
  Ollama falla). `HORARIO_SILENCIO` retrasa cualquier aviso (recordatorio o briefing) sin marcarlo
  como avisado, para que salga apenas termine el silencio.
- **Hecho cuando**: un recordatorio a una hora dada llega aunque la UI esté cerrada, sin duplicarse.
  Verificado en pruebas reales (bóveda de copia): agrega con fecha natural, `ciclo()` avisa una sola
  vez al vencer y no se repite, `HEARTBEAT.md` se actualiza, y el briefing usa datos reales de la bóveda.
- **Pendiente dentro de esta fase**: Piper como TTS offline de respaldo; unificar `main.py`/`main_ui.py`/
  `main_voz.py` como clientes del núcleo por IPC (hoy cada uno llama `procesar_comando` directo — hará
  falta cuando Telegram, Fase 8, deba compartir estado en vivo con el núcleo). El diario automático y
  la rotación mensual del log ya se hicieron (ver la sección de 2026-09-29).
- Aprendido al probar: `win11toast` (usa `winrt`) provoca un access violation nativo si se carga en
  el mismo proceso *después* de `onnxruntime` (openwakeword/VAD/faster-whisper) — nunca al revés. El
  núcleo corre en su propio proceso por esto también, y `tests/conftest.py` fuerza el orden seguro
  para que la suite completa no truene.

### Fase 8 — Telegram (canal móvil)
- Bot bidireccional: texto y notas de voz (transcritas con Whisper); solo responde a `TELEGRAM_CHAT_ID`.
- Recordatorios y briefings por Telegram; confirmaciones con botones Sí/No.
- Captura rápida a `00-Sistema/Inbox.md`, clasificada después (tarea, idea, contacto, nota).
- **Hecho cuando**: desde el celular se puede pedir algo, confirmar una acción y recibir recordatorios.

### Fase 9 — Llamadas telefónicas proactivas
- **9a interactiva**: Twilio llama al celular, dice el aviso con voz es-MX y escucha "sí/no" o
  teclas (1 = ya lo hice) para actualizar pendientes. Webhook por túnel con dominio fijo; se valida
  la firma de Twilio.
- **9b conversación completa**: Twilio Media Streams ↔ Gemini Live (audio bidireccional en tiempo
  real, con interrupciones), con la personalidad del agente y herramientas seguras (pendientes, agenda).
- Escalamiento: aviso → Telegram → llamada si no respondes en N minutos. Horario de silencio, tope
  de llamadas/día y de gasto/mes.
- Monitores de "percances": Ollama caído, disco casi lleno, sin internet, proceso largo terminado.
- **Hecho cuando**: un pendiente vencido e ignorado termina en una llamada en la que se puede
  conversar y marcarlo como hecho.

### Fase 10 — Control amplio del PC
- Archivos en carpetas permitidas: crear, leer, buscar, renombrar (BAJO); mover y borrar a la
  papelera con `send2trash` (ALTO).
- Navegador: pestañas y URLs; automatización de páginas con Playwright como sub-fase.
- "¿Qué hay en mi pantalla?": captura + visión de Gemini (explicar errores, resumir lo que se ve).
- Portapapeles ("resume/traduce lo que copié"); sistema (volumen, medios, bloquear la PC).
- Terminal (CRITICO): siempre confirmada, muestra el comando exacto, timeout y salida resumida.
- Aviso cuando termina un proceso largo (build, entrenamiento, descarga).
- Mejora de eco para la interrupción: audífonos o cancelación de eco por software.

### Fase 11 — Comunicación
- Gmail API: leer, buscar y resumir la bandeja; borradores; enviar (ALTO).
- Google Calendar: consultar y crear eventos, avisos antes de cada evento, entra al briefing.
- WhatsApp Desktop: enviar vía `whatsapp://send?phone=...&text=...` + Enter tras confirmar.
- Contactos con teléfono y correo estructurados en `01-Perfil/Contactos.md`.

### Fase 12 — Vida, estudio, trabajo y negocio
- **Estudio**: clases/reuniones grabadas → transcripción + resumen + tareas con fecha en la bóveda;
  quiz y repaso espaciado de notas; seguimiento de entregas y exámenes.
- **Vida personal**: hábitos, revisión semanal automática, metas.
- **Negocio**: finanzas por voz ("gasté 200 en...") con resumen mensual y alertas de presupuesto;
  CRM ligero (clientes, último contacto, seguimientos); cotizaciones desde plantillas (Markdown → PDF).
- **Programación**: comandos git/tests por voz, agente de investigación (Gemini + fuentes → nota).
- ~~Búsqueda en la bóveda híbrida con embeddings locales de Ollama~~ (hecha el 2026-09-29).
- Repaso espaciado y quizzes pueden reusar el índice semántico (`indice.buscar`, `notas_similares`).

### Fase 13 — Servidor 24/7
- Núcleo al Proxmox (LXC); bóveda sincronizada con Syncthing; agente "manos" en la PC conectado
  por LAN con token; Gemini o un modelo ligero en CPU cuando la PC esté apagada.

---

## 🔍 Alternativas evaluadas

- **Integrar OpenClaw** → no. Se toman sus patrones (canal/cerebro/manos, HEARTBEAT.md,
  aprobaciones, auditoría, topes de gasto) porque Jarvis ya tiene voz, personalidades y bóveda
  propias en Python, y OpenClaw tuvo incidentes de seguridad (skills maliciosas, gateways expuestos).
- **MCP**: el registro de herramientas se diseña para poder conectar servidores MCP más adelante.
- **Llamada completa**: Gemini Live en vez de ElevenLabs Agents (misma API key, control total,
  ejemplos de referencia con Twilio).
- **WhatsApp**: automatizar WhatsApp Desktop (tu propia cuenta) en vez de la API de negocio de Meta
  (número aparte, plantillas); Telegram como canal propio de Jarvis.
- **Clicks**: por texto accesible (pywinauto/UIAutomation) en vez de coordenadas o capturas + visión.
  Tkinter y algunas apps web no exponen nombres accesibles.

---

## 📂 Estructura del repositorio

```
kindred/
├─ CLAUDE.md, README.md, docs/arquitectura.md, docs/pruebas-manuales.md
├─ requirements.txt, requirements-dev.txt, requirements-lock.txt, .env.example
├─ Jarvis.bat                   # lanzador único (menú; `Jarvis.bat <opción> [--pruebas]`)
├─ src/
│  ├─ lanzador.py, arranque.py  # menú; arranque común (.env, bóveda, --pruebas, --seccion)
│  ├─ main.py                   # procesar_comando (streaming, red de honestidad, métricas) + CLI de texto
│  ├─ main_ui.py, main_voz.py, main_voz_wakeword.py, main_metricas.py
│  ├─ ajustes.py, local.py, diagnostico.py   # ajustes de la UI, %LOCALAPPDATA%\kindred, diagnóstico
│  ├─ router/intent_router.py   # atajos por palabras clave
│  ├─ herramientas/             # registro con permisos, catálogo por grupos y auditoría (Fase 6)
│  ├─ nucleo/                   # heartbeat, recordatorios, briefing, diario, jardinero, proceso, estado
│  ├─ engines/                  # ollama_client (streaming, precalentar), gemini_client, embeddings
│  ├─ agente/                   # personalidad, contexto_turno, conversación, reflexión, oraciones,
│  │                            #   métricas por turno, saludo del día
│  ├─ obsidian/                 # lectura/escritura, estructura, formato, índice semántico, notas
│  │                            #   (crear/editar/mover/conectar/eliminar), tareas, grafo, fechas
│  ├─ actions/                  # apps, clicks/escritura, búsqueda web, confirmación
│  ├─ voice/                    # stt, tts (VozEnVivo, pronunciación), vad, activación, wake word
│  ├─ ui/                       # app, estilo, vistas (hoy, bóveda, uso, ajustes), grafo 3D, paletas
│  └─ pruebas/                  # bóveda de ejemplo y evaluador de agentes con modelos reales
└─ tests/                       # conftest aísla %LOCALAPPDATA% y apaga los embeddings reales
```

Se mantiene la separación por responsabilidad; módulos nuevos de fases futuras:
`canales/telegram.py` (F8), `canales/telefono.py` (F9), `integraciones/google.py` (F11).

## 📂 Bóveda de Obsidian

```
C:\kindred\
├─ Inicio.md    nota de entrada: mapa y áreas (las áreas se agregan solas)
├─ 00-Sistema/  Logs/AAAA-MM.md, Registro-Acciones (F6), Alias-Aplicaciones (F6), HEARTBEAT (F7),
│               Plantillas/, Respaldos/, Inbox (F8)          ← nunca se busca ni se conecta
├─ 01-Perfil/   Yo, Contactos, Patrones
├─ 02-Tareas/   Pendientes, Completadas, Recurrentes
├─ 03-Proyectos/     una nota por proyecto (Jarvis...)
├─ 04-Conocimiento/  una subcarpeta por área, cada una con su nota índice (<Área>/<Área>.md)
├─ 05-Decisiones/    06-Diario/ (AAAA-MM-DD, lo escribe el núcleo al cierre)    07-Archivo/
```

Ruta configurable con `OBSIDIAN_VAULT_PATH`, nunca hardcodeada. Categorías y reglas en
`src/obsidian/estructura.py`: sistema (no se busca ni conecta), operativas (se buscan, no se
conectan) y conocimiento. Las notas que mantienen las herramientas llevan `## Relacionado` al final.
Obsidian está configurado para usar `00-Sistema/Plantillas` y `06-Diario`, y su grafo oculta 00-Sistema.

## 🔑 Variables de entorno

```
# Actuales
OLLAMA_HOST=http://<ip-de-la-pc>:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b   # memoria semántica (ollama pull), corre en CPU
OLLAMA_KEEP_ALIVE=3h                      # "-1" = nunca descargar el modelo de la VRAM
GEMINI_API_KEY=
GEMINI_MODEL=
GEMINI_DAILY_QUOTA=1000
EDGE_TTS_VOICE=  EDGE_TTS_VOICE_OLLAMA=  EDGE_TTS_VOICE_GEMINI=
ELEVENLABS_API_KEY=  ELEVENLABS_VOICE_ID=  ELEVENLABS_VOICE_ID_OLLAMA=  ELEVENLABS_VOICE_ID_GEMINI=
OBSIDIAN_VAULT_PATH=
GANANCIA_MICROFONO=3.0
# Fase 6
CARPETAS_PERMITIDAS=        # separadas por ";" — por defecto Escritorio, Documentos, Descargas, Imágenes
# Fase 7
HORA_BRIEFING=08:00  HORA_CIERRE=21:30  HORARIO_SILENCIO=23:00-07:00
# Fase 8
TELEGRAM_BOT_TOKEN=  TELEGRAM_CHAT_ID=
# Fase 9
TWILIO_ACCOUNT_SID=  TWILIO_AUTH_TOKEN=  TWILIO_NUMERO=  TELEFONO_USUARIO=  URL_PUBLICA=
MAX_LLAMADAS_DIA=5
# Fase 11
GOOGLE_OAUTH_CLIENTE=       # ruta al JSON del cliente OAuth (fuera del repo)
```

## 🧰 Preparación que hace el usuario (fuera del código)

- **F8**: crear el bot con @BotFather y obtener el token; mandarle un mensaje para registrar el `chat_id`.
- **F9**: cuenta de Twilio con saldo, un número (~1.15 USD/mes), permiso geográfico para México,
  y un túnel con dominio fijo (ngrok con dominio estático gratis o Cloudflare Tunnel con dominio
  propio). Costo estimado: ~0.05 USD/min a celular de México.
- **F11**: proyecto en Google Cloud con Gmail API y Calendar API y un cliente OAuth de escritorio;
  instalar WhatsApp Desktop.

## ⚙️ Convenciones

- Python 3.11+; nombres, comentarios y mensajes en español.
- `httpx` para HTTP; manejo de errores explícito con fallback, nunca un crash que corte la conversación.
- Cada módulo testeable en aislamiento (se mockean Ollama, Gemini, audio, ventanas y APIs externas).
- Tests con `pytest`; la suite completa debe quedar en verde antes de cada commit.
- Verificación en vivo de automatización de ventanas **solo sobre objetivos desechables** (pestaña
  nueva en blanco), nunca sobre ventanas con contenido real del usuario.
- Commits pequeños y descriptivos; no se hace push sin que el usuario lo pida.
- Regenerar `requirements-lock.txt` al cambiar dependencias.
- Estado técnico (cursores, avisos, métricas, índice, ajustes) en `%LOCALAPPDATA%\kindred\`, nunca en
  la bóveda. Los tests lo aíslan solos (`tests/conftest.py`: carpeta temporal y embeddings apagados).
- Prompt y descripciones de herramientas **cortos**: en esta GPU cada 1000 tokens de contexto cuestan
  ~3 tok/s de generación en todas las respuestas. Medir con `Jarvis.bat evaluar` al cambiarlos.
- La UI y la voz nunca deben importar `win11toast` (ni `nucleo.servicio`/`nucleo.avisos`): con
  onnxruntime en el mismo proceso truena con código 139. Hay un test que lo vigila.
- Verificar la UI en vivo sin tocar el escritorio del usuario: servirla en modo web
  (`ft.run(..., view=ft.AppView.WEB_BROWSER)` con `FLET_DISPLAY_URL_PREFIX` para que no abra el
  navegador; `flet-web` instalado solo en el venv) y capturarla con Chrome headless por DevTools.
  Las ventanas de Flet de escritorio lanzadas en segundo plano no pintan hasta activarse.
- Para cualquier cambio de comportamiento de los agentes: `Jarvis.bat evaluar` antes y después.

## 🚫 Fuera de alcance por ahora

- Fine-tuning de modelos y wake words entrenados a medida (evaluado: demasiado costoso para el beneficio).
- Multiusuario y despliegue público.
- Pagos o compras automáticas sin intervención humana.

## ▶️ Siguiente objetivo

Las **Fases 6 y 7** y el paquete de **memoria, velocidad, voz y UI (2026-09-29)** están implementados
y verificados (suite automática + `Jarvis.bat evaluar` con los modelos reales + la UI renderizada).
Antes de la Fase 8, esperar a que el usuario los pruebe (`docs/pruebas-manuales.md`) y confirme.

Pendiente de esta etapa (para la siguiente sesión):
- Que el usuario elija voces en Ajustes tras escucharlas (las multilingües quedaron como experimentales).
- Vigilar en uso real el umbral de conexión (0.50) y el de contexto (0.50) con notas reales de su
  carrera; si conecta de más o de menos, ajustar en `src/obsidian/notas.py` / `indice.py`.
- qwen3:8b todavía cierra a veces con preguntas de seguimiento y usa emojis (la voz los omite).
- Opcional en el servidor de Ollama (cambio del sistema, solo si el usuario lo pide):
  `OLLAMA_KV_CACHE_TYPE=q8_0` podría acelerar la generación con contexto largo en la RX 7600.
- El autoarranque del núcleo existe (botón en Ajustes) pero no está activado en el sistema real:
  activarlo solo si el usuario lo pide.
