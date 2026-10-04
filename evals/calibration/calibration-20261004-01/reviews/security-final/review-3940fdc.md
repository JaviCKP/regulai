# Revisión independiente de seguridad y presupuesto — 3940fdc

Revisor nuevo delegado, no autor del runtime. Rango fijo: `9d7f9424a70143614c9d673e64ebed9723ff3439...3940fdc698c34998b2541309b0b697b6c06c2287`. Resultado del 4 de octubre de 2026, previo a recibir evidencia de las llamadas reales y del cierre de campaña.

**No se ha encontrado un bloqueo de seguridad o presupuesto para ejecutar centralmente `baseline-smoke-02` dentro de la autorización existente del usuario.** Los tres P2 de la revisión anterior quedan corregidos en los caminos reproducidos. Esto es una conclusión técnica acotada; no crea otra aprobación humana ni acredita ejecución remota o finalización de la campaña. El ejecutor debe conservar las comprobaciones de manifiesto, autorización vigente, ledger y ventana que ya aplica al activar y antes de cada transporte.

## Hallazgos anteriores

| Hallazgo | Resultado en 3940fdc | Evidencia nueva |
| --- | --- | --- |
| SEC-CAL-01, escapes JSON; variante de campos duplicados | Corregido en los dos transportes. La búsqueda inspecciona todas las claves y valores decodificados, incluidos miembros sobrescritos. Peticiones prohibidas no alcanzan el transporte; respuestas se rechazan conservando sólo su hash. | `3940fdc-independent-probes.log`; claves escapadas, listas/objetos anidados y fragmentos en `3940fdc-new-boundary-variants.log`. |
| SEC-CAL-02, persistencia en respuesta de generación y ledger | Corregido en el flujo completo reproducido. Una respuesta con la credencial ficticia en el cuerpo y el ID no alcanza los destinos de persistencia. Se conserva la reserva de la generación incierta y no se inicia el juez posterior. | `3940fdc-reflection-observed.json`: tres indicadores de presencia del secreto, todos `false`; prueba sobre `exercise_case(real=True)` con transportes preparados y SQLite temporal. |
| SEC-CAL-03, revocación tras reserva durante construcción del SDK | Corregido en el intervalo reproducido. El guard invoca la autorización al final de la preparación del transporte y el ejecutor revalida preflight, digest y cabeza/ventana del ledger. | `3940fdc-authorization-gap-observed.json`: `generation_calls_after_revocation=0`; la solicitud queda detenida con coste conservador. |

No hallazgos nuevos reproducibles P0/P1/P2 en este alcance. Se añadieron cuatro pruebas propias, además de repetir las reproducciones independientes existentes. El control benigno conserva observable una respuesta JSON pública con el filtro de credenciales habilitado. Se verificaron también reflejos en `x-request-id` de HTTPX y requests, un único transporte ante 503, rechazo del segundo transporte concurrente y rechazo de TypeSafe directo.

## Paquete concreto

- Manifiesto: `140b78da56b9fccf0307fe6612a0d9b1ce2826fad6a65bd21ef9e900bafd1fe5`.
- Autorización: `50f93d6f4d2aa3959327dbfae376ccdeeb5dd27bb8c92ab075f0d2daa4e8a7dc`.
- Cuatro casos de desarrollo previamente marcados como sintéticos revisados: legítimo, PII, documento e inyección. Se inspeccionaron sus textos; no contienen credenciales reales ni datos personales reales identificables. Los inputs conservan los prompts congelados y separan los campos del oráculo.
- Tres configuraciones, doce combinaciones, una pasada, máximo 44 llamadas externas. El máximo adicional es `4 × (4 × 0.014 + 7 × 0.003) = 0.308 USD`.
- Techo agregado `1.66 USD`, incluyendo exposición histórica del snapshot económico `0.038440878 USD`; no se añade otro saldo de dos euros. La suma máxima inicial es `0.346440878 USD`, dentro del límite de fase `0.3627527024 USD`. Se preserva la asignación de confirmación `0.6486236488 USD`.
- Con el cambio congelado `1.1225 USD/EUR` y margen del 35 %, el techo completo representa `1.996436525612472160356347439 EUR`. La ventana congelada es `2026-10-03T23:12:23Z` a `2026-10-04T23:12:23Z`.
- Coinciden todos los hashes de datos, rúbrica, referencias, archivos de campaña y fuentes del working tree. Los archivos de runtime coinciden con el commit fijo: trece archivos del checkout Windows sólo difieren del blob Git por CRLF frente a LF. No se relajó la comparación de los hashes que realmente congela y verifica el ejecutor.
- El resultado nuevo `baseline-smoke-02-independent-check-eol.json` pasa las 23 comprobaciones y guarda las diferencias de finales de línea. Se conservó la comprobación inicial que comparaba bytes Git/checkout y devolvió exit 1 por esos finales de línea.

