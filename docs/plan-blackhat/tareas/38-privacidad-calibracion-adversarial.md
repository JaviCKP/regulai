# 38 — Privacidad en la calibración adversarial

**Status:** in_progress — correcciones locales y diagnósticos verificados; contraste con desarrollo ampliado y aceptación integrada pendientes.
**Blocked by:** congelación de desarrollo por el propietario del corpus; validación/selección y cinco puertas por el coordinador.
**Propietario:** B, privacidad/clasificación; código exclusivo `local_masking.py`, `classification.py` y pruebas focales `test_calibration_privacy.py`.
**Especificación:** [05](../05-clasificacion-documental.md), [11](../11-evaluacion-reproducible.md), [privacidad obligatoria](21-privacidad-obligatoria.md), [detector local](../enmascarado-local.md), [tareas 32](32-banco-adversarial-y-datos-personales.md), [33](33-limites-del-detector-adversarial.md), [34](34-bloqueos-semanticos-en-casos-benignos.md) y [35](35-frontera-numerica-del-umbral.md).

## Aceptación y resultado observado

- [x] Reproducir omisiones DNI con espacios/Unicode y correo con palabras; controles benignos y hostiles sintéticos, sin reservado ni llamadas pagadas.
- [x] Capturar el contenido efectivo del clasificador, generador y juez en tres HTTP, sin inferir que «sin repetir» explique PII-03 o los demás rechazos.
- [x] Registrar hipótesis antes de candidatos y conservar rojo→verde, pérdidas y candidatos descartados.
- [x] Mantener interfaces, máscara obligatoria, YARA original, autorización, aislamiento, citas literales y frontera Decimal. `classification.py` no se modifica.
- [x] Declarar cadenas opacas y pérdidas de NER/citas pendientes; no añadir excepciones por palabras del banco ni cambiar oráculos.
- [ ] Evaluar base/candidato en corpus ampliado de desarrollo y selección independiente autorizada; no leer reservado.
- [ ] Aceptación final de integración por coordinador y revisores independientes sobre commit fijo.

[Evidencia y comandos completos](../../../evals/calibration/calibration-20261004-01/privacy/README.md). Base `9d7f942`; candidato local `regulai-local-v5`, sin nuevas dependencias. R1 añade vista Unicode con offsets y DNI separado; R2 añade correo de palabras sólo tras etiqueta explícita; R3 une coincidencias originales y normalizadas tras descubrir que normalizar puntuación podía acortar un secreto etiquetado. v3/v4 quedan descartados como finales por esa regresión, reproducida con cuatro casos nuevos de desarrollo y corregida con pruebas de sufijos.

En 33 casos propios congelados: 18→28 casos completos, 9→19/20 valores eliminados y 28/32 textos preservados sin cambios. En las 44 regresiones históricas, ejecutadas de nuevo: 37→40 casos completos, 27→31/32 valores eliminados y 61/66 textos preservados. Cero casos empeorados entre estas anotaciones finales; la precisión/recobrado exhaustivos por span no se infieren de desaparición de cadenas. No se suman variantes como familias independientes ni se mide calidad semántica con fixtures.

La captura base de 99 cuerpos demuestra que NER transforma `Resume` con/sin negación/PII y `Calcula` en BENIGN-01 y una operación independiente. No demuestra la causa de las puntuaciones vivas históricas. El juez recibe `requirements`, respuestas 88/98 intactas y rúbrica real. Las citas INJ-05/DOC-03 vuelven a pasar antes de máscara y fallar después con `quote_not_found`; el cierre seguro permanece, la pérdida de utilidad sigue abierta.

Verificación nueva de R3: 87 tests en 22,781 s, exit 0 (85 aprobados, 2 fallos esperados preexistentes de NER). Tras ampliar únicamente captura de respuestas: 9 tests propios en 8,206 s, exit 0 (7 aprobados, los mismos 2 fallos esperados). SQLite en memoria y ajustes privados sustituidos; sin red real. No se presentan las 404 pruebas o 150 simulaciones históricas como ejecuciones de esta tarea.
