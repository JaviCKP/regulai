# Verificación local final de Community

Revisión ejecutada: `12ca58d3a2b5a6570840ca80676a1799f6eac097`. Fecha UTC registrada por comando en [gates.json](gates.json). Los commits posteriores de documentación/evidencia no cambian el código probado. Sin push, despliegue, publicación ni llamadas reales a proveedores o Jev.

| Puerta | Salida real | Registro íntegro |
| --- | --- | --- |
| Django check | System check identified no issues (0 silenced). | [check.log](check.log) |
| Suite front/api | Ran 302 tests in 66.767s; OK, sin expectedFailure ni omitidas | [tests.log](tests.log) |
| Migraciones | No changes detected | [migrations.log](migrations.log) |
| Evaluación offline | 150 simulated runs; 0 failed controls; real calls 0 | [evaluation.log](evaluation.log) |
| pip-audit | No known vulnerabilities found | [audit.log](audit.log) |

[Banco final y manifiesto](../offline-community-fixes-final-20261003/report.md), [integraciones anteriores](integration-gates.json), [doce regresiones B1–B10/C1–C2](regressions.json), [rojo original](baseline-regressions.log), [tres cambios development y reserved intacto](dataset-changes.json).

El resumen de integraciones conserva también el intento frontend rechazado y revertido; las salidas de cada etapa no son pruebas únicas que deban sumarse. La suite contiene controles negativos que fuerzan seis errores de evaluación para probar su detección; ese texto no es un fallo de la puerta final. La nueva prueba CLI comprueba además un proceso que devuelve error con 52 controles fallidos y conserva sus informes.

Los proveedores, respuestas, jueces y costes del banco son sintéticos. No mide precisión semántica, ahorro real ni funcionamiento del CI remoto o PostgreSQL. Véanse los [pendientes](../../../docs/plan-blackhat/estado-ejecucion.md) y las [revisiones independientes](../../../docs/plan-blackhat/revisiones-correcciones/README.md).
