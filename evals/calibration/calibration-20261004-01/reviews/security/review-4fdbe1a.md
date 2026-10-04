# Revisión independiente de seguridad y presupuesto

Revisor delegado nuevo, no autor de los módulos revisados. Comparación fija: `9d7f9424a70143614c9d673e64ebed9723ff3439...4fdbe1af7502ec458e05320a1429628dc809061e`. Revisión manual acotada: runtime del detector, evaluador, ledger, ejecutor y pruebas nuevas; los artefactos históricos son contexto, no ejecuciones nuevas. No se abrió un scan Security adicional.

## Hallazgos reproducidos

### SEC-CAL-01 — P2: el filtro de credenciales no interpreta JSON escapado

`regulai/front/evaluation.py:100`, `:141` y `:183` comparan las credenciales prohibidas contra bytes crudos. Una cadena JSON válida que representa la misma credencial mediante escapes `\uXXXX` evita esas comparaciones. El recorder persiste el cuerpo de respuesta reversible y declara `response_omitted_credential_reflection=false`; ocurre en HTTPX y requests. Una petición con el secreto escapado en `messages[].content` también se captura y alcanza el transporte. El control equivalente sin escapes sí se omite/rechaza.

Impacto: la captura detallada puede conservar una credencial reflejada pese a `forbidden_secrets`. No se sostiene que un proveedor haya reflejado una credencial real: todas las reproducciones usaron valores ficticios y transportes locales.

Reproducción: `CredentialCaptureProbes` en `security_probes.py`, 4 tests, 3 fallos y 1 control correcto. Evidencia en `4fdbe1a-probes.log` y `4fdbe1a-probes-execution.json`. Corregir la comprobación antes de persistir/transmitir, contemplando las cadenas y claves JSON decodificadas además de la representación cruda.

### SEC-CAL-02 — P2: omitir la respuesta del recorder no impide persistirla en otros destinos

`regulai/front/evaluation.py:143` omite el cuerpo de captura cuando refleja una credencial, pero el transporte devuelve la respuesta íntegra al SDK. `:570` conserva el contenido en `generation_responses`; `:463` copia un identificador de respuesta reflejado al ledger. Estos dos destinos existían antes del diff y ahora son reutilizados por el ejecutor nuevo; es un fallo de integración de la promesa de preservar secretos, no una regresión atribuida a su creación.

Reproducción a través de `exercise_case(real=True)`, con modelo/configuración reales de producto, requests preparado, SDK OpenAI y HTTPX MockTransport, claves falsas y SQLite temporal: una respuesta que coloca la credencial ficticia en `message.content` e `id` produce `wire_response_omitted=true`, `retained_response_contains_secret=true`, `ledger_contains_secret=true`, `delivered_answer_contains_secret=false`, una generación. La máscara del producto funciona en la respuesta entregada; el fallo está en los otros artefactos. Evidencia booleana en `4fdbe1a-reflection-observed.json` y traza en `4fdbe1a-reflection.log`.

Debe impedirse que una respuesta reflejada alcance esos destinos o aplicarse una protección común a todos ellos, conservando el coste incierto de la llamada ya iniciada. El saneamiento exclusivo de `synthetic-payloads.json` no cierra este caso.

## Comprobaciones y resultado

Todos los comandos se ejecutaron desde la raíz mediante `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security\run_fixed_review.py` y sólo sobre el snapshot del commit fijado.

| Argumentos adicionales | Resultado | Evidencia |
| --- | --- | --- |
| `--run-name existing-captured` | exit 0; 34 tests, 2 fallos NER ya declarados como esperados | `4fdbe1a-existing-captured.log`, `4fdbe1a-existing-captured-execution.json` |
| `--probes` | exit 1; 4 tests, 3 fallos de SEC-CAL-01 | `4fdbe1a-probes.log`, `4fdbe1a-probes-execution.json` |
| `--label security_probes.FullFlowCredentialReflectionProbe --run-name reflection` | exit 1; SEC-CAL-02 reproducido | `4fdbe1a-reflection.log`, `4fdbe1a-reflection-execution.json` |
| `--label security_probes.TransportControlProbes --run-name controls` | exit 0; 3 controles independientes | `4fdbe1a-controls.log`, `4fdbe1a-controls-execution.json` |

Los controles independientes demuestran una sola llamada de transporte ante HTTP 503 del SDK, rechazo del segundo transporte concurrente y rechazo de TypeSafe directo antes del transporte. La suite focal incluye parejas sintéticas en las tres entradas HTTP y captura de clasificación/generación/juez; compite por reservas, revoca mientras espera el bloqueo, conserva historial y reserva incierta, limita ventana y bloquea repetición tras interrupción.

Lectura del ejecutor: `0.077 USD/caso` corresponde a 3 + 3 + 5 llamadas externas y 1 + 1 + 2 generaciones máximas. La admisión por fase descuenta exposición histórica y protege `0.6486236488 USD` de confirmación. Se revalidan fuentes por preflight, autorización bajo bloqueo de reserva, destinos/modelos y archivos congelados antes del transporte. No se encontró otro bypass reproducible por el flujo de preparación normal en esta revisión.

## Límites

- No llamadas de pago, accesos a la base del usuario, ledger real, credenciales, `local_settings.py`, nuevas dependencias, push ni publicaciones. Sockets/DNS bloqueados durante los tests y credenciales ficticias por entorno.
- No se leyeron casos, etiquetas ni resultados del reservado. El commit revisado aún no contiene el corpus ampliado ni la muestra adaptada final; su procedencia, exclusión de datos reales y ausencia de oráculos en la muestra concreta quedan pendientes del commit final.
- El ejecutor de pruebas excluye assets estáticos del snapshot, por lo que Django muestra `staticfiles.W004`; no afecta estas pruebas. La primera ejecución de 34 tests pasó, pero su redirección local no capturó el log; `existing-captured` repite la misma suite con evidencia persistida y es la referencia utilizada aquí.
- No se revisó seguridad integral del repositorio ni se reabrió la investigación de token usage/tarifas. No hay medición semántica real en estas pruebas.
- Los hallazgos se comunicaron al orquestador y al propietario del evaluador. No se declaran corregidos hasta repetir las sondas contra un nuevo commit fijo integrado.
