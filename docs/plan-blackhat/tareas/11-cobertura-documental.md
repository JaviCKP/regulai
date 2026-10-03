# 11: Cobertura documental explícita

**Status:** implemented
**Blocked by:** none

## Entrega y aceptación

Formatos corrientes, cambios aceptados, CSV/codificación, agrupación, avisos y bloqueo HTTP de partial.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

Integrado hasta `b61d11d`, con ajuste de fixtures en `9f58dbf`: cuatro estados de cobertura, disclosures, codificaciones, bloques de texto/CSV, cambios aceptados de Word, numeración, cachés de fórmulas y avisos PDF/XLSX. B7 queda sin expectedFailure. La extracción no hace OCR.

ASTRA ejecutó las 17 pruebas nuevas contra el producto `4400f0b`: 15 AssertionError de comportamiento, cero errores y dos invariantes ya correctos. Tras integrar: check sin incidencias; 180 tests OK (10 expected failures ajenos) en 29.446 s; migraciones sin cambios; 150 controles offline correctos, cero llamadas reales; pip-audit sin vulnerabilidades conocidas. Evidencia local: `regulai-wt/evidence/03-documents` y `D-orchestrator-red.log`.

Pendiente externo: ejemplos sintéticos guardados desde aplicaciones Word, Excel y LibreOffice reales. La integración del consentimiento `complete_text_only` corresponde a P/F.
