# kindred

Asistentes IA para uso personal.

## Jarvis

Asistente de voz personal local-first. Ver [CLAUDE.md](CLAUDE.md) para la
arquitectura completa y el plan de fases.

Estado actual: **Fase 0 + Fase 1 + Fase 2 + Fase 3 (completa, con wake
word) + Fase 4 (parcial) + Fase 5 (parcial) + UI de escritorio**
(scaffold, MVP por CLI de texto con Ollama/Gemini, integración con una
bóveda de Obsidian como memoria, voz con Whisper local + ElevenLabs —
push-to-talk o manos libres con wake word "hey jarvis" —, control del
sistema: abrir aplicaciones y búsqueda web con confirmación obligatoria,
métricas de uso, y una UI de escritorio con Flet). Sin clicks/escritura
automática ni correo/redes sociales todavía.

### Lanzadores rápidos

Para no tener que abrir consola cada vez: `Jarvis-UI.bat`, `Jarvis-Texto.bat`,
`Jarvis-Voz.bat`, `Jarvis-VozManosLibres.bat` y `Jarvis-Metricas.bat` en la
raíz del repo activan el entorno y corren el modo correspondiente con doble
clic. Hay accesos directos a cada uno en el escritorio.

**Modelo de Ollama:** usa `qwen3:8b` por defecto (mejor razonamiento que
`mistral:7b`, confirmado en pruebas reales) con `num_ctx=8192` en las
llamadas (`src/engines/ollama_client.py`) — Ollama usa 4096 tokens de
contexto por defecto aunque el modelo soporte más, y con el contexto de
Obsidian + búsqueda web que se le inyecta, se saturaba fácil. Cambia
`OLLAMA_MODEL` en tu `.env` si prefieres otro (ej. `mistral-nemo` es
fuerte específicamente en español).

**Velocidad de Ollama:** tres ajustes en `src/engines/ollama_client.py` y
`src/main.py`, confirmados con mediciones reales:
- `think: false` — Qwen3 (y otros modelos "razonadores") generan un modo
  de pensamiento largo por defecto que nunca mostramos; desactivarlo bajó
  una respuesta trivial de ~5.8s a ~0.6s.
- `keep_alive: "30m"` — sin esto, Ollama descarga el modelo de la VRAM
  tras 5 minutos sin uso (default del servidor) y el siguiente mensaje
  paga la recarga completa (~5-6GB desde disco): **26.5s medidos** en una
  recarga real, contra **0.9-2.3s** con el modelo ya caliente. Esto era la
  causa principal de la lentitud "de cada mensaje", no el hardware.
- `INSTRUCCION_BREVEDAD` — se le pide al modelo responder en 1-3 oraciones
  salvo que se pida detalle, lo que además de generarse más rápido reduce
  el texto que ElevenLabs tiene que sintetizar (TTS bajó de ~5-10s a
  ~1.5s en pruebas, sin necesitar streaming).

