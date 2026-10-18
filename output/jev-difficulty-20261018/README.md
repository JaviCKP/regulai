# Jev: dificultad también en el agente

Aplicado y verificado localmente el 18 de octubre de 2026.

La empresa tenía clave Jev y ruta auto/difficulty, con clasificación local.
El chat normal consultaba la dificultad; el agente sólo consultaba Jev cuando
la clasificación era obligatoria. Los tres últimos recibos conservaban
not_consulted/classification_local. No era un error del proveedor.

## Comportamiento

| Configuración | Antes | Ahora |
| --- | --- | --- |
| Agente local + auto/difficulty | 0 consultas Jev | 1 evaluación de dificultad por inferencia nueva |
| Repetición de la misma inferencia | Sin consulta adicional | Sin consulta adicional |
| Clasificación obligatoria | 1 evaluación completa | 1 evaluación completa, sin segunda consulta de dificultad |
| Ruta manual o auto/quality y clasificación local | Sin evaluación Jev | Igual |

El modelo sigue fijado por el perfil del agente. La dificultad se evalúa y se
registra; no concede permisos, reduce sensibilidad ni cambia automáticamente de
modelo. La clasificación completa y la verificación final conservan su política.
No se añaden textos a la interfaz ni se reescriben recibos históricos.

La evaluación usa el contexto protegido, el contrato difficulty-v1 y el gobierno
existente: autorización fresca, YARA, presupuesto, revocación, contabilidad e
idempotencia. No hay caché de evaluaciones Jev entre inferencias. Cada nueva
inferencia, incluida una continuación con herramientas, puede generar una nueva
consulta; la clasificación obligatoria tiene prioridad y evita duplicarla.

También se corrige el resumen Jev cuando una respuesta llega tras cancelar: se
deriva del recibo de la llamada registrada, conservando la cancelación, entrega e
historial. El test existente de cancelación fallaba también con HEAD anterior.

## Verificación

- Regresión roja observada antes del cambio: cero consultas donde se esperaba
  una; sin clave continuaba generando. Tras el cambio, 31 pruebas de dificultad y
  transparencia pasan en SQLite.
- Imagen candidata: 93 pruebas PostgreSQL pasan sin errores, fallos ni omisiones.
  Incluyen las tres entradas HTTP, el recibo público que consume la interfaz,
  privacidad, concurrencia, replay, errores, costes, revocaciones y controles de
  consultas de las optimizaciones anteriores.
- Reinicio y reversión: 17 pruebas offline, incluidos fallos parciales.
- Proveedores simulados en red interna y PostgreSQL efímero; cero llamadas de
  pago. Contenedores y red de pruebas retirados.
- Comprobación instalada de sólo lectura: el selector devuelve difficulty con
  la configuración real y clave presente. Cero trabajos activos o inciertos.

La primera suite PostgreSQL no pudo importar test_chat_island; se añadieron sus
fixtures a los montajes de prueba y se repitió íntegramente. No se eliminó
cobertura. El primer intento de activación detectó el worker detenido tras
reiniciar web y restauró web. Se recuperó el mismo worker y se corrigió la
conmutación coordinada de ambos servicios. El contenedor candidato fallido fue
retirado. El segundo intento y la verificación posterior fueron correctos.

## Instalación y reversión

Único archivo de aplicación sustituido: regulai/front/agents/service.py.
La nueva imagen 82417497 deriva de la imagen instalada 11d2287c. Se conservaron
las fuentes de recuperación del chat 12 y las mejoras previas de latencia.
El worker se reinició con el mismo ID, imagen, configuración y claves.
No hubo migraciones ni cambios de políticas. La comparación de huellas confirma
que toda la base permanece idéntica desde la preparación inicial; también se
conservaron montajes, claves y checkpoints.

Desde C:\Users\javi\Documents\Codex\regulai-privacy:

~~~powershell
rtk proxy python ops/agent_chat/jev_local.py verify
rtk proxy python ops/agent_chat/jev_local.py rollback
~~~

Rollback exige ausencia de trabajos activos, recupera el web anterior retenido
y reinicia el mismo worker. No restaura una base antigua sobre datos nuevos.
Stage privado: /opt/regulai/updates/jev-difficulty-20261018-a1.
No hubo push ni publicación. Cloudflared sigue pendiente de la aclaración previa.

Para probarlo con uso real, enviar un mensaje nuevo en modo agente y abrir su
recibo: Jev debe figurar como consultado con propósito de dificultad, su decisión
y coste observado, salvo bloqueo previo o fallo del proveedor. Los recibos antiguos
no cambian. La consulta externa añade latencia y coste propios; no se ha medido
su tiempo real ni se afirma una mejora de velocidad con proveedores simulados.

Evidencia: [pruebas PostgreSQL](tests-1.json),
[pruebas del reinicio](helper-verification.json), [activación](apply-1.json),
[verificación](verify-1.json), [configuración instalada y conservación](post-activation.json).
