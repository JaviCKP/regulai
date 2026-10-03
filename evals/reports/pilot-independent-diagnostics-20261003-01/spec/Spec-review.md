# Spec review — diagnóstico aditivo

**Sin hallazgos abiertos ni cambios propuestos al producto.** Revisión independiente de `535eb9d` → `972edb88c82a5220a43ffcc89316a9f9033e82f7`, limitada al contrato solicitado: conservar el control de envío y añadir una causa segura para fallos futuros.

`chat_service.py:31–36,591–599` solo conserva códigos de una lista cerrada; valores desconocidos pasan a `unknown_jev_error`. El mensaje de error deja de afirmar que no hubo envío. El juez utiliza también el código saneado al registrar su fallo. `evaluation.py:266` propaga el campo al metadato de liquidación sin modificar coste, reserva ni estado.

Ejecuté las mismas **cinco pruebas propias** contra ambos commits: **5/5 OK en cada snapshot, código 0**. Los once resultados comparados tienen exactamente el mismo SHA256 después de excluir únicamente `duration_ms` y `provider_error_code` de los recibos: `780281cd5eb9e43e148b2f3332bc5debac3643bb46432a3a231e9acb1f848e9b`. Se comparan estados HTTP/aplicación, causa pública, costes/cotas, rutas, verificación, límites y consentimiento. La corrección deliberada del texto público se revisó en el diff.

Las pruebas cubren las tres entradas HTTP con 401 y 599; un código del juez con salto de línea y contenido sintético privado; éxito y consentimiento sin diagnóstico espurio; repetición de un registro sin causa, que conserva sus datos y no reenvía; y liquidación mediante observador falso. El nuevo código no filtra el contenido sintético en la respuesta ni en los logs capturados.

El diff no cambia políticas, rutas, rúbricas, reintentos, presupuesto ni evidencias bajo `evals/`. **La causa de la clasificación incierta del ensayo anterior sigue desconocida**: no la infiero de estas pruebas ni modifico su registro.

Límites: SQLite de pruebas en memoria; transporte HTTP simulado y sockets/DNS bloqueados; observador contable falso, sin abrir un ledger persistente. No ejecuté el puente ni leí bases/claves del usuario. Cero llamadas reales y gasto. No repetí las suites de 73/387 pruebas informadas por otros agentes. Solo añadí archivos propios en `.claude/review-diagnostics-spec/`; comandos, salidas y hashes están en `evidence.json`, y `package-files.json` enumera la evidencia pública.
