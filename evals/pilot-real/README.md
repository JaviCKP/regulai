# Ensayo sintético inicial

Ocho casos, tres configuraciones, offline por defecto. `fault` y `economy_output` solo controlan fixtures offline. En vivo no se fabrica un rechazo o un segundo intento.

- `cases.jsonl`: entradas, documentos íntegramente ficticios y expectativas de controles.
- `manifest.json`: destinos/modelos/tarifas/rúbricas/configuración/semilla y hashes congelados. Los alias DeepSeek se declaran móviles.
- `authorization.pending.json`: **no autoriza gasto ni salida**. La fecha histórica del 2 de octubre no se reutiliza.
- `rubric.md`: instrucciones de revisión humana, todavía sin revisores ni resultados.

El comando real comparte un único ledger y lock con evaluate_ai. Antes de cada transporte revalida aprobación y manifest; un resultado incierto conserva reserva. El destino de máscara real no está definido; el acceso TypeSafe directo no está comprobado. El preflight los rechaza sin red.

[Propuesta de aprobación, tarifas oficiales, dependencias, parada y recuperación](../../docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md). [Resultados nuevos](../reports/pilot-evaluation-20261003-01/README.md). No calidad ni ahorro reales medidos.
