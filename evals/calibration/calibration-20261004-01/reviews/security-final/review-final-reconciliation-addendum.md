# Adenda final: seguridad, cadena de autorización y presupuesto

Fecha de verificación: 2026-10-04 08:47:36 UTC. Runtime fijo: `b3fea6a63761c06ef66695fee26377d23786c347`, con base `9d7f9424a70143614c9d673e64ebed9723ff3439`. Revisor independiente: `security_final`.

El cierre económico y la parada son coherentes con los artefactos finales. Las 40 comprobaciones independientes pasan, con salida 0. No aparece una nueva regresión de seguridad o presupuesto en este alcance. Se mantiene la parada de nuevas llamadas pagadas y la reserva completa de la respuesta inválida. Esta conclusión no convierte la campaña interrumpida ni la comparación local en una validación semántica completa.

Esta adenda complementa `review-3940fdc.md`, `review-b3fea6a.md` y `review-final-stop-b3fea6a.md`, sin sustituir sus evidencias. Los tres P2 previos sobre reflexión de credenciales, persistencia y revocación antes del envío quedaron cerrados por las pruebas documentadas allí. La precisión temporal sobre la revisión completa de R4 permanece en el informe de parada: terminó después del comienzo del ensayo; no se presenta como aprobación previa.

## Evidencia independiente y límites

Se leyó el código completo de `reconcile.py`, pero no se volvió a ejecutar. Evita el constructor de `EvaluationBudget`, abre SQLite con `mode=ro` y `PRAGMA query_only=ON`, usa el cálculo `snapshot()` original y sólo escribe tres archivos JSON nuevos. Compara el hash del ledger antes y después, exige coincidencia con el último presupuesto de R4 y conserva el prefijo histórico.

El revisor contrastó esos JSON con las autorizaciones, manifiestos, activación histórica, presupuesto de R4, selección, fuentes de runtime pertinentes, logs de puertas y resúmenes agregados locales. No abrió el ledger ni la base de usuario, no leyó credenciales, no hizo llamadas de proveedor y no ejecutó el constructor ni operaciones de reserva o conciliación. El hash de SQLite que se cita es el registrado por la ejecución central, no una nueva lectura del revisor.

Comando reproducible de la verificación de artefactos:

```text
rtk proxy .venv\Scripts\python.exe evals/calibration/calibration-20261004-01/reviews/security-final/check_final_reconciliation.py
```

Resultado: **40/40 PASS, exit 0**, en `final-reconciliation-independent-check.json`. El programa bloquea conexión de sockets/DNS y escribe su resultado con creación exclusiva. Reejecutarlo requiere una ruta nueva de resultado; el archivo existente no se sobrescribe. No se volvieron a ejecutar las pruebas de runtime ya verdes: el delta fijo cuenta con 80 pruebas focales, cuatro pruebas independientes de política y una reproducción local de la respuesta inválida, descritas en los informes previos.

## Ledger y autorización

Los 199 asientos del snapshot final son idénticos al `budget.json` de la última ejecución R4. El prefijo de 110 asientos históricos conserva todos sus campos. Los 89 nuevos son 88 `completed` y uno `outcome_unknown`: 49 llamadas externas (29 clasificación, 11 generación y 9 verificación) y 40 operaciones locales de coste y reserva cero. Los lotes consumieron 19, 19 y 11 llamadas externas respectivamente.

Las cinco extensiones tienen secuencia continua, identidades y digests únicos y una única ejecución por extensión. Para los tres lotes de esta campaña se recalcularon los digests canónicos de autorización y hashes de manifiesto, se verificaron los enlaces `extends`, la identidad de cada asiento y el límite de 44 llamadas por lote. Todas las llamadas nuevas están dentro de la ventana original, después de la autorización y del registro de su ejecución. El techo de 1,66 USD conserva el historial; no se ha reiniciado con cada lote.

La cabecera final es `calibration-20261004-01-r4-smoke-01`, digest `c8caf6f23b967df75190bf1b241ea27b8a2d841f5e11d8726aa070e5392d5b1a`. El último asiento continúa siendo `fa61b595-536f-4eac-b455-7c5cdd40c19c`, clasificación P0619/router, con `invalid_response`, `outcome_unknown`, coste `null` y reserva de 0,003 USD. No hay un asiento posterior en la reconciliación final.

La respuesta Jev HTTP 200 capturada tiene probabilidades que suman 0,99. La reproducción local ya documentada confirma que el parser la rechaza. El valor de facturación capturado, **0,000035742 USD**, no está validado como cargo seguro ni se incorpora a los costes comunicados validados. La reserva completa de 0,003 USD permanece, además de los 0,003 USD de incertidumbre histórica. No se liberó ni reconcilió ninguna reserva.