**Micrófono débil:** si tu micrófono entrega poca señal incluso al
volumen máximo de Windows, la voz amplifica la señal capturada por
software (`GANANCIA_MICROFONO` en `.env`, default 3.0x) antes de mandarla
a Whisper y al detector de wake word — afecta tanto STT como wake word.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env      # y completar con tus valores reales
```

### Uso

CLI de texto:
```bash
python -m src.main
```

CLI de voz (push-to-talk, requiere micrófono y `ELEVENLABS_API_KEY` con
créditos disponibles):
```bash
python -m src.main_voz
```
Presiona Enter para empezar a hablar y Enter de nuevo para terminar de
grabar. Si ElevenLabs falla (sin créditos, sin conexión), la respuesta se
muestra como texto en vez de audio.

CLI de voz manos libres, con wake word (di **"hey jarvis"** para activar,
sin presionar nada — graba automáticamente hasta detectar silencio):
```bash
python -m src.main_voz_wakeword
```
Usa [openWakeWord](https://github.com/dscripka/openWakeWord) (100% local,
sin costo, modelo `hey_jarvis` pre-entrenado). La primera vez descarga los
modelos (~5 MB). Requiere el mismo micrófono/ElevenLabs que el modo
push-to-talk.

En todos los casos, un comando simple va a Ollama y uno complejo (p. ej.
"busca en internet...") va a Gemini, con fallback automático a Ollama si falla.

**Nombres de personalidad:** en consola (y ya sea texto o voz), Ollama se
muestra como **Crimson** y Gemini como **Clover** (ej. "Crimson: ..."), y
las acciones del sistema como **Jarvis**. Internamente siguen siendo
`ollama`/`gemini`/`accion`, así que no afecta logs, `.env` ni tests. Se
define en `NOMBRES_MOTOR` (`src/router/intent_router.py`).

**Personalidad, memoria y bóveda (`src/agente/`, `src/obsidian/herramientas.py`):**
- Cada agente tiene un prompt de sistema con su personalidad
  (`src/agente/personalidad.py`): **Crimson** es confiable, alegre,
  calculadora y diplomática; **Clover** es igual de inteligente pero seria,
  fría, orientada a cumplir el objetivo, ordenada y transparente. Incluye la
  fecha, el mapa de la bóveda y tu perfil (`Yo.md`, `Patrones.md`).
- Recuerda los últimos 5 turnos de la conversación (`src/agente/conversacion.py`);
  en la UI, Voz y Chat comparten la misma conversación.
- Crimson usa la bóveda con **herramientas** (tool calling de Ollama): lee
  notas completas, busca, agrega y completa pendientes, guarda datos tuyos y
  contactos. Si una petición es ambigua, pregunta antes de actuar.
- Salvaguardas contra un modelo de 8B que a veces falla: si dice que cambió
  algo sin haber llamado a la herramienta, se le pide hacerlo de verdad (y si
  insiste, admite que no pudo); si escribe la llamada como texto JSON, se
  ejecuta igual; se quita la muletilla "¿necesitas algo más?" del final.
- **Reflexión** (`src/agente/reflexion.py`): cada 10 interacciones, en
  segundo plano, revisa lo nuevo del log y anota en `Yo.md` y `Patrones.md`
  lo que aprendió de ti (sin duplicar, y exigiendo 3+ interacciones para un
  patrón). El contador vive en `00-Sistema/Configuracion.md`.
- El log de conversaciones ya no se usa como fuente de búsqueda (contaminaba
  las respuestas con charlas viejas), y los pendientes ya no se guardan por
  palabras clave.
- Clover (Gemini) recibe su personalidad, tu perfil y tus pendientes en el
  prompt, pero todavía no tiene herramientas.
- La voz ya no lee markdown, viñetas ni emojis (`limpiar_para_voz` en `src/voice/tts.py`).

**Voces distintas por motor:** en el CLI de voz, cada motor puede tener su
propia voz de ElevenLabs — configurable con `ELEVENLABS_VOICE_ID_OLLAMA` y
`ELEVENLABS_VOICE_ID_GEMINI` en `.env` (cada una debe ser una voz que ya
esté en tu biblioteca "My Voices"; las cuentas gratuitas solo pueden usar
voces `premade`, no las de la Voice Library, vía API). Si no se configura
una específica, cae a `ELEVENLABS_VOICE_ID` genérica.

**Acciones sobre el sistema (Fase 4):** un comando tipo "abre la
calculadora" abre la app directamente (lista blanca fija en
`src/actions/system_control.py`, ampliable ahí mismo) — nunca pasa por
Ollama/Gemini, porque ellos no pueden ejecutar acciones reales. Un comando
tipo "busca en internet..." activa el grounding con Google Search de
Gemini para respuestas basadas en resultados reales, no solo en su
conocimiento estático. **Toda acción (abrir una app) pide confirmación
explícita antes de ejecutarse** — por texto en el CLI de texto, por voz
("di sí o no") en el CLI de voz.

**Búsqueda web auxiliar para Ollama:** Ollama no tiene acceso nativo a
internet (a diferencia de Gemini). Cuando un comando de búsqueda termina
respondiéndolo Ollama (router lo eligió, o Gemini falló y cayó aquí como
fallback — el caso típico sin facturación configurada en Gemini), se le
inyectan resultados reales de DuckDuckGo (`src/actions/busqueda_web.py`,
sin API key ni costo) como contexto adicional.

**Métricas de uso (Fase 5):**
```bash
python -m src.main_metricas
```
Lee el log de interacciones ya guardado en la bóveda (`00-Sistema/Logs-Interacciones.md`)
y reporta qué % de las respuestas resolvió cada motor, más la tasa de
éxito real de Gemini (cuenta también sus fallos, no solo cuando cae a
Ollama) — útil para decidir si vale la pena ajustar las palabras clave del
router según el uso real.

**UI de escritorio:**
```bash
python -m src.main_ui
```
Ventana con [Flet](https://flet.dev) (renderiza con Flutter, sin HTML/JS
ni servidor separado), con dos apartados en la barra inferior:

- **Voz:** el agente elegido aparece como un orbe animado en el centro
  (Crimson carmesí, Clover violeta, Jarvis azul). Cuando el agente
  responde, el orbe brilla con el color de quien realmente habló.
  - **Activación por nombre** (interruptor, encendido por defecto): di
    "Crimson", "Clover" o "Jarvis" (solo o seguido de lo que quieres, ej.
    "Crimson, ¿qué pendientes tengo?"). Eso abre una **ventana de
    conversación de 1 minuto**: mientras sigas hablando no hace falta
    repetir el nombre, y cada frase reinicia el minuto. Tras un minuto en
    silencio hay que volver a llamarlo. Decir otro nombre le pasa la
    palabra a ese agente. El orbe brilla un poco más mientras la ventana
    está abierta, y el estado muestra los segundos que quedan.
  - El nombre lo detecta Whisper (escucha continua + tolerancia a errores
    de transcripción como "Yarvis"/"Grimson"), así que usa algo de CPU y
    puede activarse si mencionas el nombre en una plática.
  - Mientras el agente piensa y habla, la escucha se pausa (si no, se
    oiría a sí mismo y se contestaría en bucle). Las confirmaciones
    (abrir apps) se responden por voz: "sí" o "no".
  - El micrófono manual sigue disponible: tocar para empezar, tocar para
    terminar.
- **Chat:** conversación por texto (incluye también lo dicho por voz).

Arriba se elige el agente a mano (o diciendo su nombre): **Crimson**
siempre usa Ollama, **Clover** siempre usa Gemini (con fallback a Ollama si
falla) y **Jarvis** deja que el router decida.

### Tests

```bash
pytest
```
