# 86 — E4 — Envíos e historial

Status: implementación completa; matriz extendida de regresión en E7.
Blocked by: [85](85-privacidad-politica-detectores.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E4 y criterios de la sección 11.

Aceptación: Tres entradas HTTP y agente con el mismo contrato; todos los destinos externos capturados y fallos sin salida.

Verificación observada: 37 pruebas de privacidad y flujo de chat pasan en PostgreSQL desechable; tras el endurecimiento adicional, 18 pruebas de política/HTTP/agente pasan. Captura del transporte HTTP real del SDK en las tres entradas, clasificador y juez, generación/compacción del agente, reintentos y bloqueo de archivos. La revisión independiente encontró fronteras de metadatos, skills, paginación y posiciones: corregidas, con regresiones de posiciones, literal repetitivo y comprobación final. Recursos binarios y restauración documental hacia workers se bloquean con esta política. La matriz extendida de herramientas/HTTP, comparación con main y evidencias finales se completan en E7. Datos exclusivamente sintéticos; sin activación real, push ni integración en main.
