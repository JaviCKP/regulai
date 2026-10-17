# 84 — E2 — Modelo y servicio común

Status: completada; integración y validación local cerradas en E7.
Blocked by: [83](83-privacidad-contrato-vertical.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E2 y criterios de la sección 11.

Aceptación: Contrato independiente de AgentExecution; registro existente, revisión, permisos, unicidad y migraciones aditivas desactivadas.

Verificación observada: 13 pruebas OK sobre PostgreSQL 18 desechable en puerto 55483, un único proceso Django. Cuatro escritores concurrentes obtienen un solo alias; conservación de alias anterior, cifrado real, rotación de claves HMAC, secretos irreversibles, ámbito, empresa actual, revisión fija y revocación. El adaptador del agente mantiene la operación documental restringida; `front/privacy.py` no depende de AgentExecution. Migración 0044 exclusivamente aditiva, sin cambios en empresas ni alias previos. Avance/reversión completa queda en E7.

Decisión: las configuraciones con diccionarios y las variantes de presentación se cifran; la política pública sólo referenciará una revisión inmutable. No se persiste proyección natural. El contador de uso tiene unicidad por turno/llamada/alias y las apariciones por mensaje/rango, separado de los recibos existentes.

Cierre consolidado: [entrega y matriz](../entrega-privacidad-20261017.md). Migraciones 0044/0045 avanzadas y revertidas en PostgreSQL desechable, ciphertext anterior intacto; rotación de cifrado y HMAC comprobadas.
