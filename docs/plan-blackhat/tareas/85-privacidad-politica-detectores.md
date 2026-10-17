# 85 — E3 — Política y detectores

Status: completada; interfaz y validación local cerradas en E7.
Blocked by: [84](84-privacidad-servicio-comun.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E3 y criterios de la sección 11.

Aceptación: Categorías, literales y YARA localizado con simulación; conflictos deterministas y bloqueos/consentimientos intactos.

Verificación observada: 19 pruebas de privacidad OK en PostgreSQL desechable. Categorías, literales exactos repetidos, Unicode, conflictos, secreto dentro de literal, YARA con múltiples instancias, condición falsa, ausencia de posiciones, `wide`/binario rechazados, bytes truncados o divididos, fallo/timeout y revisión cambiada. Mensajes, apariciones y usos idempotentes; variantes cifradas. Simulación sin llamadas, activación firmada obsoleta rechazada y bloqueo YARA intacto.

La configuración pública sólo añade `privacy: {version: 1, revision_id}` cuando se activa explícitamente. Ausencia significa desactivada; ninguna migración añade esa clave. Las pruebas activan exclusivamente empresas sintéticas transaccionales. El validador antiguo rechaza esta clave, de modo que un rollback de aplicación no convierte una política nueva en permiso de salida.

Cierre consolidado: [entrega y matriz](../entrega-privacidad-20261017.md). Interfaz con prueba sintética/diferencias y activación firmada; reglas de seguridad originales intactas.
