# SEC-1: aprobación durante la reserva

Regresión del hallazgo independiente de seguridad sobre `febc8aa`, reproducida por integración antes del corrector. SQLite en memoria, ledger temporal, transportes requests/SDK simulados y sockets bloqueados. Sin gasto ni llamadas de producto.

- `red.json` / `red.log`: 1 test, ocho fallos, exit 1; revocar o vencer la aprobación dentro de `reserve()` todavía permite el transporte de máscara, clasificación, generación o verificación.
- `green.json` / `green.log`: **21 tests correctos, 35,033 s, exit 0**, incluyendo las ocho variantes, fallo de liquidación, presupuesto y evaluación offline. El runner registra también la duración completa del proceso, comando y hashes de código/log.

El observador revalida la aprobación después de obtener la reserva. Si ya no es válida, conserva el registro con su cota y lo liquida como `not_started`, coste `0`, procedencia `not_incurred`, antes de devolver permiso al transporte. Si la liquidación falla, conserva exposición incierta y detiene el envío; el test comprueba `outcome_unknown` y reserva de `0.01` sin transporte.

Comandos reproducibles (usar nombres nuevos para conservar evidencia):

```text
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-evaluation-followup-20261003-02/run_regression.py red front.test_smoke.SmokeIsolationTests.test_authorization_changed_during_reservation_prevents_each_transport
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-evaluation-followup-20261003-02/run_regression.py green front.test_smoke front.test_evaluation_budget front.test_evaluation
```

Los errores estructurados de las pruebas negativas son esperados. Esta evidencia del implementador no sustituye el cierre independiente ni las cinco puertas finales. Una comprobación local no puede retirar una petición que ya haya empezado su transporte; el arreglo cierra el intervalo reproducido dentro de la reserva.
