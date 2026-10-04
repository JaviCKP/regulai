# Delta de revisión independiente: 3491d6b

Rango fijo `4fdbe1a...3491d6b`; se conserva la revisión anterior y sus pruebas rojas. El corpus y el pack final todavía no forman parte de este commit. No se ha leído el reservado.

## SEC-CAL-03 — P2: revocación después de reservar no llega al guard de transporte

`scripts/run_calibration_campaign.py:218` comprueba archivos congelados y contenido en `make_guard`, pero no revalida la aprobación vigente. `LedgerObserver.before_call` sí revalida antes/dentro/después de reservar (`regulai/front/evaluation.py:416`–`:451`); posteriormente el servicio crea el cliente SDK (`chat_service.py:743`) antes de enviar. Una revocación en ese intervalo deja salir esa generación y sólo se detecta al intentar la siguiente llamada.

Reproducción causal: `authorization_gap_probe.py` ejecuta `exercise_case(real=True)` sobre SQLite temporal, callback de autorización que lee un JSON sintético, guard real del ejecutor y fronteras preparadas requests/SDK/HTTPX MockTransport. El constructor del cliente revoca el JSON después de las comprobaciones de reserva. El proveedor falso recibe la generación con estado ya revocado: `generation_calls_after_revocation=1`, eventos `classification,generation`, nueve comprobaciones `approved` antes y una `revoked` en el control posterior. No hay acceso a la autorización o ledger reales.

Comando desde la raíz:

```text
rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security\run_fixed_review.py --commit 3491d6b --label authorization_gap_probe --run-name authorization-gap
```

Exit 1, 1 fallo. Evidencia: `3491d6b-authorization-gap.log`, `3491d6b-authorization-gap-execution.json`, `3491d6b-authorization-gap-observed.json`. La corrección debe trasladar también la validación vigente (aprobación/digest/ventana) a la frontera final de envío, después de preparar el SDK. No se afirma una carrera infinitesimal inevitable: se ha reproducido una ventana concreta de trabajo entre dos funciones.

## Delta de muestras y precios

`reviewed_sample` separa `provider_input` de oráculos, exige el indicador de revisión por caso, verifica integridad y congela los archivos de selección, API, manifiesto y partición. La nueva opción de fuentes de precios compara cada snapshot con su SHA declarado y conserva los archivos fechados. Lectura sin hallazgos adicionales; la muestra adaptada concreta queda pendiente del pack final.

Comando del runner focal: el mismo ejecutor de revisión con `--commit 3491d6b --label front.test_calibration_runner --run-name runner`. Exit 0, 4 tests. Logs: `3491d6b-runner.log` y `3491d6b-runner-execution.json`. El snapshot deliberadamente no contiene assets estáticos y Django muestra el aviso no bloqueante `staticfiles.W004`.

Los hallazgos SEC-CAL-01/02 no se han declarado corregidos: se espera el commit integrado con la protección de todos los destinos de persistencia. No se han ejecutado llamadas pagadas, leído credenciales ni cambiado runtime compartido.
