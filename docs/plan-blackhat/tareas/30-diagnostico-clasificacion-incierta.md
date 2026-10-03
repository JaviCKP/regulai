# 30 — Diagnosticar la clasificación incierta del ensayo real

**Status:** en diagnóstico local, sin nuevas llamadas.
**Blocked by:** la causa concreta del resultado externo no está conservada en el informe actual; se revisa qué puede reproducirse sin red.
**Propietario:** C (análisis aislado) y orquestador (integración).
**Especificación:** [07](../07-verificacion-y-escalado.md), [11](../11-evaluacion-reproducible.md), [ensayo autorizado 29](29-ensayo-autorizado-vercel.md).

La ejecución viva del commit `698e8f0` se detuvo tras ocho de las 24 combinaciones previstas, en `document-success/strong`, con `classification` en `outcome_unknown`. El ledger mantiene coste `null` y reserva de 0,003 USD. Se conservan 17 llamadas externas y 12 transformaciones locales. No se repite la llamada ni se continúa gastando durante este diagnóstico.

## Aceptación

- [ ] Contrastar el diario, las llamadas y la suma de costes sin contar dos veces las filas de resumen por split.
- [ ] Identificar únicamente lo que permite la evidencia; no atribuir un HTTP/timeout/contrato concreto sin datos.
- [ ] Reproducir sin red cualquier pérdida de código diagnóstico antes de corregirla.
- [ ] Si procede una corrección, conservar únicamente códigos seguros, con regresión; no cuerpos remotos, claves ni contenido sensible en logs.
- [ ] Conservar ledger, reservas, umbrales y resultados originales; revisión independiente de cualquier cambio de producto.
- [ ] Preparar una siguiente acción verificable, sin reintentar automáticamente resultados inciertos.

Observación inicial: la captura de excepción general en `chat_service.py` sustituye la causa segura de Jev por `security_check_failed` en clasificación. Su texto visible también dice que no se envió la petición, aunque hubo una salida al juez. La reproducción y el alcance de un posible corrector están pendientes; no se atribuye esa limitación como causa del fallo remoto.
