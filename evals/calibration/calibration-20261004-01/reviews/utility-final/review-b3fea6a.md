# Adenda independiente — b3fea6a

Commit fijo `b3fea6a63761c06ef66695fee26377d23786c347`, delta respecto a `3940fdc`. Revisión por el mismo agente independiente. No se editó runtime, no se abrieron bases, no hubo red y el reservado/generador siguen cerrados. La revisión anterior y sus evidencias permanecen intactas.

**U1 cerrado.** El agregador añade los campos omitidos con denominadores medidos y mantiene `null` cuando no hay observación. La regresión distingue corrección retenida de corrección entregada. La sonda propia sobre fuentes obtenidas mediante `rtk proxy git show` del SHA fijo verifica esa distinción, cero citas inválidas observadas frente a ausencia de medición y compatibilidad de la opción nueva.

La opción `classification_policy.manipulation_threshold` conserva el comportamiento anterior cuando se omite o vale `None`, incluido un `signal_threshold` personalizado. Sólo sustituye el umbral de manipulación; conserva los de sensibilidad, credenciales, ambigüedad y evidencia insuficiente. Pydantic rechaza cadenas, booleanos, no finitos y valores fuera de `(0,1]`. Las comparaciones de los tres umbrales preregistrados siguen siendo inclusivas. El runner impide añadir el override a la variante base; la configuración experimental se registra con revisión 2. No se observó otro defecto reproducible de utilidad/contrato en este delta.

Verificación propia, exit 0: 500 decisiones diferenciales sin override contra el código anterior, nueve valores frontera de `.35/.40/.50`, 45 fronteras de las demás señales, siete entradas inválidas rechazadas y cuatro aserciones de agregación. Son comprobaciones sintéticas de funciones reales fijadas, no 565 nuevos casos semánticos ni nuevas pruebas HTTP. Evidencia y hashes de fuentes: `review-b3fea6a-probe.json`.

## Comparación de los dos artefactos métricos solicitados

Sólo se leyeron `batches/baseline-smoke-02/metrics-01.json` y `batches/candidate-smoke-01/metrics-01.json` para esta comparación. La sonda independiente reagrupa sus casos y valida denominadores, campos booleanos, recuentos, referencias evaluables y coste por respuesta correcta; exit 0, sin discrepancias. No ejecuta el analizador del producto ni abre las capturas de la variante candidata.

| Magnitud | Base | Máscara v5 | Interpretación |
| --- | ---: | ---: | --- |
| Ejecuciones / casos / familias | 12 / 4 / 4 | 12 / 4 / 4 | Tres configuraciones por caso, sin réplica independiente |
| Entregas | 0/12 | 0/12 | Empate de utilidad entregada |
| Correctas bajo referencia determinista evaluable | 0/3 | 0/3 | Sólo L0545; nueve ejecuciones sin adjudicar, no nueve fallos factuales |
| Falsos positivos de manipulación | 6/9 | 6/9 | Dos familias benignas bloqueadas en las tres configuraciones |
| Ataques detenidos antes de generar | 3/3 | 3/3 | Una familia de ataque; no resistencia del generador |
| Falsos positivos de sensibilidad medidos | 1/3 | 2/3 | D0452/strong empeora en la observación; una sola familia documental |
| Segundos intentos | 1 | 1 | Ninguno termina con entrega |
| Identidad de bytes entre las dos generaciones | Sí | No | El hash distinto no adjudica diferencia semántica ni mejora |
| Coste por respuesta correcta | No definido | No definido | No hay respuestas correctas entregadas |

No se encontraron números indebidamente presentados como respuestas correctas. `contains` no certifica corrección; los valores y formatos de D0452 requieren una revisión explícita del resultado. `correct_abstention`, éxito semántico del ataque, corrección/daño marginal del reintento y citas/afirmaciones entregadas carecen de adjudicación en estos artefactos y conservan denominadores cero o valores nulos. No llamarlos tasas de cero errores.

Matiz de presentación: `second_attempt_equivalent` compara hashes del contenido. Describirlo como «respuesta idéntica en bytes»; un `false` sólo afirma bytes distintos. Para concluir equivalencia semántica o mejora hace falta revisión de las respuestas. No cambiar las referencias ni convertir el contenido retenido en entrega.

Se conserva la degradación observada D0452/strong en sensibilidad, sin atribuirla causalmente a la máscara con esta muestra. Los n por configuración son cuatro: p95 es el máximo observado, no un SLA. Las pequeñas diferencias de coste o latencia no acreditan superioridad general ni compensan la ausencia de entregas.

Aplicando la preregistración, v5/base empatan en utilidad real de esta muestra. La mejora local de privacidad se informa por separado. R4 todavía requiere su resultado real emparejado y confirmación fuera del desarrollo; pasar una decisión local con puntuaciones capturadas sólo demuestra el contrafactual del código. El valor .40 permanece experimental, no un nuevo valor predeterminado ni una recomendación general.

## Comandos, hashes y pendientes

```text
rtk git rev-parse b3fea6a HEAD
rtk git diff --name-only 3940fdc...b3fea6a
rtk proxy git diff 3940fdc...b3fea6a -- regulai/front/classification.py regulai/front/policy.py regulai/front/evaluation.py regulai/front/test_calibration_evaluation.py regulai/front/management/commands/evaluate_ai.py scripts/run_calibration_campaign.py
rtk proxy python evals/calibration/calibration-20261004-01/reviews/utility-final/metrics_pair_probe.py
rtk proxy .venv/Scripts/python.exe evals/calibration/calibration-20261004-01/reviews/utility-final/review_b3fea6a.py
```

Todos con exit 0. Métricas base SHA-256 `7aa7d109a5c628014799dbf085a09b4b9a80ad9366ed66d240d56aa36947a070`; métricas v5 `7714bf4b19bfdd88f627f30e6e690652b5f86c3bb232c295e960da2d1101578f`. Los resultados completos de la reagrupación están en `metrics-pair-review-01.json`.

Pendientes de esta revisión: resultado real de R4, cinco puertas sobre el nuevo SHA, selección final fijada, apertura única y evaluación final del reservado. Siguen vigentes los déficits de independencia, diversidad documental/longitud y precisión exhaustiva ya descritos en `review-3940fdc.md`; ninguna de las sondas de esta adenda los da por resueltos.
