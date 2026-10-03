# Ensayo sintético inicial

Ocho casos, tres configuraciones, offline por defecto. `fault` y `economy_output` solo controlan fixtures offline. En vivo no se fabrica un rechazo o un segundo intento.

- `cases.jsonl`: entradas, documentos íntegramente ficticios y expectativas de controles.
- `manifest.json`: destinos/modelos/tarifas/rúbricas/configuración/semilla y hashes congelados. Los alias DeepSeek se declaran móviles.
- `authorization.pending.json`: **no autoriza gasto ni salida**. La fecha histórica del 2 de octubre no se reutiliza.
- `rubric.md`: instrucciones de revisión humana, todavía sin revisores ni resultados.

El detector local real usa CPU, spaCy 3.8.16 y xx_ent_wiki_sm 3.8.0 más patrones de PII/secretos. Su identidad y los hashes del código/modelo están fijados en el manifiesto. No usa endpoint HTTP, API de pago ni descarga automática. Es un detector heurístico: sus omisiones y falsos positivos necesitan evaluación humana; no garantiza anonimización completa.

El comando real comparte un único ledger y lock con evaluate_ai. Antes y después de reservar revalida aprobación y manifiesto; una llamada externa incierta conserva reserva. Las transformaciones locales reservan coste de API 0 y se contabilizan aparte. Solo DeepSeek y Jev son destinos externos propuestos, con contenido enmascarado. El acceso TypeSafe directo y la nueva autorización siguen pendientes; el preflight bloquea sin red.

[Propuesta de aprobación, tarifas oficiales, dependencias, parada y recuperación](../../docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md). [Evidencia local del detector](../reports/pilot-evaluation-local-20261003-01/README.md); [ensayo histórico de máscara simulada](../reports/pilot-evaluation-20261003-01/README.md). No calidad ni ahorro reales medidos.
