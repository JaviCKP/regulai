# Revisión independiente de utilidad y requisitos — 3940fdc

Estado: revisión inicial completa sobre el commit fijo; pendiente de nueva integración, selección y liberación final del reservado. Esta revisión no autoriza por sí sola afirmar una mejora general ni sustituye la revisión de seguridad/presupuesto.

Revisor: agente nuevo `utility_final`, separado de los implementadores. Es revisión por agente, sin participantes humanos. Base `9d7f9424a70143614c9d673e64ebed9723ff3439`; candidato revisado `3940fdc698c34998b2541309b0b697b6c06c2287`. Se leyó el encargo original, AGENTS/RTK, glosario, planes 05/06/07/11/12, tareas 32–35, informe adversarial anterior, corpus público, código pertinente y evidencias nuevas. La skill code-review se aplicó sólo al eje de requisitos: este encargo ya asigna revisores separados y prohíbe nuevos subagentes.

El reservado y el generador que contiene sus literales permanecen cerrados. No se ejecutó `validate_calibration_corpus.py`, porque incluso `--public-only` importa ese generador para aritmética. La sonda independiente implementa una gramática AST limitada, sin importar el generador. No hubo red, llamadas de producto, apertura de base del usuario, edición de runtime ni commits del revisor.

## Hallazgo que requiere una corrección de informe o agregación

**U1, P2 — La agregación omite métricas necesarias para distinguir corrección retenida de beneficio entregado.** En `regulai/front/evaluation.py:827`, `summarize_calibration` agrega `second_attempt_corrected` y `second_attempt_introduced`, pero omite `second_attempt_delivered_correction`, `second_attempt_equivalent`, ataques que llegaron/no llegaron al generador, citas inválidas entregadas y afirmaciones entregadas sin respaldo. Estos campos sí existen por caso. El encargo exige publicación por caso y agregado y separación entre calidad retenida y utilidad entregada.

Reproducción nueva: `metric_probe.py` ejecuta las tres funciones extraídas del AST del archivo revisado, sin Django, red o bases. Una primera respuesta 41 y segunda 42, ambas retenidas, producen correctamente `second_attempt_corrected=true` y `second_attempt_delivered_correction=false`; el resumen sólo expone el primer 1/1. No es una llamada real ni un resultado semántico del proveedor. Se comprueba asimismo que fixtures, referencias `contains` y prosa numérica no se convierten en aciertos deterministas. Exit 0; cuatro comprobaciones. Fuente exacta SHA-256 `adbfee978d6c1750ea6fe2ba4f1082d2edef11eee035f42296323799c5b0c38e`, igual a los bytes de `3940fdc`.

Corrección concreta: incluir los campos omitidos con denominador medido y nulo explícito cuando no haya observación, o completar esos agregados en un nuevo informe de análisis. Conservar los resultados originales y no convertir `contains` en corrección completa. Añadir una regresión que contraste corrección retenida con entrega falsa. No hace falta repetir llamadas de proveedor para recalcular agregados de capturas existentes.

## Requisitos incompletos y limitaciones de selección

