# Ensayo inicial autorizado a través de Vercel

Código y alcance fijados en `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`. El usuario aprobó hasta 1 USD para ocho casos sintéticos × economy/strong/router y después indicó usar Jev por Vercel. No se reutiliza la autorización del 2 de octubre. Banco humano, publicaciones, despliegues, compras y contactos quedan fuera.

- [Manifiesto congelado](manifest.json), SHA256 `ff5a3056a6d13d7bc8a9c8baae559b002e201cc235be1a3aaa3cc4cd9e6e5b9d`.
- [Registro de autorización](authorization.json), ligado a ese manifiesto y a las respuestas del usuario; ventana hasta el 3 de octubre de 2026 a las 23:59:59 UTC.
- [Preparador versionado](prepare.py), [identidad de preparación](preparation.json) y [puente de ejecución](run_authorized.py).
- [Preflight](preflight.stdout.log): `ready_for_real=true`, cero llamadas. [Resultado del puente](preflight-result.json): base original en modo de solo lectura y hash sin cambios; ninguna credencial apareció en los logs.

Destinos: `https://api.deepseek.com`, modelos `deepseek-flash`/`deepseek-v4-pro`; Jev en `https://ai-gateway.vercel.sh/typesafe/v1/systemone`, alias `typesafe-ai/jev` con proveedor limitado a `typesafe-ai`. Los alias son móviles y no prueban pesos inmutables. El original se procesa con el detector local falible; no se utiliza un enmascarador externo.

El puente selecciona un único par de credenciales de la misma empresa y las pasa solo al entorno del hijo con `regulai.test_settings`. Las empresas y sus datos se crean en SQLite en memoria. La base original no se migra. El ledger persistente común está en `.claude/pilot-real-budget.sqlite3`; no se borra para reiniciar el presupuesto. Cada llamada reserva antes de comenzar; una incertidumbre mantiene su reserva. Se detiene ante fallo, deriva o presupuesto insuficiente y no repite automáticamente.

```powershell
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-real-vercel-20261003-01/run_authorized.py --preflight
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-real-vercel-20261003-01/run_authorized.py --real
```

Estos comandos representan una ejecución única ya preparada, no una instrucción para volver a ejecutarla. El puente rechaza sobrescribir sus resultados. El registro de un permiso no prueba que el ensayo se haya realizado; los resultados observados se incorporan después de terminar la ejecución.

## Resultado observado

Ejecutado de 15:42:54 a 15:43:22 UTC del 3 de octubre. **Parada controlada, exit 1, tras 8/24 combinaciones**: cinco IDs de los ocho previstos. [Informe generado](live-run-01/report.md), [filas originales](live-run-01/results.jsonl), [diario incremental](live-run-01/completed-cases.jsonl), [ledger](live-run-01/budget.json) y [resultado del puente](live-result.json).

| Combinación | Resultado |
| --- | --- |
| consent-accepted / router | Consentimiento confirmado; clasificación bloqueó por señal de manipulación. Sin generación. |
| verification-failed / economy | Clasificación bloqueó por señal de manipulación. Sin generación. |
| arithmetic / router | Respondió `4`; verificación aprobada. |
| blocked / router | Regla local bloqueó antes de cualquier llamada. |
| arithmetic / strong | Respondió `4`; verificación aprobada. |
| document-success / router | Dos generaciones con citas localmente válidas; verificación semántica rechazó ambas. Sin respuesta entregada. |
| document-success / economy | Cita localmente válida; verificación semántica rechazó la respuesta. |
| document-success / strong | Clasificación incierta; parada global antes de generar. |

Son **17 llamadas externas**: siete clasificaciones, cinco generaciones y cinco verificaciones. Doce transformaciones locales se cuentan por separado. Dos respuestas entregadas, tres bloqueos, dos rechazos de verificación y un resultado incierto. No hay revisión humana; no se concluye que todo bloqueo o rechazo semántico sea correcto. Faltan 16 combinaciones y no se presenta el banco como completado.

Costes: **0,000312522 USD comunicados**, **0,00074496 USD estimados por tarifa**, **0,003 USD de reserva incierta**. Exposición conservadora del ledger: **0,013858062 USD**; saldo de admisión:0,986141938 USD. Las estimaciones tampoco liberan sus cotas, por lo que la exposición no es la suma de las cifras pequeñas ni una factura. Se mantiene el límite conjunto1 USD. El coste desconocido queda `null`, sin convertirlo en cero.

El puente verificó el hash sin cambios de la base original y que no aparecieron claves en stdout/stderr. El ledger y todos los resultados quedan conservados. No se repitió la llamada incierta ni se ejecutaron las combinaciones restantes.

[Verificación independiente del diario y sumas](result-verification.json), [script](verify_results.py). El primer verificador leyó por error el plan inicial en lugar del manifiesto final; su [fallo de arnés](result-verification-initial.json) y [script original](verify_results_initial.py) se conservan. No se modificaron las salidas vivas ni se hizo red para corregir el verificador.

La causa concreta de la excepción de clasificación no se conservó en la versión ejecutada: el informe solo guarda `security_check_failed`. No permite afirmar timeout, HTTP o respuesta mal formada. Se abrió la [tarea30](../../../docs/plan-blackhat/tareas/30-diagnostico-clasificacion-incierta.md) para corregir esa pérdida de diagnóstico sin volver a llamar al proveedor. Antes de proponer una continuación, hay que contrastar el evento de Gateway de las 15:43:21 UTC y mantener la reserva mientras no exista una liquidación fiable.
