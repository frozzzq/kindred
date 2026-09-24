# CLAUDE.md — Proyecto Jarvis (Agente de IA Personal)

> Este archivo es la guía de contexto para Claude Code. Léelo completo antes de generar código. El objetivo es construir el proyecto de forma incremental, empezando por un prototipo mínimo funcional (MVP) y creciendo desde ahí.

---

## 🎯 Qué estamos construyendo

Un asistente de voz personal tipo "Jarvis" que corre principalmente en local, con estas piezas:

- **STT** (voz → texto): Whisper local
- **TTS** (texto → voz): ElevenLabs
- **Motor local**: Ollama (mistral:7b) corriendo en una PC con GPU AMD RX 7500, expuesto en red local vía `OLLAMA_HOST=0.0.0.0:11434`
- **Motor en la nube**: Gemini 2.5 Flash / Flash-Lite (API de Google AI Studio), para tareas complejas
- **Memoria / segundo cerebro**: una bóveda de Obsidian (archivos Markdown) que ambos motores pueden leer y escribir
- **Orquestador**: un servicio Python que recibe el comando de voz, decide qué motor usar, ejecuta acciones y responde

El agente correrá con el orquestador hosteado en un **servidor Proxmox** (Xeon E5-2680 v4, 24GB RAM) y Ollama corriendo remotamente en una **PC con GPU RX 7500** en la misma red local.

---

## 🧠 Lógica central: Router de intención

Todo comando de voz pasa por un router que decide el motor:

1. **Comando SIMPLE** (pendientes, recordatorios, notas, preguntas sobre contexto ya guardado en Obsidian) → **Ollama + RAG sobre Obsidian**
2. **Comando COMPLEJO** (buscar en internet, abrir apps, gestionar cuentas, contestar mensajes, analizar/resumir) → **Gemini Flash**
3. Si Gemini no tiene cuota o no hay internet → fallback a Ollama con aviso al usuario
4. Después de cualquier respuesta relevante → evaluar si se debe guardar/actualizar algo en la bóveda de Obsidian

Este comportamiento debe quedar aislado en un módulo propio (`router/` o similar) para poder ajustarlo sin tocar el resto del sistema.

---

## 🏗️ Fases de desarrollo (construir en este orden)

### Fase 0 — Setup del repositorio
- Estructura de carpetas inicial (ver abajo)
- Entorno virtual / gestión de dependencias (Python)
- Archivo `.env.example` con las variables necesarias (API keys, IP de Ollama, ruta de la bóveda)
- `README.md` básico

### Fase 1 — Prototipo mínimo (sin voz todavía)
- Cliente que llama a Ollama local (vía HTTP a `http://<ip-pc>:11434`)
- Cliente que llama a Gemini Flash (API de Google AI Studio)
- Router de intención muy simple (basado en palabras clave, sin IA todavía)
- Todo interactuando por texto en terminal (CLI de prueba)

### Fase 2 — Integración con Obsidian
- Módulo para leer/escribir notas Markdown en la bóveda
- Búsqueda simple por palabras clave dentro de la bóveda (luego se puede mejorar a embeddings)
- El router empieza a inyectar contexto de Obsidian en los prompts de Ollama y Gemini
- Definir la estructura de carpetas de la bóveda (ver sección abajo)

### Fase 3 — Voz
- Integrar Whisper (STT) para escuchar comandos
- Integrar ElevenLabs (TTS) para responder
- Wake word / activación (a definir la librería)

### Fase 4 — Control del sistema y acciones
- Ejecutar acciones en la PC (abrir apps, clicks, escritura)
- Acceso a APIs externas (búsqueda web, redes sociales, correo)
- Sistema de confirmación para acciones críticas (borrar, enviar mensajes, comprar)

### Fase 5 — Pulido y evolución
- Logs de interacciones y métricas (qué % resuelve Ollama vs Gemini)
- Ajustar el router según el uso real
- UI (se definirá después, no es parte de este alcance por ahora)

