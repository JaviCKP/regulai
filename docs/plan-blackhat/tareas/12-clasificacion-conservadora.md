# 12: Clasificación ordinal conservadora

**Status:** integrated; pending pipeline integration
**Blocked by:** 09, 10

## Entrega y aceptación

C1/C2, probabilidades coherentes, avisos y simulador compartiendo decisión; esquema opcional estricto.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

Integrados 5a14086 y 12d80fe (origen 335fcf8 y 2e1369f). Decide ordinal conserva suelo local, distingue manipulación y rechaza incoherencia; simulador comparte decisión sin ampliar destinos. ASTRA reprodujo siete pruebas HTTP del simulador en 4400f0b: siete AssertionError, cero errores/omitidas. El agente observó rojo/verde por comportamiento y 151 tests correctos en su rama.

Gates de integración: 163 tests en 24.081 s, OK(expected failures=11); check sin incidencias; migraciones sin cambios; 150 ejecuciones offline, cero controles fallidos/cero llamadas reales; auditoría sin vulnerabilidades conocidas. B3 ya pasa sin expectedFailure (f80a14a). C1/C2 del chat requieren integración P y siguen marcados.

Compatibilidad: si no se configura call_timeout_seconds, se limita al deadline antiguo menor que 30 s. classification=local no activa Jev por elegir ruta automática en el simulador; P replicará esta regla. Presupuesto+enmascarado sin cota se rechaza antes de cualquier salida. Temporalmente el simulador semántico con máscara activa devuelve masking_required, sin llamadas; P conectará el helper y ledger antes de retirar ese cierre.