| Concepto, incluido el historial | USD |
| --- | ---: |
| Coste comunicado validado | 0,002794596 |
| Coste estimado por tarifa | 0,00961932 |
| Coste conocido, suma de los dos anteriores | 0,012413916 |
| Reservas inciertas retenidas | 0,006 |
| Exposición conservadora total | 0,076271376 |
| Techo global | 1,66 |

La exposición incluye las reservas correspondientes y no se suma otra vez al coste conocido. Equivale a **0,09172949452115812917594654788 EUR** aplicando el cambio congelado de 1,1225 USD/EUR y un margen del 35 %, por debajo del techo total de 2 EUR. La diferencia contable restante, 1,583728624 USD, no autoriza nuevas llamadas: la condición de parada prevalece. No se investigaron de nuevo precios, cambio ni consumo de tokens.

## Puertas y configuración final

Se verificaron los hashes de los seis logs: las cinco puertas solicitadas (`check`, `front-api`, `migrations`, `offline`, `dependencies`) y la auditoría adicional de dependencias PostgreSQL tienen salida 0, sobre el SHA fijo b3fea6a y con fuentes registradas sin cambios. La suite `front-api` ejecutó 452 pruebas con dos fallos esperados de NER. No se ejecutó CI remoto. Ambas auditorías de dependencias omiten `xx-ent-wiki-sm 3.8.0` por no estar en PyPI; su salida 0 no acredita ese paquete.

La configuración seleccionada coincide con su hash congelado: `privacy-v5-legacy-policy`, `manipulation_threshold: null`, `signal_threshold: 0.2`, clasificación obligatoria y verificación `enforce`. R4 0,40 sigue siendo experimental y no seleccionado. `final_selection.json` conserva `stop_new_paid_calls: true` y prohíbe ajuste posterior a la apertura del reservado.

## Comparación local reservada

Sólo se revisaron los resúmenes agregados y sus hashes; no se abrieron casos, etiquetas individuales, resultados por caso ni el constructor del corpus. Ambos resúmenes son idénticos: 571 casos, 372 familias, 120 ejecuciones HTTP con **114 controles superados**, 239 de 290 anotaciones locales superadas, cero intentos en las diez entradas de red vigiladas y cero coste API. Declaran fuentes sin cambios, `semantic_quality_measured: false` y salida 0 sólo para la integridad del harness.

Hay seis controles HTTP fallidos por brazo y 51 anotaciones locales no superadas por brazo. El empate agregado no demuestra ausencia de fallos individuales ni equivalencia caso por caso; no se diagnostican aquí sus contenidos. Estos límites impiden describir la comparación como privacidad universal, éxito de todos los controles o confirmación semántica remota.

## Hashes de cierre

| Artefacto | SHA-256 |
| --- | --- |
| `economics/final-reconciliation-01/summary.json` | `47c41b5cfc7180ad09fe9688ef17933afc81770191e15c6f8bebb91c46e03168` |
| `economics/final-reconciliation-01/ledger-snapshot.json` | `bdf26d430f6420e477fab132365842dda210ee51a33fa3842625872923ca34ec` |
| `economics/final-reconciliation-01/authorization-chain.json` | `7ffc92692a1eb1b88d9348fce59599087945074006a8d38a7018ed40fceff775` |
| `reconcile.py` | `4cc4ebe222fa577d9689f6975f621301af65e06a9c4f84d2e21b1b0b8b853b9c` |
| `gates-02/manifest.json` | `87c992525975f86af98db031f9afac7af666e6da7954af861d7e7813e723035e` |
| `final_selection.json` | `a33dad5bcb906f0bf26b55dfab04aa90be2f299faa4780216f157c68282d72a5` |
| `final-candidate-configuration.json` | `d8038364b6c01aec5159c73d7f938d4dd4c1c2be5db131ceb8df884eb715d5da` |
| Cada resumen agregado reservado | `6aa8042dfca5309504764c868c1f1a762383d79d4eecdaa6d5f841c4665d7de7` |
| Ledger SQLite, hash registrado centralmente | `614c62a38388af6ba9b8fc008ffd7c7c20b1d8bab844346c3205489a9864f250` |

Alcance final: revisión manual del diff y de su cierre económico, no auditoría exhaustiva de todo el repositorio. El revisor no hizo cambios de runtime, commits, migraciones, reservas, pagos, push ni despliegue.
