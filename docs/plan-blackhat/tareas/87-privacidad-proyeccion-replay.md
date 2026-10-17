# 87 — E5 — Presentación y replay

Status: completada; navegador y matriz extendida cerrados en E7.
Blocked by: [86](86-privacidad-envios-historial.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E5 y criterios de la sección 11.

Aceptación: Proyección autorizada normal/agente, segmentos atómicos, replay idempotente y renderizado seguro sin alterar offsets ni recibos.

Verificación observada: [matriz final](../entrega-privacidad-20261017.md), 60 pruebas de privacidad y 49 de frontend. Proyección separada del canónico, deltas con offsets protegidos, parser por consumidor/inferencia; reconstrucción al reanudar fuera del lock del escritor, snapshot si un frame excede su límite. Cancelación, replay, dos consumidores, permisos actuales y contexto irreversible comprobados. React/legacy pintan originales opacos y la copia natural reautoriza. Capturas y vídeo acreditan la restauración durante streaming y tras recarga.
