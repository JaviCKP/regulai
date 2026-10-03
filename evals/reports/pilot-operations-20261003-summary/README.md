# Evidencia de operación local, 2026-10-03

Fuente de comparación: `6c78cd3`; fuentes efectivas y HEAD de cada ejecución están en su `source-manifest.json`. No son resultados históricos reutilizados. Cada directorio conserva comandos, códigos, duración y SHA256 de logs; `verification.json` vuelve a comprobar esos hashes y registra cero coincidencias de claves sintéticas o marcador sensible en logs.

| Ejecución | Resultado observado |
| --- | --- |
| 01 | Falló inspección de base Python no retenida por BuildKit; construcción correcta |
| 02 | Migración/seed/static/deploy check correctos; puerto inaccesible en red interna |
| 03 | HTTPS disponible; permiso600 de estático impidió lectura Nginx |
| 04 | HTTPS/aislamiento/transportes correctos; harness alcanzó throttle al repetir login |
| 05 | Concurrencia/desconexión/reinicio correctos;82 tests PostgreSQL: error del test al asumir nombre `csrftoken`, una omisión SQLite |
| 06 | Ejecución completa correcta;82 tests PostgreSQL en12,336s (una omisión SQLite); recuperación/recifrado/conflicto real |
| 07 | Ejecución completa correcta;82 tests PostgreSQL en12,464s (una omisión SQLite); recuperación y endpoint supervisado durante1s |

Los problemas de configuración/harness se corrigieron sin reducir límites, aserciones ni protecciones. El test de cookie lee ahora `settings.CSRF_COOKIE_NAME` y conserva la prueba de rechazo/aceptación CSRF. El test omitido usa triggers SQLite; el conflicto se ensayó mediante una conexión PostgreSQL concurrente en `postgres-real-rotation-conflict.log`.

En06/07 se compararon filas y hashes de las27 tablas, los dos archivos privados y descifrado de credenciales; la reversión del dump y claves volvió a coincidir. Ninguna base existente fue usada. Tras07, `rtk proxy docker ps -a --filter label=regulai.synthetic-lab --format "{{.Names}} {{.Status}}"` devolvió salida vacía y código0. Carpetas privadas y backups sintéticos conservados en `.claude/`; recursos Docker temporales retirados.

Comando de auditoría: `rtk proxy .venv/Scripts/python.exe evals/reports/pilot-operations-20261003-summary/verify_evidence.py`, código0;7 ejecuciones, hashes coincidentes,0 valores sensibles sintéticos hallados. El script rechaza sobrescribir su salida. Repetir en un nuevo directorio si se necesita otra evidencia.

Límites: no usuarios humanos, no proveedores vivos, no CI remoto, no despliegue público. El enmascarador sintético reemplaza un marcador exacto; el transporte no evalúa calidad de lenguaje. Ver [procedimiento](../../../docs/plan-blackhat/operacion-y-recuperacion-piloto.md).