**Empieza por la Fase 0 y Fase 1. No avances a fases posteriores hasta que las anteriores funcionen y estén confirmadas.**

---

## 📂 Estructura de carpetas propuesta para el repositorio

```
jarvis-agent/
├─ README.md
├─ CLAUDE.md                  # este archivo
├─ .env.example
├─ requirements.txt
├─ src/
│  ├─ main.py                 # punto de entrada
│  ├─ router/
│  │  └─ intent_router.py     # decide Ollama vs Gemini
│  ├─ engines/
│  │  ├─ ollama_client.py     # cliente HTTP a Ollama remoto
│  │  └─ gemini_client.py     # cliente API de Gemini
│  ├─ obsidian/
│  │  ├─ vault_reader.py      # lee notas de la bóveda
│  │  └─ vault_writer.py      # crea/actualiza notas
│  ├─ voice/
│  │  ├─ stt.py               # Whisper
│  │  └─ tts.py                # ElevenLabs
│  └─ actions/
│     └─ system_control.py    # abrir apps, clicks, etc (fase 4)
├─ tests/
└─ docs/
   └─ arquitectura.md          # referencia, ya generada aparte
```

Ajusta nombres si tiene más sentido, pero mantén la separación por responsabilidad: router, engines, obsidian, voice, actions.

---

## 📂 Estructura de la bóveda de Obsidian (segundo cerebro)

```
Obsidian Vault/
├─ 00-Sistema/
│  ├─ Configuracion.md
│  └─ Logs-Interacciones.md
├─ 01-Perfil/
│  ├─ Yo.md
│  ├─ Contactos.md
│  └─ Patrones.md
├─ 02-Tareas/
│  ├─ Pendientes.md
│  ├─ Completadas.md
│  └─ Recurrentes.md
├─ 03-Proyectos/
├─ 04-Conocimiento/
└─ 05-Decisiones/
```

La ruta local de la bóveda debe ser configurable vía variable de entorno (`OBSIDIAN_VAULT_PATH`), no hardcodeada.

---

## 🔑 Variables de entorno necesarias

```
OLLAMA_HOST=http://<ip-de-la-pc>:11434
OLLAMA_MODEL=mistral:7b

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite

ELEVENLABS_API_KEY=

OBSIDIAN_VAULT_PATH=/ruta/a/la/boveda

GEMINI_DAILY_QUOTA=1000
```

Crea `.env.example` con estas claves (sin valores reales) y asegúrate de que `.env` esté en `.gitignore`.

---

## ⚙️ Convenciones y buenas prácticas

- Python 3.11+
- Usar `requests` o `httpx` para llamadas HTTP (Ollama y Gemini)
- Manejo de errores explícito: si Ollama o Gemini fallan, debe haber fallback y no un crash
- No exponer API keys en el código, siempre vía `.env`
- Cada módulo debe ser testeable de forma aislada (permitir mockear Ollama/Gemini en tests)
- Comentarios y nombres de funciones en español o inglés, pero consistente en todo el proyecto (decide uno y mantente)
- Commits pequeños y descriptivos si se usa git desde el inicio

---

## 🚫 Fuera de alcance por ahora

- UI gráfica (se definirá en una fase posterior)
- Wake word avanzado / multi-idioma
- Fine-tuning de modelos
- Despliegue en producción / multiusuario

---

## ✅ Primer objetivo concreto para esta sesión

1. Crear la estructura de carpetas del repositorio (Fase 0)
2. Crear `ollama_client.py` que pueda mandar un prompt a Ollama remoto y regresar la respuesta
3. Crear `gemini_client.py` que pueda mandar un prompt a Gemini Flash y regresar la respuesta
4. Crear un `main.py` simple que, por CLI, reciba texto, decida con un router básico (por palabras clave) cuál motor usar, y muestre la respuesta

No avances más allá de esto sin confirmar que funciona.
