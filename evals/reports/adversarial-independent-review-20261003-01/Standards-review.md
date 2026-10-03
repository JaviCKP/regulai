# Standards review

Revisión independiente del mismo diff fijo `21bdd9f → df91ea1` y seguimiento `128d66a`, realizada por el revisor de requisitos, sin participar en la implementación. Se mantuvieron ambos ejes separados en los informes; no se abrieron más agentes por el límite de concurrencia indicado.

**Sin incumplimientos documentados abiertos ni sugerencias de refactorización necesarias para aceptar este alcance.** Fuentes: `AGENTS.md`, instrucciones RTK, `docs/agents/domain.md`, `docs/agents/issue-tracker.md`, skill `code-review` y preparación previa basada en `llm-app-code`, `numerical-care`, `api-surface-care`.

La extensión mantiene el dinero en Decimal, SQL parametrizado, lock de ejecución y transacciones breves sin transporte. Evoluciona la persistencia con tablas aditivas; no reescribe el ancla ni movimientos históricos. Constructor y reserva validan la cabeza, mientras la CLI separa validación de alta explícita. La reclamación durable evita reiniciar una pasada tras caída. Los metadatos de identidad y conteo no se pueden cambiar mediante la liquidación.

El P2 de informe incoherente se registra en Spec, sin duplicarlo como infracción de estilo. La corrección añade rechazo explícito al cambio de aprobación, y sus pruebas comprueban ausencia de efectos secundarios.

El runner intercepta la frontera del SDK/HTTPAdapter; no sustituye el servicio de chat por una respuesta prefijada. Declara que clasificador, juez y generador son fixtures; conserva fallos del detector y de controles por separado. La salida 0 significa integridad de ejecución, no todas las expectativas verdes. Tres HTTP usan adaptadores reales con Django Client, no sockets de servidor vivo. Fuentes y dataset se congelan por hash; límites de anonimización, semántica, documentos y muestreo quedan explícitos.

La preparación del puente usa sustituciones de texto sobre un script histórico concreto. Es una dependencia estrecha deliberada, revisada estáticamente mediante identidad exacta de la función de credenciales y hashes del origen/destino; no justifica introducir una abstracción adicional aquí. No se ejecutó.

Recomendación: conservar los resultados negativos y el permiso pendiente; no convertir métricas de anotaciones o fixtures en afirmaciones de eficacia empresarial. Ningún cambio de producto, corpus, índice o evidencia histórica realizado por este revisor.
