# Verificación tras integrar la documentación

Las cinco puertas se repitieron después de integrar la aclaración de enmascarado activo, sobre `52bdc8d71d37dcf40b59293346a4f74f043ef416`. Evidencia conservada el 2026-10-03T08:40:27.198035+00:00. El código funcional coincide con la [verificación técnica anterior](../community-fixes-verification-20261003/README.md). Ninguna llamada real a proveedores/Jev.

| Puerta | Salida real | Registro |
| --- | --- | --- |
| Django check | System check identified no issues (0 silenced). | [check.log](check.log) |
| Suite front/api | Ran 302 tests in 62.428s; OK, sin expectedFailure ni omitidas | [tests.log](tests.log) |
| Migraciones | No changes detected | [migrations.log](migrations.log) |
| Evaluación offline | 150 simulated runs; 0 failed controls; real calls 0 | [evaluation.log](evaluation.log) |
| pip-audit | No known vulnerabilities found | [audit.log](audit.log) |

[Comandos, revisión y hashes de los logs](gates.json). [Banco offline copiado de la ejecución original](offline/report.md), con su [manifiesto](offline/manifest.json); los comandos registran su directorio original fuera del checkout. Los controles negativos de la suite provocan fallos de evaluación de forma deliberada; la suite y el banco final terminan correctamente.

La revisión documental y los [pendientes externos](../../../docs/plan-blackhat/estado-ejecucion.md) se documentan por separado. No se ejecutó CI remoto, PostgreSQL ni calibración pagada. Los cambios posteriores de cierre y archivo de evidencias no modifican el código probado.