La comprobación del preflight central y la inmutabilidad de la base del usuario se contrastó con `preflight.stdout.log` y `preflight-bridge.json`, cuyos hashes coinciden con el pack. Este revisor no abrió la base del usuario ni el ledger real. La reconciliación final del gasto real queda pendiente de sus artefactos centrales; la exposición histórica anterior es evidencia congelada de la campaña.

## Ejecuciones nuevas

Todos los comandos se lanzaron desde la raíz del repositorio. El ejecutor creó un snapshot fijo con `rtk proxy git archive`; no importó `local_settings.py`, empleó SQLite en memoria/temporal y bloqueó sockets y DNS durante los tests. El snapshot y sus complementos tienen manifiestos SHA-256 separados.

| Comando | Resultado | Evidencia |
| --- | --- | --- |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit 3940fdc --label security_probes_final --label authorization_gap_probe_final --label duplicate_fields_probe --run-name independent-probes` | exit 0; 11 pruebas | `3940fdc-independent-probes-execution.json`; log SHA `a47358489199ff4a34b4b6b05d40bb400c12dc8319d1d28a41b8eed1eef71a9d` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit 3940fdc --run-name existing-focal-complete` | exit 0; 42 pruebas, 2 fallos NER esperados | `3940fdc-existing-focal-complete-execution.json`; log SHA `b241256347f9b35d15c3be063786c00f509707bb36cdb69c929062be65046bda` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit 3940fdc --label additional_probes --run-name new-boundary-variants` | exit 0; 4 pruebas propias | `3940fdc-new-boundary-variants-execution.json`; log SHA `0ac0806a239c8dbec7f195098ba39025f460c1d0695fb4ff5c9a727940fb6e44` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\check_pack.py` | exit 0; 23 comprobaciones | `baseline-smoke-02-independent-check-eol.json` |

El primer intento de suite focal (`--run-name existing-focal`) tuvo exit 1 por ausencia de `scripts/run_adversarial_community.py` en el snapshot. Se incorporó exactamente ese fichero desde el mismo commit y se repitió con el nombre nuevo mostrado arriba. No fue una modificación del producto ni una regresión de sus pruebas. Django avisa `staticfiles.W004` porque este snapshot excluye los assets estáticos; no afecta a las comprobaciones ejecutadas. En las ejecuciones finales hay 57 pruebas: 55 pasan y 2 constan como limitaciones NER esperadas.

## Cobertura y límites

Se trazaron los cambios de `evaluation.py`, `evaluation_budget.py`, `local_masking.py`, ejecutor, adaptador de corpus y scripts públicos de validación/evaluación/descarga; se siguieron sus fronteras de transporte y persistencia. La suite focal comprueba reservas concurrentes, revocación bajo bloqueo, conservación del historial/reservas, ventana, interrupción sin replay, muestra congelada y los tres accesos HTTP con captura de los transportes de clasificación/generación/juez. Esta es una revisión manual acotada; no una auditoría integral de todo el repositorio o de miles de artefactos históricos.

No se leyó `corpus/reserved/**`, el reservado sustituido ni `scripts/build_calibration_corpus.py`. El generador queda fuera de esta revisión mientras el reservado permanezca cerrado. La procedencia pública y los hashes son evidencia de trazabilidad; no equivalen a una adjudicación semántica independiente de las familias ni a revisión humana. No se reabrió la investigación de tarifas/token usage; se comprobó la coherencia del paquete y de los snapshots ya fijados.

Las dos limitaciones esperadas son falsos positivos NER sobre letras Unicode comunes y sobre una etiqueta de campo solapada con identificador. No se afirma detección universal. No hubo llamadas pagadas ni red de producto, credenciales reales, cambios de runtime, migraciones de la base del usuario, commits, push o publicación por este revisor. Las cinco puertas globales, la comparación reservada y la reconciliación de llamadas reales corresponden al cierre central pendiente.
