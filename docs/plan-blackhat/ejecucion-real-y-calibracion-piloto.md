# Ensayo real y calibración humana del piloto

Preparación local a 3 de octubre de 2026. **No se han ejecutado llamadas nuevas de producto ni se ha concedido una nueva autorización de gasto.** La autorización histórica del 2 de octubre no activa ningún comando. Los ensayos de este trabajo usan transporte simulado y bases en memoria; no acreditan calidad, calibración ni ahorro reales.

## Qué queda preparado

`smoke_ai` y `evaluate_ai` llaman al mismo `send_chat_message`, con máscara obligatoria, política, consentimiento, clasificación, generación, verificación y como máximo un segundo intento. Los dos comandos comparten `EvaluationBudget` y, en modo real, el archivo fijo `.claude/pilot-real-budget.sqlite3` y su lock. No hay selector de otro ledger para eludir el límite. El límite conjunto propuesto es **1,00 USD**, incluyendo todos los intentos de ambos comandos y bancos. El uso posterior exige revisar el saldo y las reservas; no empieza desde cero.

El estado normal es offline. El modo real exige `--real`, `--max-usd 1.00`, autorización explícita con identidad/referencia humana, lista de hashes exactos de manifiestos y una ventana de hasta 24 horas. Antes de cada llamada se vuelven a comprobar autorización, fuentes, dataset, rúbrica, runtime, destinos y fecha de revisión de tarifas. Una edición intermedia detiene las llamadas siguientes. El fichero de aprobación es un registro operativo de la aprobación del usuario, no un mecanismo criptográfico de firma ni permiso para que el agente se autorice a sí mismo.

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
| Enmascarado | **Pendiente de URL real y contrato** | Contrato de array JSON del servicio existente | Pendiente; la propuesta reserva hasta 0,01 USD por llamada. |

Referencias oficiales consultadas el 3 de octubre: [DeepSeek, modelos y tarifas](https://api-docs.deepseek.com/quick_start/pricing/) y [TypeSafe, modelos y versionado](https://docs.typesafe.ai/models). Se utiliza la tarifa pico sin caché como estimación conservadora. La generación conserva las temperaturas del servicio compartido: 0,6 para entrada general y 0,1 cuando hay documento; ambos valores y `thinking: disabled` están registrados en el manifiesto y contrastados con el cuerpo HTTP del SDK. El [Gateway de Vercel](https://vercel.com/ai-gateway/models/jev) anuncia `typesafe-ai/jev`, pero la propuesta nueva usa el modelo explícito directo para evitar ese alias adicional. El acceso histórico por Gateway **no prueba** acceso a TypeSafe directo con esta cuenta.

DeepSeek publica versiones, pero sus identificadores de API son alias móviles. Se conserva esa limitación y el modelo comunicado; un identificador efectivo inesperado o ausente detiene la evaluación. Si el proveedor mantiene el alias mientras cambia los pesos, ese cambio no se detecta solo con la respuesta. La revisión oficial el mismo día y la aceptación explícita de esa limitación son obligatorias; no se presenta como versión inmutable ni comparación plenamente reproducible de pesos.

## Dependencia de máscara: opciones concretas

La URL `https://mask.service.invalid` del manifiesto es un marcador que el preflight rechaza. No se ha construido ni comprobado una máscara real. El fixture offline devuelve el lote sintético sin modificar y demuestra el recorrido del contrato, **no eliminación de PII**.

1. Usar un servicio propio de la empresa, accesible mediante HTTPS, que cumpla `POST <base>/api/mask`, reciba `text` como string de array JSON y devuelva `masked` con la misma cantidad y orden de strings. Hay que aportar URL real, configuración `detect=both`, revisión de TLS/retención, prueba independiente con PII/secretos sintéticos y evidencia del coste incremental por llamada. Cero solo se declara si está justificado.
2. Elegir un servicio externo compatible y autorizado para recibir el **original**, documentando esos mismos datos y su cota tarifaria. No hay proveedor externo ni precio elegido/verificado para esta opción; no se puede aprobar todavía como destino concreto.
3. Continuar con la preparación y revisión humana offline a coste de API 0 USD mientras se resuelve esa dependencia.

El dato original solo puede salir hacia la máscara autorizada. Generador y Jev reciben el resultado del enmascarado. Los marcadores bloqueados por YARA no salen a ningún destino. Restricted permanece bloqueado. Ninguna de estas opciones concede permiso para publicar, desplegar, comprar créditos o contactar a un proveedor.

## Contabilidad, parada y recuperación

Cada llamada de máscara, clasificación, generación o juez obtiene una reserva SQLite **antes** del transporte, después de persistir su intención en la ficha. Se registran llamadas fallidas, descartadas y los dos intentos. Las transacciones del ledger se cierran antes de la red. El lock común evita solapar los dos comandos; una reserva también se serializa atómicamente.

Se distinguen costes calculados por tarifa, costes comunicados por el proveedor y reservas inciertas. Una estimación barata no libera su reserva conservadora. Un timeout o un error sin factura no equivale a cero. Solo un importe comunicado válido, cero configurado de servicio propio, o una llamada demostrablemente no iniciada permiten liquidar según esos datos. Si el importe observado supera la cota, se conserva y se bloquean las llamadas posteriores.

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

Solo después de resolver la máscara, credenciales/acceso, versiones/tarifas y aprobación explícita se podrá sustituir el fichero pendiente por uno aprobado y ejecutar el modo real. Se deben aprobar los hashes exactos de ambos manifiestos si comparten la misma autorización. No se propone ejecutar ese comando como parte del arranque.

Cuando personas reales completen una copia de la plantilla de resultados:

```powershell
rtk proxy .venv/Scripts/python.exe scripts/pilot_human_report.py --results RUTA/results.jsonl --reviews RUTA/revisiones-humanas.json --output RUTA/revision-nueva
```

## Estado de aceptación

Las [tareas 23](tareas/23-recorrido-real.md) y [24](tareas/24-calibracion-humana.md) distinguen preparación comprobada de validación viva/humana pendiente. Los resultados nuevos están en [evidencia del piloto](../../evals/reports/pilot-evaluation-20261003-01/README.md). Las cifras y la autorización histórica permanecen en la tarea 08 y no se contabilizan como ejecución de este piloto.