1. **Independencia de al menos 1.500 familias: incompleta.** Los 2.043 grupos operativos tienen reglas reproducibles de agrupación, pero los umbrales léxicos y las etiquetas de subtipo no acreditan independencia semántica. El README y el borrador principal lo declaran correctamente. No se exige un estudio humano inventado: una revisión por agentes de la independencia y una agrupación más sólida podrían aportar evidencia; hasta entonces no dar este objetivo por completado. No modificar familias u oráculos tras mirar el reservado para conseguir el número exigido.
2. **Cobertura documental y de longitud de la confirmación: insuficiente.** El manifiesto deja un documental en validación y uno en reservado, y cero casos `very_long` en ambos. Los 788 documentales de plantilla y 200 PII de registro quedaron juntos en desarrollo, preservando la separación. El reparto por familias sí se aproxima a 60/20/20; el problema es la escasa diversidad para confirmar esos comportamientos. Las cuotas globales no subsanan esa falta de cobertura. Una ampliación posterior necesita nuevas familias y una nueva partición congelada, sin presentar como no vistos casos ya examinados.
3. **Selección de utilidad: provisional.** Los 33 valores adicionales ocultados en desarrollo pertenecen a una familia; validación empata; HTTP empata. La máscara v5 tiene mejora local observada y ninguna pérdida nueva en estas anotaciones, pero no hay 33 confirmaciones independientes ni prueba de mejora de entrega. Aplicar el orden preregistrado: invariantes, aciertos entregados/cobertura y después coste/latencia. Un empate semántico conserva la base o la configuración más simple; se puede distinguir una corrección local de privacidad de una calibración semántica todavía experimental.
4. **Métricas de entidad y semántica: parciales.** El arnés mide desaparición/preservación literal de valores, no precisión/recobrado exhaustivos ni ausencia de sufijos filtrados. Publica `null` para calidad de fixtures y referencias no adjudicables. La sonda pública encuentra 525 casos `manual`, 217 `abstain` y 1.612 `contains`; estas referencias no deben transformarse automáticamente en respuestas completamente correctas. Las partes sin referencia suficiente quedan sin resolver.
5. **Formato documental y NER: abiertos, no regresiones nuevas demostradas del diff.** El lote vivo base muestra el conflicto entre el objeto JSON solicitado por D0452 y el contrato documental obligatorio. Strong devuelve campos/valores solicitados y se rechaza por `invalid_document_structure`; economy/router devuelven claims con valores y citas, sin el formato pedido. Router repite sus bytes. No clasificar todos esos rechazos como error de Jev, RAG universal o éxito factual completo. Los falsos positivos del NER y las pérdidas de citas siguen observados con ambas máscaras.

## Evidencia independiente y denominadores

`public-audit.json` conserva los hashes de las fuentes leídas y los artefactos revisados. La sonda propia comprueba 3.433 casos públicos, 990 documentos, 2.095 spans sensibles, 2.000 spans a conservar y 321 referencias numéricas; no encuentra fallos de hash, spans, evidencia literal, duplicados de solicitud pública, aritmética o cruce público de familias. Las 17 descargas fijadas coinciden en tamaño/hash. El banco histórico mantiene SHA-256 `1576e3128bdf1257dbd437396cdfa6f2e39b1a58a79a1111824ed7f6ced8456e`.

| Evidencia | Base | Candidato | Alcance válido |
| --- | ---: | ---: | --- |
| Desarrollo: valores ocultados | 1.201/1.572 | 1.234/1.572 | Anotaciones literales; 2.813 casos, 1.250 grupos |
| Desarrollo: texto conservado | 1.716/1.742 | 1.716/1.742 | Cero pérdidas nuevas en las anotaciones |
| Desarrollo HTTP | 51/60 | 51/60 | 10 casos × 3 HTTP × 2 perfiles simulados |
| Validación: valores ocultados | 423/523 | 423/523 | 620 casos, 421 grupos; empate |
| Validación: texto conservado | 246/258 | 246/258 | 12 pérdidas anotadas en ambos |
| Validación HTTP | 54/60 | 54/60 | 10 casos × 3 HTTP × 2 perfiles simulados |
| Histórico nuevo: valores ocultados | 27/32 | 31/32 | 44 regresiones conocidas; no conjunto no visto |
| Histórico nuevo: texto conservado / HTTP | 61/66; 258/264 | 61/66; 258/264 | Citas/contextos dañados no se ocultan como éxitos |

Los hashes de los cuatro runs locales, sus comparaciones y logs de puertas coinciden. Las fuentes de `plan.json` fijan el runtime de cada ejecución; las reparaciones posteriores de instrumentación no convierten retroactivamente las ejecuciones antiguas en pruebas de ese código posterior.

La revisión de `baseline-smoke-02/live-run-01` se registra separadamente en `live-baseline-review-02.json`: 12 ejecuciones reales de 4 familias, 0 entregas, 9 bloqueos y 3 fallos. Son 12 clasificaciones, 4 generaciones y 3 juicios: los 19 `body_utf8` capturados no contienen los IDs de los cuatro casos ni campos de etiquetas/oráculos del banco. La comprobación no afirma ausencia universal de metadatos de cualquier clase. Tres configuraciones de un ataque detenido constituyen una familia; no miden resistencia del generador. El único segundo intento observado es idéntico y sin entrega.

La primera sonda de cuerpos buscó un nombre de campo incorrecto y no midió las fugas. Se conserva como sustituida en `live-baseline-review-superseded.json`; sólo la ejecución 02, que exige un cuerpo en cada registro y declara N=19, sustenta la conclusión sobre marcadores. No se alteró ninguna captura del producto.

