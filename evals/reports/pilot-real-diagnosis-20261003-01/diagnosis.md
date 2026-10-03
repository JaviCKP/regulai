# Diagnóstico del ensayo Vercel 2026-10-03

La ejecución conservada terminó con una llamada de clasificación incierta después de procesar 8 de las 24 combinaciones previstas. La causa concreta de esa última llamada no es recuperable de la evidencia guardada. Un defecto local de diagnóstico eliminaba `JevError.code` en clasificación y mostraba un texto que afirmaba que no hubo envío. Ese defecto se ha reproducido y corregido sin alterar decisiones, umbrales, destinos, costes, reservas ni reintentos.

Base del ensayo: commit `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`. Manifiesto ejecutado: `ff5a3056a6d13d7bc8a9c8baae559b002e201cc235be1a3aaa3cc4cd9e6e5b9d`. El replay y las sumas leen exclusivamente los informes UTF-8; no abren la base de usuario ni el ledger SQLite real. Los hashes de 11 archivos de evidencia se comprobaron antes y después: iguales. La evidencia anterior no se rellena con causas obtenidas de simulaciones posteriores.

| Configuración | Combinaciones procesadas | Entregadas | Intentos externos registrados | Transformaciones locales | Generaciones | Segundo intento | p50 ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economy | 2 | 0 | 4 | 3 | 1 | 0 | 2437 | 3781 |
| strong | 2 | 1 | 4 | 3 | 1 | 0 | 2562,5 | 4109 |
| router | 4 | 1 | 9 | 6 | 3 | 1 | 4008 | 6828 |
| Total | 8 | 2 | 17 | 12 | 5 | 1 | — | — |

Hay 29 entradas contables: 12 transformaciones locales a coste API cero y 17 intentos externos (16 completados y uno incierto). Los externos se reparten en 7 clasificaciones, 5 generaciones y 5 verificaciones. Se iniciaron 5 casos distintos; quedaron 16 combinaciones sin iniciar. `cases.executed.jsonl` contiene las ocho definiciones previstas y no demuestra que se ejecutaran todas. `completed_order` contiene resultados terminales, incluidos bloqueos, fallos e incertidumbre, no ocho éxitos.

Las dos respuestas entregadas fueron `4`, en arithmetic/router y arithmetic/strong. Hubo tres bloqueos (uno local y dos por clasificación), dos fallos de verificación y un resultado incierto. `control_pass=true` en las ocho filas verifica invariantes de ejecución, como bloqueo local, consentimiento previo y número máximo de generaciones. En modo real no compara `expected_status`; no significa ocho respuestas correctas. La revisión humana sigue en cero y las métricas de calidad, ahorro y coste por respuesta correcta permanecen nulas. Las filas `split=all` y `split=development` del resumen representan el mismo conjunto y no se deben sumar. Es una muestra interrumpida y desigual; sus latencias y cobertura no permiten comparar las configuraciones.

| Concepto contable observado | USD |
| --- | ---: |
| Coste comunicado por Gateway | 0.000312522 |
| Estimación por tarifa de las generaciones | 0.00074496 |
| Suma de importes conocidos, mezclando comunicado y estimado | 0.001057482 |
| Cotas conservadas para esas generaciones estimadas | 0.01054554 |
| Reserva de la clasificación incierta | 0.003 |
| Exposición conservada total | 0.013858062 |
| Capacidad presupuestaria restante según el ledger | 0.986141938 |

La exposición es `0.000312522 + 0.01054554 + 0.003`. Supera la suma conocida en `0.00980058` de margen conservado para estimaciones, más `0.003` de la llamada incierta. No es una factura ni un gasto confirmado de 0.013858062 USD. El saldo aritmético restante tampoco autoriza una repetición automática. El informe de presupuesto conserva correctamente todos estos conceptos; no se modificó ni liberó ninguna reserva real.

Los dos bloqueos de clasificación se reproducen con `classification.decide` y las señales guardadas. `consent-accepted/router` tiene manipulación 0,85; `verification-failed/economy`, 0,22. Ambos superan `classification_policy.signal_threshold=0.2`. El 0,8 del manifiesto es el umbral de confianza y no el umbral de presencia de señales. El resultado demuestra aplicación de la política configurada, no que el contenido haya sido revisado por humanos ni que esas detecciones sean verdaderos positivos. En `verification-failed/economy` no llegó a ejecutarse la prueba semántica sugerida por el nombre del caso. El fallo de cita del fixture solo se fuerza offline.

Las tres generaciones de `document-success` (router en dos intentos y economy en uno) conservaron exactamente el mismo contenido y hash: `62abd4bfed6d811355217fd2ef9d859a9c27c9cc047bac761ac4a8f7989357ac`. El replay de extracción, máscara real y comprobación local mantiene la respuesta sin cambios y aprueba las citas literales. La cita resuelta es `el plazo de entrega es de 17 días.`. Las probabilidades de fallo por omisión, 0,34 / 0,34 / 0,32, superan el corte de aceptación semántica de aproximadamente 0,2. Las demás señales no provocan el rechazo. El segundo intento router produjo el mismo texto y volvió a rechazarse. No se ha ajustado el umbral para aceptar estas respuestas.

