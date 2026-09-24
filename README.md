# kindred

Asistentes IA para uso personal.

## Jarvis

Asistente de voz personal local-first. Ver [CLAUDE.md](CLAUDE.md) para la
arquitectura completa y el plan de fases.

Estado actual: **Fase 0 + Fase 1 + Fase 2 + Fase 3 + Fase 4 (parcial)**
(scaffold, MVP por CLI de texto con Ollama/Gemini, integración con una
bóveda de Obsidian como memoria, voz con Whisper local + ElevenLabs en
modo push-to-talk, y control del sistema: abrir aplicaciones y búsqueda
web real con Gemini, ambos con confirmación obligatoria antes de
ejecutar). Sin wake word, clicks/escritura automática, ni correo/redes
sociales todavía.

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

En ambos casos, un comando simple va a Ollama y uno complejo (p. ej. "busca
en internet...") va a Gemini, con fallback automático a Ollama si falla.

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

### Tests

```bash
pytest
```
