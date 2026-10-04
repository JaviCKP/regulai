# Revisión independiente del delta R4 — b3fea6a

Rango fijo: `3940fdc698c34998b2541309b0b697b6c06c2287...b3fea6a63761c06ef66695fee26377d23786c347`. Revisor delegado nuevo respecto a los autores del runtime; se conserva íntegra la revisión anterior `review-3940fdc.md`. Resultado previo al ensayo R4 comunicado al ejecutor central el 4 de octubre de 2026, a las 08:32 UTC aproximadamente.

**No se encontró una regresión reproducible de privacidad, autorización o presupuesto que bloquee el ensayo central de `r4-smoke-01` bajo la autorización existente.** No se declara aún una mejora semántica general: el umbral 0,4 reduce deliberadamente los bloqueos por manipulación con puntuación en `[0,2; 0,4)`. Sus consecuencias adversariales necesitan la evaluación prevista; esta revisión no crea otra aprobación humana.

## Superficie revisada

Se leyó el diff completo de los ocho archivos modificados de runtime y pruebas. `ClassificationPolicyConfig.manipulation_threshold` es opcional, estricto y finito en `(0,1]`; `None` y omisión conservan el umbral compartido previo. Sólo la condición de manipulación consulta el override. Los criterios de credenciales, datos personales, confidencialidad de negocio, ambigüedad y evidencia insuficiente conservan `signal_threshold`; también se conservan el suelo local, `unknown` y el bloqueo `restricted`.

El evaluador traslada el override desde el manifiesto firmado por hash a la política y lo versiona mediante revisión 2. El ejecutor de preparación limita las opciones a 0,35, 0,40 o 0,50 y rechaza el override para la base antes de crear el pack. El transporte real utiliza la política del pack; un argumento CLI nuevo no sustituye durante la ejecución una política congelada. No cambian ledger, reserva, guard de credenciales, plazo, destinos ni número máximo de generaciones. El cambio de agregados distingue mejora de respuesta retenida y beneficio realmente entregado; ausencia de medición permanece `null`.

Sin hallazgos nuevos P0/P1/P2 en este delta acotado. El hecho de conservar la privacidad no demuestra que una puntuación de manipulación inferior a 0,4 sea siempre benigna.

## Pruebas independientes nuevas

Sobre un snapshot `git archive` del commit fijo se ejecutaron **84 pruebas, todas correctas**:

- 80 de los módulos de manipulación, clasificación, presupuesto, evaluación y runner. Incluyen doce subcasos de benigno/ataque/credenciales/PII a través de los tres accesos HTTP con SDK y captura del transporte sin sockets reales. Las credenciales a 0,2 siguen bloqueadas incluso hacia destino privado; PII a 0,2 conserva nivel confidencial. Se conservan las regresiones de reflexión de claves, límites y autorización.
- Cuatro sondas propias en `r4_independent_probes.py`: 1.536 combinaciones con override omitido/`None` comparadas contra la función real de `3940fdc`; 3.072 mezclas de las otras cinco señales comparadas contra la función anterior; doce combinaciones que mantienen el bloqueo de credenciales en presencia de manipulación por debajo del nuevo límite; siete entradas de proveedor malformadas que siguen cerrando el flujo.

Las 4.627 combinaciones internas son comprobaciones deterministas, no observaciones independientes de modelos ni del corpus semántico.

| Comando desde la raíz | Resultado | Registro |
| --- | --- | --- |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit b3fea6a --label front.test_calibration_manipulation --label front.test_classification --label front.test_calibration_budget --label front.test_calibration_evaluation --label front.test_calibration_runner --run-name delta-focal` | exit 0, 80 pruebas | `b3fea6a-delta-focal-execution.json`; log SHA `d2c44ca1ea2d1c645b72d48eba91ec6fd023019320f33cb626fdac66dfd9ba0b` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit b3fea6a --label r4_independent_probes --run-name independent-policy-grid` | exit 0, 4 pruebas | `b3fea6a-independent-policy-grid-execution.json`; log SHA `4521d360e672fa8fa8a99682bab2e22e8520febedd613808a85ca8cfe85d3404` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\check_r4_pack.py` | exit 0, 22 comprobaciones | `r4-smoke-01-independent-check.json` |

La advertencia `staticfiles.W004` corresponde a la exclusión deliberada de assets estáticos del snapshot de revisión. No se repitió la suite NER en este delta: su código no cambia y sus dos limitaciones esperadas permanecen documentadas en la revisión anterior.

## Paquete y gasto

El manifiesto `07c306ebf6e5ad258b3ad4a282cb34476e4d6f370d07d7a47fddb0fc19ed56d6` y autorización `0cd59edcb186ba81f3c5ab7e3e86f3d9d8e002c2281535f1c7013b6403d0c0a2` coinciden con el pack recibido. Coinciden sus fuentes congeladas y las del checkout con el nuevo commit; trece diferencias de bytes Git/checkout son exclusivamente CRLF frente a LF y están listadas. Los hashes de casos, oráculos y rúbrica son idénticos a la muestra inicial ya revisada. El override congelado contiene únicamente `manipulation_threshold: 0.4`; la máscara es v5, clasificación obligatoria y verificación `enforce`.

La extensión enlaza por identidad y digest canónico con `candidate-smoke-01`. Su artefacto final `live-run-01/budget.json`, SHA `5184dd0dfa87ebe51592152533b91bebdf1e97eabdfd70541a7bfee80b3f5cb4`, declara exposición compartida `0.065225712 USD`, incluyendo historial y `0.003 USD` de reserva incierta. El máximo adicional permanece `0.308 USD` para doce combinaciones y 44 llamadas; el peor total resultante es `0.373225712 USD`. Cabe en el tope de desarrollo `1.0113763512 USD` y preserva `0.6486236488 USD` para confirmación. El techo global, conversión, margen y ventana no cambian.

La comprobación usa el artefacto de presupuesto ya finalizado, no el ledger vivo. Corresponde al ejecutor central verificar cabeza, exposición y ventana al activar y en la frontera de cada envío. No se recalcularon precios mediante nuevas consultas ni se reabrió investigación de token usage.

## Pendiente de cierre

Las cinco puertas tras el último cambio, los resultados reales de R4/confirmación y la reconciliación final llegarán por separado. Esta revisión no abre el reservado ni su generador, no ajusta el candidato y no certifica la calidad de sus respuestas. No hubo llamadas pagadas, acceso a credenciales, base del usuario, ledger real, modificaciones de runtime, commits ni push por el revisor. Las únicas escrituras están bajo `reviews/security-final/`.
