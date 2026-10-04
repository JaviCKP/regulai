# Cierre independiente de seguridad y presupuesto

Commit revisado: `b3fea6a63761c06ef66695fee26377d23786c347`, con revisiones anteriores conservadas en `review-3940fdc.md` y `review-b3fea6a.md`. **La campaña pagada queda detenida por incertidumbre y no admite nuevas llamadas.** No se ha encontrado una violación del tope compartido ni liberación indebida de la reserva. R4 0,40 permanece sin confirmar y no se selecciona; el candidato final conserva v5 con política predeterminada `manipulation_threshold=None`.

## Parada y causa comprobada

`r4-smoke-01/live-run-01` completó cinco de las doce combinaciones previstas entre `08:31:38.601551Z` y `08:31:55.530040Z`, con once transportes HTTP: cinco clasificaciones, tres generaciones y tres verificaciones. El ejecutor terminó con exit 1 y `failed_or_uncertain_provider_call`. La quinta combinación, `P0619/router`, se detiene en clasificación; no entrega respuesta ni genera después del error.

El último transporte devolvió HTTP 200 y un cuerpo JSON completo, SHA `71b2f1e89094e6574bad9e1f09ec746b7c3aac7b41d3746cb92c1160f7a4e4da`. Las probabilidades de categoría suman **0,99**: `0,09 + 0,20 + 0,13 + 0,02 + 0,55`. El parser exige una distribución normalizada con tolerancia `1e-6`. Un replay estrictamente local del cuerpo capturado sobre el parser del commit fijo reproduce `invalid_response`, `outcome_unknown=True`, sin devolver un `JevResult` válido.

Una copia contrafactual local que cambia únicamente la masa confidencial de 0,55 a 0,56 pasa ese validador, lo que identifica el defecto del contrato. No se cambió la respuesta original, ningún oráculo o resultado del banco, ni se utilizó esa copia para clasificar contenido o liquidar costes.

El cuerpo contiene `provider_metadata.gateway.cost="0.000035742"`. **Ese importe es una factura/coste capturado dentro de una respuesta inválida, no un cargo validado.** La causa reproducida no es que ese número monetario tenga formato incorrecto; es la distribución de clasificación inválida. El asiento permanece `outcome_unknown`, `cost=null`, `cost_kind=unknown`, con reserva íntegra de `0.003 USD`. No se reclasifica como éxito, cero o coste comunicado seguro.

La captura termina en ese evento y el snapshot final del ledger termina en ese asiento; no aparecen un reintento ni llamadas posteriores. Se conservan sin cambios todos los asientos que existían en el snapshot del lote candidato anterior. El fallo observado confirma que el cierre conservador funciona; no demuestra que R4 sea una configuración semántica aceptable.

## Reconciliación del presupuesto

Los totales se recomputaron desde todos los asientos del artefacto final `batches/r4-smoke-01/live-run-01/budget.json`, SHA `bdf26d430f6420e477fab132365842dda210ee51a33fa3842625872923ca34ec`, sin abrir ni modificar el SQLite real.

| Concepto compartido, incluido el historial | USD |
| --- | ---: |
| Coste comunicado validado | 0.002794596 |
| Estimación por tarifas | 0.00961932 |
| Suma conocida comunicada + estimada | 0.012413916 |
| Reservas inciertas: 0,003 histórica + 0,003 nueva | 0.006 |
| Exposición conservadora total | 0.076271376 |
| Techo operativo agregado | 1.66 |
| Saldo contable bajo ese techo; no permiso para seguir gastando | 1.583728624 |

Las estimaciones por tarifa conservan sus reservas cuando éstas son mayores; por eso la exposición supera la suma conocida e incierta. La exposición convertida con el cambio congelado y el margen del 35 % equivale a `0.09172949452115812917594654788 EUR`; es una conversión conservadora de exposición, no un cargo bancario observado. El techo completo de 1,66 USD mantiene la equivalencia máxima ya revisada de aproximadamente 1,99644 EUR.

