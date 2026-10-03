# Evaluación con detector local — 3 octubre de 2026

Preparación offline. **Cero llamadas nuevas de producto, cero USD de APIs, cero revisiones humanas completadas.** No se leyeron credenciales reales ni se usó una base de usuario. La plantilla de autorización sigue pendiente y el límite conjunto propuesto sigue en 1 USD. Los importes estimados de los fixtures no son gasto ni facturación.

Los bancos nuevos y la demo ejecutan el detector real local (spaCy 3.8.16, xx_ent_wiki_sm 3.8.0 y patrones), con respuesta/juez simulados y transporte externo bloqueado. El modelo instalado se identifica por `4f5b7a5c5baf29c9e940befeb1f02a3021acc22806e3c1cbcef48e2078a2477a`; el código del detector queda identificado en cada manifiesto observado. Las transformaciones locales conservan entradas del ledger a coste de API cero y no cuentan como llamadas externas. CPU, memoria y operación no se han valorado.

El gate focal definitivo `tests-focal-final.log` termina **40 tests OK, 76,796 segundos, exit 0**. Incluye 150 recorridos del banco histórico sin controles fallidos (más los casos alterados deliberadamente para comprobar que el evaluador detecta errores). La línea de PowerShell `NativeCommandError` al inicio es su representación de stderr de Django; el resultado del proceso se toma del código de salida y del resumen del runner.

## Informes finales

Ambos se ejecutaron sobre `ac9eb745cf201fd3378799a8a7bb6fab68ab5cb6`; fuentes, runtime e identidad del detector declarados coinciden con lo observado. No se modificó código durante esos procesos. Los dos corrieron simultáneamente en procesos/bases/ledgers offline separados: sus latencias incluyen carga concurrente. El modo real sigue usando un único ledger persistente compartido.

| Informe | Recorridos / controles previstos | Transformaciones locales | Llamadas externas simuladas | Estimación con tokens ficticios USD | Exposición simulada USD | Exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [smoke-local-final](smoke-local-final/report.md) | 24 / 24 | 38 | 54 | 0,00240900 | 0,13905828 | 0 |
| [human-local-final](human-local-final/report.md) | 72 / 72 | 120 | 180 | 0,00663600 | 0,45566592 | 0 |

Son controles de recorrido, no aciertos humanos ni precisión de proveedores. Revisiones humanas completadas: **0**. Coste real de APIs: **0 USD**. El cómputo local no tiene tarifa de API, pero no se ha calculado su coste operativo. Los informes contienen p50/p95 y n por configuración y split, además de las respuestas/evidencias originales de cada resultado.

`preflight-final.json` y `human-preflight-final.json` confirman identidad/fuentes/runtime y continúan con `ready_for_real=false`, cero red y sin crear directorios de ejecución. Faltan aprobación/ventana, aceptación de alias, revisión tarifaria ligada a esa aprobación y credenciales aisladas; en el banco humano además autorización de reservados y revisión independiente de referencias. No queda pendiente una URL de máscara: la propuesta usa el detector local.

## Resultados intermedios conservados

| Evidencia | Resultado | Interpretación |
| --- | --- | --- |
| `tests-focal-01.log` | 38 tests; 2 fallos y 3 errores; exit 1 | Proceso que había cargado el detector anterior a la corrección de identificadores estructurales de citas. No representa el código final. |
| `smoke-local-01/` | 24 recorridos; 24 controles previstos; exit 0 | Detector corregido; 38 transformaciones locales, 54 llamadas simuladas de generación/juez y cero llamadas reales. Snapshot intermedio, anterior al cierre de fuentes. |
| `tests-focal-02.log` | 40 tests; 1 fallo y 1 error; exit 1 | Persistían seis diferencias literales al aplicar NER al banco histórico de 50 casos. |
| `legacy-local-01/` | 150 recorridos; 144 controles previstos; 6 discrepancias; exit 1 | Evidencia íntegra de esas transformaciones, sin retocar casos ni expectativas. |
| `legacy-ner-diagnosis.json` | 2 respuestas de desarrollo transformadas, red bloqueada; exit 0 | «Ana, Luis, Marta» se oculta como personas; «Único» también se marca como persona (falso positivo contextual). |

Cada uno de los dos casos difiere en las tres configuraciones. Se conserva esta limitación sin excepcionar nombres/palabras ni ajustar el modelo a los resultados. El banco histórico vuelve a usar su fixture HTTP de identidad, explícitamente rotulado, para mantener el contrato original de regresión literal. Los bancos nuevos y la demo mantienen el detector real. Casos, rúbricas, etiquetas y umbrales no se han cambiado.

## Alcance de las pruebas

Las pruebas del modo real usan el servicio, ledger, SDK y clientes habituales, pero interceptan el transporte HTTP con datos sintéticos. Comprueban reserva previa, liquidación, incertidumbre de fallos/timeout externos, revocación/caducidad después de reservar (SEC-1), cambios del modelo, coste local cero incluso ante fallo y ausencia del email original en payloads de DeepSeek/Jev. El fallo de una máscara local no selecciona un destino remoto. Las pruebas HTTP de compatibilidad permanecen separadas.

Los reportes por caso guardan respuestas, citas, cobertura, sensibilidad, segundos intentos, costes y trazas. Las plantillas de revisión humana permanecen vacías; acierto/coste por respuesta correcta, calidad y ahorro no se infieren del juez prefijado. p50/p95 describen esta muestra y esta máquina bajo carga local, no un SLA.

## Dependencias para uso real

Revisar límites y errores del detector con datos representativos; disponer de credenciales aisladas y acceso directo a TypeSafe (el Gateway histórico no lo prueba); revisar el mismo día tarifas/modelos; y obtener una autorización nueva explícita para los hashes exactos, destinos DeepSeek/Jev, datos sintéticos, acciones, ventana y techo conjunto. La revisión humana requiere dos personas reales. Nada en esta evidencia concede aprobación, compra créditos, publica ni despliega.

[Propuesta revisable, parada y recuperación](../../../docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md). Los informes de [la preparación anterior](../pilot-evaluation-20261003-01/README.md) se mantienen sin cambios.
