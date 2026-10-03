# 24: Preparar referencias humanas independientes y calibración

**Status:** pending human validation — banco y agregación local implementados
**Blocked by:** dos personas, validación de representatividad/referencias y adjudicación; comparación viva además depende de 23
**Specification:** [05](../05-clasificacion-documental.md), [07](../07-verificacion-y-escalado.md), [11](../11-evaluacion-reproducible.md).

- [x] Banco sintético propuesto de 24 casos con 12 de desarrollo y 12 reservados; referencias en archivos separados.
- [x] Rúbrica fija, hashes, guía para revisión independiente y plantilla vacía con trazabilidad al resultado.
- [x] Informe por caso y agregado: entrega/cobertura, acierto/abstención humanos, sensibilidad, citas, segundo intento, dinero por procedencia y p50/p95 con n.
- [x] Coste por respuesta correcta condicionado a revisión completa y costes completos; ninguna inferencia automática de calidad/ahorro desde el juez prefijado.
- [x] Preparación offline sin claves ni coste de API; revisión de transportes/métricas mediante pruebas locales.
- [ ] Dos personas validan representatividad y referencias; resolver desacuerdos y registrar nombres/fecha/razón.
- [ ] Congelar referencias antes de comparar; no usar reservados para ajustar umbrales ni luego llamarlos independientes.
- [ ] Completar revisiones humanas reales de resultados, medir errores corregidos/introducidos y comparar configuraciones sin selección favorable.
- [ ] Repetir con proveedores vivos autorizados si se desea afirmar precisión, calibración o ahorro reales.

[Banco y rúbrica](../../../evals/pilot-human/README.md), [procedimiento](../ejecucion-real-y-calibracion-piloto.md) y [evidencia](../../../evals/reports/pilot-evaluation-20261003-01/README.md). Las referencias actuales son borradores del autor, no etiquetas humanas completadas. Las sesiones iniciales propuestas son locales, con coste de API 0 USD; no se ha contactado con revisores ni inventado su aprobación.
