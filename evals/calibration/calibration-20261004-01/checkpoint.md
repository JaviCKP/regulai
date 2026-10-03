# Checkpoint — calibration-20261004-01

Inicio 2026-10-03T23:12:23Z (4 octubre en Madrid); ventana de nuevas llamadas hasta 2026-10-04T23:12:23Z. Techo conjunto 2 EUR incluyendo exposición histórica. Sin nuevas llamadas hasta reconciliar ledger, FX, tarifas, manifiestos y pruebas.

Base observada `9d7f942`, runtime anterior `1af809f`; Git tracked limpio. Preservar MESAS_RETIRO.pdf, plantilla.pdf, plantillaInformeTecnica.pdf, docs/brainstorming-regulae-vigia13-2026-10-02.md, docs/plan-blackhat/prompt-validacion-piloto-astra-max.md. No parar procesos ajenos. No escribir DB usuario ni mostrar secretos. Todos comandos shell con rtk.

## Propiedad y contrato acordado

- A `corpus`: corpus/**, scripts/build_calibration_corpus.py y auxiliares exclusivos, tarea37. Custodia del reservado; sólo hashes/esquema antes de final.
- B `privacy`: local_masking.py, classification.py, test_calibration_privacy.py, privacy/**, tarea38. Propone cambios antes de editar runtime; no cambia servicio/política.
- C `evaluation`: evaluation.py, evaluation_budget.py, test_calibration_evaluation.py, test_calibration_budget.py, scripts/calibration_local_checks.py, evaluation/**, tarea39. Sin mutar ledger real; propone interfaz antes.
- Root: chat_service.py, verification.py, política compartida, ejecutor scripts/run_calibration_campaign.py, integración, preregistro, tarea36, informe final y nuevas revisiones independientes.

Todos los spawn aceptaron `model=gpt-6-astra`, `reasoning_effort=max`, `fork_turns=none`. Modelo root no verificable. Máximo cuatro agentes activos. Commits serializados por root con rutas explícitas; nunca git add global.

Interfaz corpus acordada: JSONL v2 por development/validation/reserved; campos compatibles históricos, familia/plantilla, prompt/history/documents, clasificación/acción/oráculo, redactions/preserve/evidence/provenance/length. API load_partition development/validation; provider_input whitelist sin metadatos; verify_integrity sin revelar reservado. Bandas preregistradas 256/2048/16384/65536 bytes; casos por encima de límites reales sólo locales.

## Estado

- Lectura inicial realizada, planes05/06/07/11/12 y tareas32–35; informes históricos son antecedentes.
- Rondas/candidatos: ninguno medido todavía. Sin cambios de umbrales/rúbrica.
- Nuevas llamadas: 0; coste nuevo 0; exposición y saldo actuales pendientes de lectura segura del ledger por C.
- A investigando fuentes y corpus; B reproducciones privacidad/clasificación; C presupuesto e instrumentación.
- Root congela base, verifica tarifas/FX y estudia verificador/ejecutor vigente.

## Actualización durante implementación

- Snapshot base 620 archivos: `.claude/calibration-20261004-01-baseline`, archivo ZIP SHA256 `9be15667a063754b61a4dc87d099e3fd1d16718c63f2c01e02dec0b36f8a2688`. Manifest `baseline.json`; detector base retenido en `runtime-snapshots/base/local_masking.py`.
- Nueva ejecución completa base `baseline-run-01`: 44 casos detector (37 completos, 27/32 valores ocultos, 61/66 conservados), 264 recorridos HTTP (258 controles), red externa0, integridad correcta. Resultados anteriores intactos.
- Ledger RO confirmado por C: 110 entradas, 109 completed y1 outcome_unknown; exposición0.038440878 USD, incierta0.003. Todavía ninguna nueva llamada pagada.
- Economics: ECB2026-10-02 1.1225USD/EUR; margen35%; techo operativo1.66USD, saldo inicial1.621559122. Fuentes oficiales guardadas con hashes. El usuario pidió dejar comprobaciones adicionales de tokens; se continúa implementación con límites fijados.
- R1 normalización/R2 correo con palabras mejoraron probes pero revisión descubrió fuga por puntuación Unicode en secreto etiquetado. Ambos candidatos no aceptables sin R3 unión de spans originales+normalizados. R3 verde focal; detectorv5. No cambian classification, umbrales, rúbrica ni Decimal.
- Captura causal local: «Calcula»/«Resume» se sustituyen por PERSON antes de clasificación/juez. Scope requirements ya correcto; no atribuir scores históricos al efecto sin comparación viva. Falsos positivos NER/citas permanecen.
- Root implementó `scripts/run_calibration_campaign.py`: reutiliza evaluation.run_pilot, snapshot detectorbase cargado sin sobrescribir archivos, puente credenciales RO, guard8000B/máx512, ledger único y asignación final protegida. Tres testsrunner nuevos verdes. No real hasta pruebas C y muestras A congeladas.
- B tiene permiso commitselectivo sólo suyo; C espera ese commit antes staging. A termina oráculos/corpus, reservado aún cerrado.

## Próximo paso

Guardar snapshot de base y hashes; acordar las primeras hipótesis de B/C; comprobar contratos del ejecutor y fijar precio/FX con fuente oficial. Mantener confirmación final protegida. Tras candidato integrado, cinco puertas y dos revisores nuevos sobre commit fijo.
