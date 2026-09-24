# kindred

Asistentes IA para uso personal.

## Jarvis

Asistente de voz personal local-first. Ver [CLAUDE.md](CLAUDE.md) para la
arquitectura completa y el plan de fases.

Estado actual: **Fase 0 + Fase 1 + Fase 2 + Fase 3 (completa, con wake
word) + Fase 4 (parcial) + Fase 5 (parcial)** (scaffold, MVP por CLI de
texto con Ollama/Gemini, integración con una bóveda de Obsidian como
memoria, voz con Whisper local + ElevenLabs — push-to-talk o manos libres
con wake word "hey jarvis" —, control del sistema: abrir aplicaciones y
búsqueda web con confirmación obligatoria, y métricas de uso). Sin
clicks/escritura automática, correo/redes sociales, ni UI todavía.

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
las acciones del sistema como **Jarvis**. Es solo cosmético — internamente
siguen siendo `ollama`/`gemini`/`accion`, así que no afecta logs, `.env`
ni tests. Se define en `NOMBRES_MOTOR` (`src/router/intent_router.py`).

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

### Tests

```bash
pytest
```
