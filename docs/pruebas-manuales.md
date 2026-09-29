# Pruebas manuales

Para probar a mano, con tu voz y tus ojos, lo que los tests automáticos no pueden juzgar: si
suena natural, si la UI se siente bien y si las conexiones tienen sentido.

## Antes de empezar

1. `Jarvis.bat diagnostico`: todo en ✓ (el núcleo en "!" está bien si no lo iniciaste).
2. Para no tocar tu bóveda real: `Jarvis.bat pruebas` (reusa la bóveda de pruebas) o
   `Jarvis.bat pruebas-nueva` (la vuelve a crear con notas de ejemplo: Node.js, Express, Git,
   Bases de datos, Ollama, Jarvis, pendientes con fechas...). Arriba debe decir **MODO PRUEBAS**.
3. Si algo sale raro, anota la frase exacta que dijiste y lo que respondió.

## 1. Memoria: que responda con tus notas

En el chat o por voz, a Crimson:
- [ ] "¿Qué dicen mis notas sobre el event loop?" → responde con lo de tu nota de Node.js, sin
      tardar (primera oración en ~1-2 s).
- [ ] "¿Cómo se llamaba el framework que apunté para hacer APIs?" → Express (sin que digas la
      palabra).
- [ ] "¿Qué dice mi nota de física cuántica?" → dice que no tienes una; no inventa.
- [ ] "¿Qué tengo para hoy?" y "¿tengo algo atrasado?" → separa bien lo vencido de lo que
      todavía está a tiempo.

## 2. Gestión de notas

- [ ] "Crea una nota sobre TypeScript: es un superconjunto de JavaScript con tipos" → dice "Va,
      dame un segundito" al instante; la nota queda en `04-Conocimiento/Programación/`, aparece
      en el índice `Programación.md` y en su `## Relacionado` enlaza a Node.js.
- [ ] Pide crear la misma nota otra vez → dice que ya existe (no la sobrescribe ni la enlaza
      consigo misma).
- [ ] "Agrégale a mi nota de Node.js que el módulo fs lee archivos" → queda antes de
      `## Relacionado`.
- [ ] "Conecta mi nota de Jarvis con la de Ollama" → enlace con el motivo.
- [ ] "Mueve la nota de Git a Programación" o "renómbrala a Control de versiones" → los enlaces
      que apuntaban a ella se actualizan.
- [ ] "Elimina la nota de TypeScript" → pregunta mostrando la ruta real; con "no" no pasa nada;
      con "sí" va a la papelera de Windows y desaparece de los `## Relacionado` de otras notas.
- [ ] Crea una nota de un tema sin relación (ej. historia de One Piece) → no se conecta con nada.

## 3. Conexiones hechas por el núcleo

- [ ] Con el núcleo corriendo (Ajustes → Núcleo → Iniciar), escribe a mano en Obsidian una nota
      que mencione "Express" en `04-Conocimiento/`. Tras ~10 minutos sin tocarla, debe aparecer
      conectada y en el índice de su área; `00-Sistema/HEARTBEAT.md` lo cuenta.
- [ ] En la sección **Bóveda** de la app, las conexiones sugeridas tienen sentido y "Conectar"
      funciona.

## 4. Pendientes

- [ ] "Recuérdame comprar pilas el sábado a las 10am" → queda con 📅 y ⏰.
- [ ] "Pásame lo del reporte para mañana a las 5pm" → lo reprograma (no crea otro).
- [ ] "Ya llamé a mi mamá" → lo marca como hecho.
- [ ] En el panel **Hoy** de la app, marcar un pendiente con el círculo lo completa.

## 5. Voz y personalidad

- [ ] Las respuestas empiezan a sonar mientras se generan (sin esperar el final).
- [ ] Crimson suena cálida y con expresiones, sin repetir la misma en cada respuesta; Clover,
      sereno y seco. Ninguno cierra siempre con "¿necesitas algo más?".
- [ ] En Ajustes, prueba otras voces con el botón de bocina y cambia la velocidad; la siguiente
      respuesta ya usa la nueva.
- [ ] "Node.js", "GitHub", "Python" se entienden bien con las voces de México.
- [ ] Interrumpe al agente hablando o tocando el micrófono: se calla y te atiende.

## 6. La app

- [ ] Al abrir (una vez al día, si está activado): saludo con lo que tienes pendiente.
- [ ] Los indicadores de arriba (Crimson, Clover, Núcleo, Memoria) reflejan el estado real.
- [ ] **Uso**: conversaciones de hoy, tiempo de respuesta y cuota de Gemini se mueven al usar.
- [ ] **Ajustes → Diagnóstico → Revisar todo** muestra lo mismo que `Jarvis.bat diagnostico`.
- [ ] "Modo seguro" bloquea crear/editar/eliminar; "sal del modo seguro" lo quita.

## Al terminar

La bóveda de pruebas vive en `%LOCALAPPDATA%\kindred\boveda-pruebas`; `pruebas-nueva` la
recrea desde cero. Tu bóveda real no se tocó.
