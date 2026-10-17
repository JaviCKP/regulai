# 92 — Diagnóstico de latencia antes de ejecutar en el chat 11

Status: diagnóstico completado el 17 de octubre de 2026; optimización pendiente.
Blocked by: ninguno. Alcance solicitado: identificar por qué tarda en arrancar.

Se inspeccionaron las dos ejecuciones completadas de la conversación 11, a las
17:08 y 17:09 de Madrid. No se reenviaron mensajes ni se invocaron proveedores.

| Tiempo registrado | Primera ejecución | Segunda ejecución |
| --- | ---: | ---: |
| Cola | 1,083 s | 0,382 s |
| Desde asignación hasta primer checkpoint | 16,585 s | 17,675 s |
| Guardado del checkpoint | 2,772 s | 2,948 s |
| Desde creación de inferencia hasta llamada registrada al modelo | 2,516 s | 3,110 s |
| Llamada registrada al modelo | 1,765 s | 1,135 s |
| Total, incluidos intervalos de transporte y cierre | 25,598 s | 26,040 s |

Los logs del worker confirman `sandbox_id: null` en ambos casos. El cuello de
botella principal está en la preparación local. La salida usa modo completo por
política, pero esa espera del modelo es pequeña frente a la preparación.

Causa localizada: `privacy.protect_tree` trata cada clave y valor textual como
una protección independiente. Cada fragmento vuelve a consultar empresa,
permisos, revisión, selección y registro del turno. El trabajo se repite incluso
cuando el fragmento ya está protegido. `jobs._bootstrap` prepara el catálogo
antes de delegar en `professional.bootstrap`, que vuelve a prepararlo. Después
se recorre de nuevo el objeto completo; el SDK también consulta su catálogo.

Perfil del código instalado con los fragmentos existentes, en un proceso de
diagnóstico sin escrituras ni tráfico de API:

- Catálogo: **1.990 SELECT**, 339 SAVEPOINT y 339 RELEASE, **3,35–3,73 s**.
- Bootstrap profesional, que incluye catálogo: **2.000 SELECT, 4,36 s**.
- Recorrido posterior del objeto completo: **3.446 SELECT, 5,79 s**.
- La primera petición generó 168 fragmentos `agent`; 156 tenían menos de 80
  caracteres. La segunda generó 173, de los que 160 eran cortos.

Las consultas se contaron con `execute_wrapper` y tiempos con `cProfile`.
Se rechazaron todas las escrituras SQL y conexiones de API; cada transacción
terminó en rollback. El perfil reutiliza contenido ya procesado y añade coste
de instrumentación: sus duraciones no son una descomposición exacta de la
ejecución histórica. Las trazas reales de la tabla son la referencia de latencia.

Corrección prioritaria propuesta: contexto de privacidad compartido dentro de
cada operación, protección agrupada y eliminación de la preparación duplicada
del catálogo. Conservar comprobaciones entre operaciones, revocación de permisos,
revisión inmutable, idempotencia, aislamiento entre cuentas y controles de salida.
No se ha modificado el comportamiento ni se afirma una mejora ya aplicada.

Evidencia sin contenido de mensajes ni secretos:
[tiempos](../../../output/latency-chat11-20261017/timings.json),
[perfil y consultas](../../../output/latency-chat11-20261017/profile.json).
Los scripts adyacentes documentan cómo se obtuvieron.
