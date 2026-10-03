# Ensayo real y calibración humana del piloto

Preparación local a 3 de octubre de 2026. **No se han ejecutado llamadas nuevas de producto ni se ha concedido una nueva autorización de gasto.** La autorización histórica del 2 de octubre no activa ningún comando. Los nuevos ensayos usan el detector de máscara local real, generación/jueces simulados y bases en memoria; no acreditan calidad, calibración ni ahorro reales. Los informes anteriores de máscara HTTP simulada se conservan como históricos.

## Qué queda preparado

`smoke_ai` y `evaluate_ai` llaman al mismo `send_chat_message`, con máscara obligatoria, política, consentimiento, clasificación, generación, verificación y como máximo un segundo intento. Los dos comandos comparten `EvaluationBudget` y, en modo real, el archivo fijo `.claude/pilot-real-budget.sqlite3` y su lock. No hay selector de otro ledger para eludir el límite. El límite conjunto propuesto es **1,00 USD**, incluyendo todos los intentos de ambos comandos y bancos. El uso posterior exige revisar el saldo y las reservas; no empieza desde cero.

El estado normal es offline. El modo real exige `--real`, `--max-usd 1.00`, autorización explícita con identidad/referencia humana, lista de hashes exactos de manifiestos y una ventana de hasta 24 horas. Antes de reservar y otra vez tras la reserva, antes de iniciar transporte o cómputo, se comprueban autorización, fuentes, dataset, rúbrica, runtime, identidad/hash del detector, destinos y fecha de revisión de tarifas. Una edición intermedia detiene las llamadas siguientes. Si se revoca durante la espera por la reserva, la operación no iniciada queda registrada a coste cero; esta es la protección SEC-1. El fichero de aprobación es un registro operativo de la aprobación del usuario, no un mecanismo criptográfico de firma ni permiso para que el agente se autorice a sí mismo.

La ejecución acepta únicamente SQLite en memoria. Crea empresas/usuarios/credenciales temporales y medios en un directorio temporal; no cambia empresas ni bases existentes. Las credenciales reales, cuando exista autorización, se inyectarán mediante `REGULAI_EVAL_GENERATOR_KEY` y `REGULAI_EVAL_JEV_KEY` en el entorno del proceso, nunca en manifiestos, argumentos, informes o conversaciones. No se han leído ni preparado aquí esos secretos.

## Ensayo inicial exacto: ocho casos sintéticos

[Entradas completas](../../evals/pilot-real/cases.jsonl), [manifiesto](../../evals/pilot-real/manifest.json) y [autorización pendiente](../../evals/pilot-real/authorization.pending.json).

| ID | Comprobación | Alcance de la expectativa |
| --- | --- | --- |
| arithmetic | 2 + 2, respuesta 4 | Resultado exacto; la revisión humana continúa separada. |
| blocked | Marcador ficticio de credencial | Bloqueo local antes de cualquier salida. |
| consent-pending | Marcador ficticio de consentimiento | Cero llamadas mientras está pendiente. |
| consent-accepted | Mismo marcador, confirmación firmada | Confirma solo la petición sintética declarada; no amplía destinos. |
| document-success | Contrato ficticio con plazo de 17 días | Respuesta documental, cita y cobertura. |
| evidence-absent | Penalización ausente de la fuente | Aviso y respuesta limitada; pertinencia revisada por una persona. |
| verification-failed | Cita editada por el fixture offline | Demuestra rechazo en simulación; en vivo no se fuerza un fallo. |
| second-attempt | Fixture económico dice 30 días frente a 17 | Router puede corregir una vez en simulación; un proveedor vivo puede acertar a la primera. |

Cada caso se ensaya en economy, strong y router: 24 recorridos con idénticos datos y restricciones. Se fija semilla `20261003`, orden mezclado reproducible, límite de 512 tokens de salida, 16.000 bytes de datos de entrada por caso, plazo de 90 segundos y presupuesto de 0,15 USD por petición. Economy/strong permiten una generación; router permite dos. Las calidades configuradas 0,6/0,95 y los umbrales 0,8 son valores provisionales, **no resultados de calibración**.

