# kindred

Asistentes IA para uso personal.

## Jarvis: Crimson y Clover

Asistente de voz personal, local primero, con dos agentes y una memoria en Obsidian. Ver
[CLAUDE.md](CLAUDE.md) para la arquitectura completa y el plan de fases, y
[docs/arquitectura.md](docs/arquitectura.md) para el diagrama.

- **Crimson**: Ollama local (`qwen3:8b`) en la GPU. Cálida, mexicana, con chispa.
- **Clover**: Gemini Flash, para tareas complejas y búsqueda web. Sereno, preciso, humor seco.
- **Memoria**: tu bóveda de Obsidian, con un índice semántico que les da las notas relevantes en
  cada mensaje, conexiones automáticas entre notas del mismo tema y un diario del día.
- **Voz**: faster-whisper (entender) + edge-tts (hablar), en vivo oración por oración.
- **UI de escritorio** (Flet) con el agente como grafo 3D de tu bóveda, chat, panel de la
  bóveda, métricas de uso y ajustes.

### Empezar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-lock.txt     # o requirements-dev.txt para desarrollo (trae pytest)
copy .env.example .env                   # y completa tus valores
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b         # memoria semántica (sin él, busca solo por palabras)
```

Después, **todo se abre con `Jarvis.bat`** (doble clic): un menú con

| Opción | Qué hace |
|---|---|
| `ui` | La app: voz, chat, bóveda, uso y ajustes |
| `texto`, `voz`, `manos-libres` | Los modos de consola |
| `nucleo` | Recordatorios, briefing, diario y orden de la bóveda en esta ventana |
| `pruebas` / `pruebas-nueva` | La app con una **bóveda de pruebas** (no toca la tuya) |
| `evaluar` | Pone a prueba a los agentes con escenarios reales y mide tiempos |
| `diagnostico` | Revisa Ollama, modelos, Gemini, bóveda, índice, micrófono, voz y núcleo |
| `tests` | Los tests automáticos |
| `indexar`, `metricas` | Reindexar la bóveda; métricas en consola |

También directo: `Jarvis.bat ui --seccion uso`, `Jarvis.bat texto --pruebas`.

### Qué pueden hacer

**Responder sobre tus notas sin tener que buscarlas.** En cada mensaje reciben la hora, tus
pendientes agrupados por urgencia (vencidos, hoy, próximos) y las notas de tu bóveda que tratan
lo que preguntas, encontradas por significado: "¿cómo se llamaba el framework que apunté para
hacer APIs?" encuentra tu nota de Express aunque no digas "Express". Si no tienes nada de eso,
lo dicen en vez de inventar.

**Gestionar la bóveda completa**: crear notas (caen solas en la carpeta de su tema y se agregan
al índice del área), agregar a una nota, editarla (con respaldo de la versión anterior), moverla
o renombrarla (actualiza los enlaces), conectar y desconectar notas, sugerir conexiones y
eliminar (a la papelera, con confirmación). Pendientes con fecha en lenguaje natural,
reprogramarlos, completarlos, tareas recurrentes, perfil y contactos.

**Conectar notas de verdad.** Dos notas se enlazan si una menciona a la otra por su título (como
las "menciones sin enlazar" de Obsidian) o si comparten un fragmento muy parecido (similitud
semántica ≥ 0.50, calibrada con el modelo real: Node.js ↔ Express 0.71, Jarvis ↔ Ollama 0.57,
pero Jarvis ↔ Express 0.42 no). Nunca con notas del sistema ni listas de tareas. El núcleo
conecta también las notas que escribes a mano en Obsidian.

**Ser proactivos.** Saludo del día al abrir la app con lo que tienes pendiente, aviso de lo
vencido al empezar una conversación, recordatorios a la hora, briefing de la mañana, cierre del
día y un diario automático (`06-Diario/`), que después puedes consultar ("¿qué hice ayer?").

**Actuar en tu PC**: abrir cualquier app instalada ("abre fotoshop"), páginas y carpetas; hacer
click y escribir en la ventana activa. Todo pasa por un registro de herramientas con permisos:
lo irreversible pide confirmación, "modo seguro" bloquea las acciones y todo queda en
`00-Sistema/Registro-Acciones.md`.

### Velocidad

Medido en la PC (RX 7600, ROCm): Crimson dice su primera oración en ~1-2 s en preguntas sobre
tus notas. Lo que más pesa:
- **Streaming**: la voz empieza con la primera oración mientras el resto se genera.
- **Contexto antes que herramientas**: las notas relevantes ya vienen en el mensaje, sin una
  vuelta extra del modelo.
- **Caché de Ollama**: el prompt de sistema no cambia entre turnos (la hora va en el mensaje);
  procesarlo en frío costaba ~1.7 s y desde caché ~0.06 s.
- **Prompt compacto**: en esta GPU la generación baja de 38 a 13 tokens/s al pasar de 150 a
  4000 tokens de contexto, así que reglas y herramientas están escritas cortas, y a Crimson solo
  se le dan los grupos de herramientas que el mensaje pide.
- **Precalentar**: la app carga el modelo al abrir y el keep-alive es de 3 h (una recarga cuesta
  ~35 s).
- **Acuse inmediato**: si le pides una acción ("crea una nota..."), dice "Va, dame un segundito"
  al instante en vez de quedarse callada mientras escribe la nota.

### Voz y personalidad

Las voces se eligen en **Ajustes** (con botón para escucharlas) y la velocidad de cada una. Por
defecto: Dalia (Crimson) y Jorge (Clover), de México. Pronuncian el español nativo y los
términos en inglés se corrigen con un diccionario (Node.js ya no suena "nota jazz"). Las voces
"multilingües" (las de Copilot) son más expresivas, pero leen con acento en inglés las frases
cortas en español ("¡Órale, Josué!"). Por eso quedan como opción experimental.

### Pruebas

- `Jarvis.bat tests`: la suite automática (todo se prueba con Ollama, Gemini y audio simulados).
- `Jarvis.bat evaluar`: escenarios reales contra los modelos reales sobre una bóveda de ejemplo
  (preguntas sobre notas, crear, conectar, completar, reprogramar...), con aciertos y tiempos.
- `Jarvis.bat pruebas`: la app completa con la bóveda de pruebas (`%LOCALAPPDATA%\kindred\boveda-pruebas`).
- Guía para probar a mano: [docs/pruebas-manuales.md](docs/pruebas-manuales.md).

### Dónde queda cada cosa

- Bóveda: `OBSIDIAN_VAULT_PATH` (ver estructura en CLAUDE.md).
- Estado técnico, índice, ajustes, respaldos y log del núcleo: `%LOCALAPPDATA%\kindred\`.
- `requirements-lock.txt` fija las versiones; regenerarlo tras cambiar dependencias:
  `.venv\Scripts\python.exe -m pip freeze > requirements-lock.txt`.
