# 93 — Chat 12: ejecución y recuperación

Status: corregido, aplicado y verificado localmente el 18 de octubre de 2026.
Blocked by: ninguno.

Los dos comandos de simulación terminaron con código 0. La proyección rechazaba
el trailer del SDK; posteriormente el checkpoint privado del workspace era
rechazado como canal binario. El turno fallido se excluía del historial y «sigue»
perdía la tarea. Se corrige el contrato de resultados, se permite el checkpoint
privado cifrado con alcance y validación explícitos y se selecciona contexto de
continuación sólo desde cómputo propio completado y registrado.

Aceptación observada: las tres entradas HTTP continúan con resultados registrados,
ocultan datos sensibles al proveedor simulado y completan la entrega sin crear
otra operación execute. Se preservan privacidad/YARA, revocaciones, aislamiento,
límites, idempotencia y dinero. La recuperación mantiene validación de ZIP,
identidad, versiones y autorización. No se repiten efectos inciertos.

Detalle, resultados, límites de las suites y reversión:
[informe](../../../output/chat12-fix-20261018/README.md),
[pruebas finales](../../../output/chat12-fix-20261018/tests-3.json),
[SDK](../../../output/chat12-fix-20261018/sdk-tests-3.json),
[activación](../../../output/chat12-fix-20261018/apply-0.json),
[verificación](../../../output/chat12-fix-20261018/verify-0.json).
