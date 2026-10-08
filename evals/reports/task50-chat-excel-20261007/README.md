# Evidencia de la tarea 50

Ensayo iniciado el 7 de octubre UTC, terminado el 8 de octubre en Europe/Madrid.
Solo datos/cuentas sintéticos, SDK real, HTTP de proveedor simulado, E2B/Firecracker
y PostgreSQL reales. Cero llamadas nuevas de pago. Alcance y limitaciones completos
en la [tarea 50](../../../docs/plan-blackhat/tareas/50-agente-chat-excel.md).

Evidencia principal:

- `final-pg-boundaries.log`: 32 pruebas de 49/50 y concurrencia/migraciones PostgreSQL.
- `final-input-contract.log`: 9 pruebas después del endurecimiento final de relaciones XML.
- `final-revoked-replay.log`: las 13 pruebas de 50 pasan de nuevo, incluyendo rechazo del duplicado HTTP tras revocación.
- `final-csv-parser-bounds.log`: rechazo de CSV malformado/campos sobredimensionados sin error interno y aceptación del contrato válido.
- `final-governance-regressions.log`: 196 regresiones de gobierno, envío y estado/dinero.
- `recheck48-sdk.log`, `recheck49-sdk.log`, `final-runtime-unit.log`: 15, 5 y 2 pruebas.
- `end-to-end-real-vm.log` y `live-evidence/live-cases.json`: recorrido y fallos reales.
- `live-evidence/audit.json`, `model-requests.json`: eventos/tiempos, SHA y frontera del modelo.
- `live-evidence/live-csv.xlsx`, `live-renamed.xlsx`, `live-xlsx-input.xlsx`: salidas reales
  recalculadas con Calc. El cambio de título solo modifica XML de la primera hoja.
- `post-restart-evidence`: nueva ejecución completada después del reinicio y cambios
  finales del worker; `worker.log` contiene ID, preparación limpia y duración real.
- `real-network-metadata-fenced-vm.log`: aislamiento definitivo, controles positivos
  antes/después y denegaciones en ejecutor y microVM. Informes con `passed=false`
  son diagnósticos anteriores y no acreditan aislamiento.
- `ui-final-desktop.png`, `ui-final-mobile.png`: revisión 2, preview seguro y descarga;
  móvil comprobado con ancho DOM/scroll 390/390. Dos pestañas probaron revisión vieja.
- `defaults-off.log`, `final-schema.log`, `final-django-check.log`, `final-diff-check.log`.
- `cleanup-live-vm.log`, `real-lab-final-check-vm.log`, `shutdown-lab-vm.result.json`:
  limpieza y cero sandboxes restantes. Se conserva el volumen previo de 48.
  `cleanup-local.json` acredita VM detenida y puertos temporales cerrados.
- `baseline.json`, `preservation.json`, `lock-digests.json`: conservación del trabajo
  local anterior y versiones. El lock de 48 no cambia.

Los `.result.json` guardan comandos exactos, códigos de salida y duración. Se
mantienen los errores intermedios de construcción/caché/red. Sus scripts de
diagnóstico se archivaron en `diagnostics/`, fuera del código de ejecución.

No se extrapola a datos arbitrarios, modelos reales o producción. El perfil soporta
dos herramientas revisadas y un contrato tabular acotado. El endpoint de metadatos
de E2B precisó una ruta `prohibit`; `NoNewPrivs=0` de la microVM sigue documentado.
No se avanzó a la tarea 51.