Se observan falsos positivos del detector en texto de desarrollo. Con las mismas versiones y hashes del ensayo, el replay transforma exactamente:

```text
Entrada: ¿Cuál es el plazo de entrega? Cita la evidencia.
Salida:  ¿[[REGULAI_LOCATION]] es el plazo de entrega? [[REGULAI_PERSON]] la evidencia.

Entrada: Contrato sintético sin datos personales: el plazo de entrega es de 17 días.
Salida:  [[REGULAI_PERSON]] sintético sin datos personales: el plazo de entrega es de 17 días.
```

Esto demuestra sustitución de palabras comunes en el detector local. Es una reconstrucción determinista con los archivos del ensayo, no una captura del cuerpo HTTP enviado. No prueba que esa transformación causara la puntuación de omisión o el último error desconocido. No se han cambiado el detector, los casos, las rúbricas, las etiquetas o los umbrales. El hallazgo queda como límite observado que debe entrar en una calibración separada.

La última entrada (`document-success/strong`, clasificación, ID contable `ab67112d-9a37-43cd-9b45-76c6d1f756dd`) conserva `outcome_unknown`, coste nulo y reserva 0,003. La ficha registra duración de llamada 625 ms y no guarda cuerpo, estado HTTP, identificador de proveedor o código de causa. El log registra `security_check_failed` y clase sustituida `RuntimeError`. Esta combinación no distingue timeout, HTTP 5xx, formato inválido u otras causas compatibles. La duración tampoco identifica por sí sola el error del proveedor. La reproducción sintética demuestra que timeout, HTTP 503 y JSON inválido producían esa misma categoría pública; no determina cuál ocurrió en el ensayo.

La corrección añade `provider_error_code` a la ficha y al metadato del ledger para fallos Jev. Acepta solo códigos literales del cliente y estados conocidos por `HTTPStatus`, excluyendo HTTP 200; valores libres, diccionarios y nulos se reducen a `unknown_jev_error`. El log conserva un evento con ese código seguro. También se sanea la ruta de verificación antes de registrar una excepción. El público conserva sus `error_type`, estado HTTP y estado de ejecución previos. El texto ahora remite a la ficha de decisión y reconoce la posibilidad de un resultado incierto. Los registros históricos sin el nuevo campo siguen siendo válidos.

El siguiente paso es revisar y fijar este parche, y registrar por separado la pérdida de palabras comunes para calibración del detector. El error del ensayo sigue sin causa concreta: su reserva debe permanecer hasta disponer de evidencia independiente de coste/resultado; no se propone reintentar para averiguarlo. El nuevo runtime ya no coincide con el hash del manifiesto ejecutado, por lo que no debe renovarse o alterarse retroactivamente la autorización ni el ledger históricos.

Comandos ejecutados:

```text
rtk proxy .venv\Scripts\python.exe .claude\real-run-diagnosis\analyze.py
  exit 0; replay y auditoría inicial; audit.json SHA256 8de68be291b238c97ce2c61309969168ceb45d7c49ac43cccf5582c28d90839e

rtk proxy .venv\Scripts\python.exe regulai\manage.py test front.test_diagnostics --settings=regulai.test_settings --noinput
  rojo: exit 1, 5 tests, 16 subcasos fallidos, 4,978 s
  verde: exit 0, 5 tests, 4,873 s

rtk proxy .venv\Scripts\python.exe regulai\manage.py test front.test_diagnostics front.test_smoke front.test_evaluation_pilot front.test_evaluation_budget front.test_jev front.test_chat_flow front.test_pipeline --settings=regulai.test_settings --noinput
  final tras el último ajuste de texto: exit 0, 73 tests, 33,582 s

rtk proxy .venv\Scripts\python.exe .claude\real-run-diagnosis\analyze.py --output .claude\real-run-diagnosis\audit-after-diagnostic-fix.json
  exit 0; fuentes del replay iguales, runtime de diagnóstico nuevo identificado; evidencia histórica intacta

rtk git diff --check
  exit 0
```

Las pruebas usan bases temporales, claves sintéticas y fronteras de red simuladas. Cubren los tres puntos HTTP, reenvío con el mismo identificador sin nueva llamada, timeout/503/JSON inválido, códigos adversariales, error local sin red, fallo en verificación y reserva persistente íntegra. Coste nuevo del diagnóstico: 0 USD; llamadas nuevas de producto: 0. No se leyó ninguna credencial real ni se accedió a la base de usuario. Sin `git add`, commit, publicación o despliegue por C.

Archivos de código entregados: `regulai/front/chat_service.py`, `regulai/front/evaluation.py` y nuevo `regulai/front/test_diagnostics.py`. Commit propuesto: `fix: preserve safe Jev failure diagnostics without changing budget state`.
