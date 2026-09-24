# kindred

Asistentes IA para uso personal.

## Jarvis

Asistente de voz personal local-first. Ver [CLAUDE.md](CLAUDE.md) para la
arquitectura completa y el plan de fases.

Estado actual: **Fase 0 + Fase 1 + Fase 2** (scaffold, MVP por CLI de texto
con Ollama/Gemini, e integración con una bóveda de Obsidian como memoria:
búsqueda de contexto en las notas antes de responder, y registro automático
de interacciones/pendientes). Sin voz todavía (Fase 3).

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env      # y completar con tus valores reales
```

### Uso

```bash
python -m src.main
```

Escribe un comando simple (va a Ollama) o uno complejo, p. ej. "busca en
internet..." (va a Gemini, con fallback automático a Ollama si falla).

### Tests

```bash
pytest
```
