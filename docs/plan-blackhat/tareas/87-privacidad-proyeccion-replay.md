# 87 — E5 — Presentación y replay

Status: implementación completa; navegador y matriz extendida en E7.
Blocked by: [86](86-privacidad-envios-historial.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E5 y criterios de la sección 11.

Aceptación: Proyección autorizada normal/agente, segmentos atómicos, replay idempotente y renderizado seguro sin alterar offsets ni recibos.

Verificación observada: parser E1 y 5 pruebas de presentación con dos consumidores, permisos, purga y valores opacos; 23 pruebas backend focalizadas pasan. npm run verify: 48 pruebas y build. Proyección separada del canónico, deltas derivados con offsets protegidos, parser por consumidor/inferencia; reconstrucción una vez al reanudar agente fuera del lock del escritor, fallback a snapshot HTTP si un frame expandido excede su límite. Copia natural reautoriza; protegida obtiene revisión canónica sin destinos Markdown. React y legacy pintan originales como texto literal. Interfaz E6, capturas, más regresiones y comparación con main en E7. Datos exclusivamente sintéticos; sin activación real, push ni integración en main.