## Estado por requisito del encargo al cerrar esta revisión inicial

| Objetivo | Estado observado | Evidencia / límite |
| --- | --- | --- |
| Núcleo 4.000 + históricos intactos, categorías y 500 negativos difíciles | Preparado; público verificado, reservado aún cerrado | Manifiesto 4.004, auditoría pública 3.433; custodia conserva el resto |
| ≥1.500 familias independientes | Incompleto | 2.043 grupos operativos no acreditan independencia fuerte |
| ≥60 % español, bandas 25/35/30/10 | Preparado con comprobación léxica declarada | 2.632 etiquetas; 2.529/4.004 tras excluir ambiguos; no adjudicación humana |
| ≥200 documentos, siete formatos y cobertura honesta | Verificado en manifiesto y fuentes públicas | 1.181 distintos; 990 hashes públicos; Office creado con bibliotecas y OCR ausente explícitos |
| Fuentes, revisiones y licencias | Verificado documentalmente | 17 bytes descargados coinciden; BIPIA por componente; PINT sólo ejemplos disponibles; deepset excluido |
| Oráculos, spans y aritmética anteriores a medida | Público verificado, reservado pendiente de liberación | 321 referencias públicas verificadas sin ejecutar el generador; referencias manuales no se fuerzan |
| Entradas sin IDs/etiquetas del benchmark | Verificado en allowlist y muestra de transporte | 19 cuerpos vivos de cuatro casos; el resultado no generaliza fuera de lo inspeccionado |
| Particiones y reservado sin contaminación | Público verificado; custodia reservada pendiente | No se abrió reservado, originales reservados, muestras reservadas ni generador |
| Rondas, candidatos rechazados y conservación de evidencia | Verificado para R1–R3 | Regresión de secretos Unicode de v3/v4 descartada; v5 une coincidencias originales |
| HTTP y frontera de transporte; fixtures separados | Verificado para muestras declaradas | 60+60 controles por variante; 264 históricos; fixtures no son DeepSeek/Jev |
| Comparación real base/candidato y economy/strong/router | En ejecución del coordinador | Base viva verificada; candidato/confirmación todavía no revisados en esta versión |
| Entrega vs retención, denominadores y reintentos | Parcial; U1 abierto | Funciones por caso correctas en sonda; agregados omitidos; retry vivo sin beneficio |
| Precisión/recobrado completos, falsos positivos semánticos, citas y respaldo | Incompleto, declarado | Anotaciones parciales y muestra semántica pequeña; no inventar resultados faltantes |
| Revisión independiente | Esta parte realizada sobre SHA fijo | Pendiente nueva revisión tras cambios anunciados por root |
| Cinco puertas | Verificadas por artefactos sobre 3940fdc | 446 tests: 444 correctos + 2 expectedFailure; check/migraciones/150 offline/dependencias exit 0 |
| Balance final y configuración final | Pendiente del coordinador | No se abre ni modifica ledger desde esta revisión; evaluación seguridad/presupuesto separada |

## Comandos propios relevantes

Todos con salida 0, salvo que se indique otra cosa; ningún comando inicia llamadas de proveedor.

```text
rtk git rev-parse 9d7f942 3940fdc HEAD
rtk git log --oneline 9d7f942..3940fdc
rtk git diff --stat 9d7f942...3940fdc -- regulai scripts ":(exclude)scripts/build_calibration_corpus.py"
rtk git diff 9d7f942...3940fdc -- regulai/front/local_masking.py
rtk proxy python evals/calibration/calibration-20261004-01/reviews/utility-final/review_probe.py
rtk proxy python evals/calibration/calibration-20261004-01/reviews/utility-final/metric_probe.py
rtk proxy python evals/calibration/calibration-20261004-01/reviews/utility-final/provenance_probe.py
rtk proxy python evals/calibration/calibration-20261004-01/reviews/utility-final/review_live_baseline.py
```

`public-audit.json` SHA-256 al producirlo: `0f190055cd0fbb98c29946380b376dee534e024b633cfd7e04c52c92792934ee`. Las sondas son una revisión de evidencias y funciones concretas, no nuevas ejecuciones del corpus contra el producto. Los comandos y hashes de las cinco puertas son los registrados por el coordinador y contrastados en esta revisión; no se suman sus tests a las cuatro comprobaciones propias.
