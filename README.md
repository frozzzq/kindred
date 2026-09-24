# kindred

Asistentes IA para uso personal.

## Jarvis

Asistente de voz personal local-first. Ver [CLAUDE.md](CLAUDE.md) para la
arquitectura completa y el plan de fases.

Estado actual: **Fase 0 + Fase 1 + Fase 2 + Fase 3** (scaffold, MVP por CLI
de texto con Ollama/Gemini, integración con una bóveda de Obsidian como
memoria, y voz con Whisper local + ElevenLabs en modo push-to-talk, sin
wake word todavía).

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
esté en tu biblioteca "My Voices"; las cuentas gratuitas no pueden usar
voces de la librería general vía API). Si no se configura una específica,
cae a `ELEVENLABS_VOICE_ID` genérica.

### Tests

```bash
pytest
```
