# Errata de hashes del wrapper de revisión

3 de octubre de 2026. Esta errata corrige metadatos de las revisiones independientes, no resultados de pruebas ni evidencia del ensayo real.

Los wrappers `review-vercel-security/run_tests.py` y `review-diagnostics-security/run_tests.py` calculaban `log_sha256` dentro del bloque que mantenía abierto el fichero de salida. Algunas líneas finales seguían en el buffer de texto y se escribían al salir del bloque. Por ello, determinados campos JSON y tres celdas de la tabla del informe Vercel corresponden al prefijo del log y no al fichero completo. Los archivos originales, incluidos esos metadatos, se conservan sin cambios.

Los sellos finales se calcularon después de terminar los procesos y contienen los hashes correctos de los logs completos. Se verificó de nuevo que esos hashes corresponden a los archivos existentes. Las pruebas no se han reclasificado ni se ha reescrito evidencia para hacer coincidir un hash.

Informe afectado: `docs/plan-blackhat/revisiones-piloto/security-vercel-698e8f0.md`, sección «Pruebas y trazabilidad», tabla «Ejecución», columna «SHA-256 del log». Deben emplearse los siguientes hashes completos, que ya figuran en `.claude/review-vercel-security/final-seal.json`:

| Log | Hash parcial publicado en la tabla/JSON | SHA-256 correcto del archivo completo |
| --- | --- | --- |
| `.claude/review-vercel-security/supplied-focal.log` | `c4a3b560dac6b98cffec7dd48756058cff9a7de82b08616ca840991a89ebf9ac` | `4c48046a056bf8ccdf5c996a75db0e600d474832bf107a8cbf6c5cfd834a90e9` |
| `.claude/review-vercel-security/own-gateway.log` | `929c02b13985a3731c7ee2d5a5ed1bc76789641b20dd5ae2f4bed5eef14a0ddc` | `aab805e0059479e54cdfb6849d0ab74fee7f5557e8d727b52a6c8e19a5eeb6c2` |
| `.claude/review-vercel-security/router-negative-verification-only.log` | `5365455290d010dd5ab29a86c4c895b1e8a46b92ead031a8c3d05b3fcedf1416` | `5c330ce04ded56a113c0fbf607ca5fbe2dfc1794fa2d6f57565dd4647531fcc3` |

La fila `frozen-scope-approvedbytes` no necesita corrección: su hash publicado coincide con el fichero completo. El sello Vercel original conserva SHA-256 `659a9c0e2de7109e03737e7fd08f58c9a2b20769abea800fc4245817d2e12cc7`.

Los seis logs de esta revisión diagnóstica tienen ambos valores, temprano y final, en `finalized-log-hashes.json`; el informe diagnóstico utiliza exclusivamente los hashes finales. Ese inventario tiene SHA-256 `53e6549772330833702bb42262dbd9340e4d3a6e73d22d0c0e1e21f58b34a43d`.

Reproducción: `rtk proxy .venv\Scripts\python.exe .claude\review-diagnostics-security\finalize_log_hashes.py` terminó con exit 0, seis logs inventariados y tres erratas históricas. El script rechaza sobrescribir el inventario. Para futuras ejecuciones del wrapper debe calcularse el hash después de cerrar el fichero, o después de vaciar explícitamente sus buffers. No se han alterado los wrappers ya usados ni se han repetido llamadas de producto por esta errata.