## Destinos y modelos propuestos, todavía sin autorización

| Función | Destino exacto propuesto | Modelo / versión | Tarifa de referencia USD por millón |
| --- | --- | --- | --- |
| Generación económica | `https://api.deepseek.com` | API `deepseek-flash`; versión publicada DeepSeek-V4.1-Flash | Entrada sin caché pico 0,30; salida pico 1,20. |
| Generación fuerte | mismo destino | API `deepseek-v4-pro`; versión publicada DeepSeek-V4-Pro-0813 | Entrada sin caché pico 1,32; salida pico 3,96. |
| Clasificación y juez | `https://api.typesafe.ai/v1/systemone` | `jev-1.13.0`, versión explícita | Entrada 0,042; salida 0. |
| Enmascarado | Proceso local en CPU, sin endpoint HTTP | `regulai-local-v1`, spaCy 3.8.16, `xx_ent_wiki_sm` 3.8.0 y patrones | Coste de API 0 USD; cómputo/operación sin valorar. |

Referencias oficiales consultadas el 3 de octubre: [DeepSeek, modelos y tarifas](https://api-docs.deepseek.com/quick_start/pricing/) y [TypeSafe, modelos y versionado](https://docs.typesafe.ai/models). Se utiliza la tarifa pico sin caché como estimación conservadora. La generación conserva las temperaturas del servicio compartido: 0,6 para entrada general y 0,1 cuando hay documento; ambos valores y `thinking: disabled` están registrados en el manifiesto y contrastados con el cuerpo HTTP del SDK. El [Gateway de Vercel](https://vercel.com/ai-gateway/models/jev) anuncia `typesafe-ai/jev`, pero la propuesta nueva usa el modelo explícito directo para evitar ese alias adicional. El acceso histórico por Gateway **no prueba** acceso a TypeSafe directo con esta cuenta.

DeepSeek publica versiones, pero sus identificadores de API son alias móviles. Se conserva esa limitación y el modelo comunicado; un identificador efectivo inesperado o ausente detiene la evaluación. Si el proveedor mantiene el alias mientras cambia los pesos, ese cambio no se detecta solo con la respuesta. La revisión oficial el mismo día y la aceptación explícita de esa limitación son obligatorias; no se presenta como versión inmutable ni comparación plenamente reproducible de pesos.

## Detector local y límites de su validación

La propuesta usa `ObfuscationConfig.backend=local`, `detect=both`, idioma vacío (español/inglés admitidos), URL vacía y cota API explícita `0`. El detector procesa lotes completos, reconoce entidades con spaCy y aplica patrones de PII/secretos. No llama a DeepSeek para enmascarar, no arranca un servicio HTTP ni descarga modelos durante las peticiones. Si falta el modelo, cambia su identidad o falla la transformación, el servicio se detiene; no hay fallback externo.

El manifiesto fija el hash SHA-256 del wheel `6f3c4b853852ea9e9d2dc76cc950dddb10a7e4c42d813308caefe6c5e8be2f0a` y el hash observado de los datos instalados `4f5b7a5c5baf29c9e940befeb1f02a3021acc22806e3c1cbcef48e2078a2477a`, además de versiones y hash del módulo. `detector_metadata()` revisa archivos/versiones sin red ni carga de NLP. Los [metadatos oficiales del modelo](https://raw.githubusercontent.com/explosion/spacy-models/master/meta/xx_ent_wiki_sm-3.8.0.json) documentan versión, licencia MIT y procedencia WikiNER; [spaCy](https://spacy.io/usage/models) documenta la instalación de paquetes versionados. Las fuentes se revisaron el 3 de octubre de 2026.

La eliminación es heurística: puede omitir información sensible o marcar texto inocuo, y puede cambiar citas/respuestas. Las pruebas sintéticas de transporte demuestran el tratamiento de esos ejemplos, **no anonimización completa ni precisión empresarial**. Casos, rúbricas, etiquetas y umbrales permanecen congelados; cualquier fallo del banco causado por el detector se conserva y se informa.

La aplicación del detector al banco histórico de 50 casos produjo seis discrepancias literales, conservadas en `legacy-local-01`: los nombres de `multi-constraint-es` se ocultan y «Único» en `duplicate-request` se marca como persona. El segundo es un falso positivo contextual. No se han ajustado el detector ni las etiquetas para esos ejemplos. Ese banco conserva su fixture HTTP de identidad como regresión del contrato original; los nuevos bancos de ocho y 24 casos y la demo usan el detector real. El fixture HTTP no acredita eliminación de PII.

El original se procesa localmente. DeepSeek y Jev son los únicos destinos externos de la propuesta y reciben el resultado del enmascarado. Los marcadores bloqueados por YARA no salen a ningún destino. Restricted permanece bloqueado. El backend HTTP se conserva para configuraciones anteriores y pruebas de compatibilidad, pero no forma parte de estos manifiestos ni de su solicitud de aprobación. No se concede permiso para publicar, desplegar, comprar créditos o contactar a un proveedor.

## Contabilidad, parada y recuperación

Cada transformación de máscara y llamada de clasificación, generación o juez obtiene una reserva SQLite **antes** del transporte/cómputo, después de persistir su intención en la ficha. La máscara local deja una entrada `transport=local`, coste API 0 y procedencia `configured_zero`; sus transformaciones no cuentan como llamadas externas. Se registran también fallos, descartes y los dos intentos. Las transacciones del ledger se cierran antes de la red. El lock común evita solapar los dos comandos; una reserva también se serializa atómicamente.

Se distinguen costes calculados por tarifa, costes comunicados por el proveedor y reservas inciertas. Una estimación barata no libera su reserva conservadora. Un timeout o un error externo sin factura no equivale a cero. Solo un importe comunicado válido, cero API demostrado para cómputo local, o una llamada demostrablemente no iniciada permiten liquidar según esos datos. Un fallo local puede dejar resultado de cómputo incierto y a la vez coste de API conocido igual a cero. Si el importe externo observado supera la cota, se conserva y se bloquean las llamadas posteriores. Las cotas por llamada son 0,05 USD de generación y 0,003 USD de clasificación/verificación; el saldo conjunto nunca se amplía para terminar un banco.

El techo es un control local de admisión sustentado en las cotas revisadas; no garantiza que un proveedor nunca facture por encima de ellas. No se hacen recargas ni compras. Si ocurre una discrepancia, un fallo de contrato/transporte, deriva de modelo, revocación, presupuesto insuficiente o control fallido, se para el banco y se conservan resultados parciales. No se repite automáticamente un resultado incierto.

La carpeta nueva contiene plan, casos y rúbrica congelados, resultados JSONL, recibos, respuestas sintéticas de cada generación —sin razonamiento privado—, CSV/JSON/Markdown agregados, snapshot del ledger y plantilla de revisión vacía. Cada caso terminado se escribe y sincroniza en un diario incremental; el ledger conserva incluso una llamada que muera antes del informe. Un proceso interrumpido puede dejar lock: comprobar que terminó, conservar archivos, revisar reservas y retirar manualmente el lock únicamente tras esa revisión. Nunca borrar/recrear el ledger para conseguir presupuesto nuevo. Una aprobación modificada no renueva ni reemplaza implícitamente la autorización ya ligada al ledger.

## Calibración humana inicial local: dos personas y 0 USD de APIs

[Banco propuesto](../../evals/pilot-human/cases.jsonl): 24 casos, 12 desarrollo y 12 reservados, español/inglés, cálculo, contratos, extracción, resumen, evidencia ausente, contradicciones, sensibilidad, consentimiento e inyección. Es una propuesta sintética de cobertura, **no representatividad validada de un uso empresarial**. Una persona conocedora del dominio y otra revisora independiente deben validar representatividad y referencias; nombres, fechas y revisiones están vacíos.

Las [referencias de desarrollo](../../evals/pilot-human/development-labels.pending.jsonl) y las [reservadas](../../evals/pilot-human/reserved-labels.pending.jsonl) son borradores separados. El runner comprueba hashes, pero no usa sus etiquetas en prompts, respuestas o puntuaciones. Se fijan las etiquetas humanas antes de comparar modelos vivos. Los casos reservados se abren tras congelar respuestas; si sirven para ajustar umbrales, dejan de ser reservados y se necesita otro conjunto. No bajar umbrales para forzar un recorrido exitoso.

Dos sesiones locales propuestas: primero acordar la [rúbrica](../../evals/pilot-human/rubric.md) y adjudicar desacuerdos solo en desarrollo; después revisar el recorrido y la comprensión de bloqueo, consentimiento, cobertura, citas y coste usando resultados offline claramente rotulados. Esas sesiones preparan etiquetas y comprensión; no miden precisión de modelos vivos. La calibración real vendrá después con autorización y dependencias resueltas.

Cada revisión exige identidad, fecha con zona horaria, razón y hash de la fila original. El agregador rechaza duplicados, filas desconocidas o hashes cambiados. Acierto, abstención correcta, cobertura, sensibilidad/falsos positivos y negativos, citas y cambios del segundo intento se muestran con denominadores explícitos. Coste por respuesta correcta queda `null` hasta revisión completa y ausencia de costes desconocidos; se separan cocientes estimados y comunicados. p50/p95 incluyen n y no son SLA. No se ha rellenado ninguna revisión ni anunciado calidad/ahorro.

## Comandos locales

Elegir siempre directorios nuevos:

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py smoke_ai --settings=regulai.test_settings --output evals/reports/pilot-smoke-nuevo
rtk proxy .venv/Scripts/python.exe regulai/manage.py evaluate_ai --settings=regulai.test_settings --manifest evals/pilot-human/manifest.json --output evals/reports/pilot-human-nuevo
rtk proxy .venv/Scripts/python.exe regulai/manage.py smoke_ai --settings=regulai.test_settings --preflight --authorization evals/pilot-real/authorization.pending.json --output evals/reports/no-se-crea
```

Tras revisar cualquier cambio de código/datos/tarifas, preparar un manifiesto **nuevo**, comparar el diff y obtener una aprobación nueva ligada a sus hashes; este script no aprueba ni contacta con proveedores:

```powershell
rtk proxy .venv/Scripts/python.exe scripts/prepare_pilot_manifest.py --manifest evals/pilot-real/manifest.json --output evals/pilot-real/manifest-revisado.json
```

Solo después de revisar la configuración y limitaciones del detector local, credenciales/acceso, versiones/tarifas y aprobación explícita se podrá preparar un fichero aprobado y ejecutar el modo real. Se deben aprobar los hashes exactos de ambos manifiestos si comparten la misma autorización. El acceso directo a TypeSafe continúa sin comprobar y no se suple con el acceso histórico por Gateway. No se propone ejecutar ese comando como parte del arranque.

Cuando personas reales completen una copia de la plantilla de resultados:

```powershell
rtk proxy .venv/Scripts/python.exe scripts/pilot_human_report.py --results RUTA/results.jsonl --reviews RUTA/revisiones-humanas.json --output RUTA/revision-nueva
```

## Estado de aceptación

Las [tareas 23](tareas/23-recorrido-real.md) y [24](tareas/24-calibracion-humana.md) distinguen preparación comprobada de validación viva/humana pendiente. Los resultados del detector están en [evidencia local nueva](../../evals/reports/pilot-evaluation-local-20261003-01/README.md); el [ensayo anterior](../../evals/reports/pilot-evaluation-20261003-01/README.md) conserva su máscara simulada. Las cifras y la autorización histórica permanecen en la tarea 08 y no se contabilizan como ejecución de este piloto.
