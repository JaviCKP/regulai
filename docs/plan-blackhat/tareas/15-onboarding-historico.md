# 15: Política inicial e histórico reversible

**Status:** in-progress
**Blocked by:** none

## Entrega y aceptación

Admin por empresa, registro desactivado, bootstrap auditado, migraciones de precios/capacidades/histórico.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

Migraciones integradas individualmente y probadas en bases aisladas con ida/vuelta:

- `33a264c`, 0029 precios por millón: 216 tests OK en 33.915 s. El validador reprodujo AssertionError en `4400f0b` antes de integrar.
- `59c820b`, 0030 capacidad reasoning: 217 tests OK en 34.950 s; modelos anteriores conservados y capacidad desactivada por defecto.
- `b95f349` + `f677d54`, 0031 histórico: 218 tests OK en 32.687 s; inferencia por lotes, marca BigInteger, decisiones/relaciones/archivos conservados y reversa que respeta reasignaciones posteriores.

Cada integración pasó también check, migraciones sin cambios, 150 controles offline (cero llamadas reales) y pip-audit sin vulnerabilidades conocidas. Ocho expected failures de otros carriles permanecen. Evidencia local: `regulai-wt/evidence/06-price-migration`, `07-reasoning-migration`, `08-historical-migration`. No se migró ninguna base existente del usuario. Permisos, política inicial y consultas históricas siguen en implementación.
