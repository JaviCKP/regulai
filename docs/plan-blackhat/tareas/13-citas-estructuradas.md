# 13: Fuentes, citas y conectores

**Status:** implemented
**Blocked by:** none

## Entrega y aceptación

B8, alias, extractos resueltos desde 1, mínimos, JSON/capacidades y precios por millón.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

Integrado hasta `e042461`. B8 verde; fence JSON único, mínimo de cita de 12 caracteres sin espacios o tres palabras, máximo 30 afirmaciones, alias de fuentes y evidencia desde 1. Parámetros JSON/razonamiento explícitos en conectores; la conexión de consumidores pertenece a P y el campo de modelo a O.

ASTRA ejecutó nueve pruebas observables sobre `4400f0b`: ocho AssertionError, cero errores y un invariante ya correcto. Ajustó la prueba HTTP para afirmar el estado antes de intentar leer JSON. Suite integrada: 199 tests OK (9 expected failures ajenos) en 31.721 s; check sin incidencias; migraciones sin cambios; 150 controles offline correctos y cero llamadas reales; pip-audit sin vulnerabilidades conocidas. Evidencia local: `regulai-wt/evidence/04-verification` y `V-orchestrator-red.log`.

Adaptación del emisor offline: citas prefijadas cortas se amplían con texto literal de la fuente antes de introducir fallos sintéticos. Ninguna etiqueta, partición ni umbral cambió. Anthropic añade su esquema a la entrada facturable: P debe reservarlo; el tamaño del prompt interno del proveedor sigue sin cota publicada.