Los tres lotes de esta campaña suman **49 llamadas externas** registradas: 19 base, 19 candidato v5 y 11 R4. Hay 48 completadas y una incierta nueva; esto no sustituye el historial anterior, que también participa en los totales compartidos. Los límites por llamada, generaciones máximas y ventana original permanecen satisfechos. No se ha gastado el remanente ni se ha liberado la reserva para continuar la campaña.

## Candidato y puertas

`final_selection.json`, SHA `a33dad5bcb906f0bf26b55dfab04aa90be2f299faa4780216f157c68282d72a5`, selecciona provisionalmente `privacy-v5-legacy-policy`, registra el cese de pagos y prohíbe ajustar después del reservado. El fichero de configuración final coincide con el hash fijado `d8038364b6c01aec5159c73d7f938d4dd4c1c2be5db131ceb8df884eb715d5da`: máscara obligatoria v5, clasificación requerida, verificación `enforce`, `signal_threshold=0.2` y `manipulation_threshold=null`. El ensayo R4 queda expresamente sin adoptar.

Se verificaron los hashes y exits de los logs de `gates-02/manifest.json`, SHA `87c992525975f86af98db031f9afac7af666e6da7954af861d7e7813e723035e`, sobre el mismo commit y fuentes que el pack:

- `check`: exit 0, sin incidencias.
- Suite front/api: exit 0, 452 pruebas con dos limitaciones NER esperadas.
- Migraciones: exit 0, sin cambios detectados.
- Evaluación offline: exit 0.
- Auditoría de dependencias principal y comprobación adicional PostgreSQL: exit 0, sin vulnerabilidades conocidas en lo auditable. La principal declara expresamente que `xx-ent-wiki-sm 3.8.0` no pudo auditarse porque no está en PyPI; no se extiende a ese paquete una afirmación de cobertura completa.

Son puertas centrales existentes cuyo contenido y hashes se verificaron; no se presentan como ejecuciones adicionales de este revisor ni como CI remota.

## Evidencia independiente nueva

Además de las 80 pruebas focales y cuatro sondas propias del delta ya documentadas, se ejecutó:

| Comando desde la raíz | Resultado |
| --- | --- |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\run_fixed_review.py --commit b3fea6a --label captured_invalid_probe --run-name captured-invalid-response` | exit 0, una prueba de replay sin red; log SHA `0795091b273cc276045d4e0127daa1d09cded1f8e78748afb2876066049d10ac` |
| `rtk proxy .venv\Scripts\python.exe -X utf8 evals\calibration\calibration-20261004-01\reviews\security-final\check_r4_stop.py` | exit 0, veinte comprobaciones de contabilidad, parada, límites y puertas |

Evidencia estructurada: `b3fea6a-captured-invalid-observed.json`, `b3fea6a-captured-invalid-response-execution.json` y `r4-final-stop-independent-check.json`. El replay usa una credencial ficticia y respuesta preparada, con sockets/DNS bloqueados. Ninguna prueba devuelve el cargo de la respuesta inválida al ledger.

Corrección cronológica del informe de delta: su frase «previo al ensayo» describía el encargo, pero la comprobación integral del pack registrada a las 08:32 UTC terminó después de los transportes reales de 08:31 UTC. La lectura y las pruebas focales se habían comunicado antes. No debe presentarse el informe completo de 08:32 como una puerta temporal anterior a esas llamadas; la autorización procedía del encargo expreso del usuario.

## Límites del cierre

No hay hallazgos nuevos reproducibles de seguridad o presupuesto que exijan modificar este runtime para conservar el cierre observado. Los tres P2 anteriores permanecen corregidos en sus reproducciones. Esto no promete detección universal, calidad semántica general ni una campaña real completa: R4 y la confirmación remota quedan incompletos por la condición obligatoria de parada.

El reservado y `scripts/build_calibration_corpus.py` permanecen sin leer por este revisor. La comparación local reservada posterior corresponde a otro artefacto y no se acredita aquí. No hubo llamadas de proveedor nuevas, cambios en el ledger, credenciales reales, apertura de la base del usuario, modificaciones de runtime, commits o publicación por el revisor. Todos sus archivos están en `reviews/security-final/` y conservan la evidencia previa.
