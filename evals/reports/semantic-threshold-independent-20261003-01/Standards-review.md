# Standards review

Base `9e1ae5e58981c6ce0d45c236032a17ad6dcd60db`; commit `1af809fd209c4260d5314ff55fa090147515b8d0`.

**Cero infracciones documentadas y cero hallazgos de diseño accionables.** Criterios aplicados: `AGENTS.md` y `RTK.md` (aislamiento, datos y secretos preservados, comandos RTK), `numerical-care/SKILL.md` (representación y límites numéricos), `llm-app-code/SKILL.md` (salidas no confiables y decisiones deterministas), más el baseline de olores de `code-review/SKILL.md`. Se revisaron ambos ejes sin crear nuevos agentes.

La conversión decimal está junto a los dos puntos de decisión afectados. No requiere una abstracción compartida para unas operaciones tan cortas y distintas: límite de cada señal semántica frente a cola ordinal de varias categorías. La decisión semántica deriva de la misma lista que alimenta el segundo intento; evita que aceptación y diagnóstico discrepen. Las comprobaciones existentes de tipos, finitud y rango no se eliminan.

Los tests añadidos usan las tres entradas HTTP, respuestas sintéticas, flotantes adyacentes y las instrucciones de corrección; comprueban comportamiento relevante para el defecto. No atribuyen calidad real a fixtures. La revisión independiente añade replay de señales históricas, colas ordinales con varias masas y segundo intento completado en los tres HTTP.

Distinción de evidencia: los logs del implementador muestran **4 tests / 8 fallos** en rojo, **4 tests verdes** y **94 tests focales verdes**. Son evidencia leída, no ejecuciones propias. La ejecución propia aislada tiene **3 tests verdes**, seis peticiones HTTP, nueve comparaciones adyacentes, 24 clasificaciones y 11 verificaciones históricas. Registro completo, comandos y hashes en `preparation.json`, `run-result.json`, `observations.json` y `evidence.json`.

No se modificaron checkout, índice, corpus, manifiestos, ledger persistente, credenciales ni informes previos. Las dependencias ya instaladas se usaron desde el entorno local, sin descargas. La validación no sustituye las puertas generales que ejecuta el orquestador ni autoriza más llamadas pagadas.
