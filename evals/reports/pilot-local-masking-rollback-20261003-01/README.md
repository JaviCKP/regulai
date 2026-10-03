# Rollback sin reautorizar HTTP — 2026-10-03

Corrección del P2 independiente reproducido por `review_local_security` sobre `c85d019`. La selección local conservaba URL remota y actividad; al desaparecer `backend` en el downgrade, el código `700389c216592db1e0c8725749bb4fd02cf3fa10` volvía a aceptar la fila y enviaba el original al servicio HTTP anterior.

## Cambio

`0032_obfuscationconfig_backend.py` incorpora una operación con avance vacío y reversión que actualiza exclusivamente `backend='local', active=True` a `active=False`, usando el alias de base de datos de la migración. Se ejecuta antes de retirar el campo. Las filas HTTP activas/inactivas conservan su estado, y no se cambia URL, nombre, pertenencia, idioma, fechas, políticas o AuditLog. Repetir el downgrade y volver a avanzar no reactiva las máscaras locales anteriores.

La regresión permanente usa el formulario real para editar HTTP → local conservando la URL. Verifica dos empresas y seis configuraciones, incluyendo local con URL antigua, local sin URL, local inactiva y HTTP activo/inactivo. Compara todos los datos preservados y la autoridad observable para el código anterior.

## Rojo y verde observados

| Comando | Evidencia | Resultado |
| --- | --- | --- |
| `rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_local_masking_integration.LocalMaskingMigrationTests.test_downgrade_requires_reauthorization_of_local_masks_and_preserves_http_state --settings=regulai.test_settings --verbosity=2` | `red-regression.txt` | 1 test, 1 fallo por filas locales todavía activas; exit 1, antes del fix |
| `rtk proxy .venv/Scripts/python.exe evals/reports/pilot-local-masking-rollback-20261003-01/run_probe.py red` | `red-probe.log`, `red-result.json`, `red-observations.json` | 1 fallo; exit 1. Código anterior captura original en el HTTP antiguo |
| `rtk proxy .venv/Scripts/python.exe evals/reports/pilot-local-masking-rollback-20261003-01/run_probe.py green` | `green-probe.log`, `green-result.json`, `green-observations.json` | 0 fallos; exit 0. Exmáscara local: cero llamadas; control HTTP: una llamada sintética |
| `rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_local_masking_integration.LocalMaskingMigrationTests front.test_local_masking_integration.LocalMaskingConfigurationTests front.test_onboarding_migrations --settings=regulai.test_settings --verbosity=2` | `green-migration-gate.txt` | **9 tests OK en 2,322 s; exit 0** |

Los `.txt` conservan la codificación original UTF-16LE de PowerShell; los logs del probe son UTF-8. Ambos probes bloquean cinco fronteras socket/DNS y registran **cero intentos de red real**. La respuesta HTTP falsa sustituye solo el transporte, no las decisiones ni la migración. `frozen_legacy_masking.py` coincide con el SHA256 publicado por el revisor: `2508742be605a0c6f74d5c4a5a4fca7860667b9bbdc139ca3b16bb502835f697`.

El PoC original, sus observaciones, resultados y copia del código anterior en `.claude/review-local-security/` se leyeron sin alterarlos; sus hashes se conservan en `source-sha256.json`. El probe de esta carpeta escribe únicamente artefactos nuevos y se niega a reemplazar resultados de un run existente.

## Operación y límites

Detener procesos antes del downgrade. Ejecutar 0032 → 0031 con la migración corregida, antes de retirar el código que conoce `backend`; arrancar el código anterior después. Los antiguos locales permanecen inactivos. Reanudar HTTP exige revisión y autorización expresa del destino conservado; no se obtiene permiso porque la URL siga almacenada. Si se vuelve a la versión local, revisar y seleccionar de nuevo ese backend antes de activar.

Solo bases SQLite sintéticas en memoria. No hubo downgrade en una base de usuario, solicitudes a proveedores vivos, cambio de secretos, staging o commits de este agente. PostgreSQL y la secuencia operativa completa corresponden a la validación del coordinador. Esta corrección no puede reparar automáticamente un downgrade ya ejecutado con una copia anterior de 0032: habría que revisar las máscaras afectadas antes de volver a arrancar envíos.

Archivos de producto: migración 0032 y `test_local_masking_integration.py`. Documentación: anexo de la tarea 28. Propuesta de commit: `Disable local masking configurations before schema downgrade`.
