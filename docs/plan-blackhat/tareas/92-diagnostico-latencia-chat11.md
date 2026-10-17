# 92 — Diagnóstico de latencia antes de ejecutar en el chat 11

Status: diagnóstico completado el 17 de octubre de 2026; optimización aplicada y verificada localmente.
Blocked by: ninguno. Alcance: diagnóstico, optimización y activación local.

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
El diagnóstico inicial no modificó el comportamiento; la implementación posterior se documenta debajo.

Evidencia sin contenido de mensajes ni secretos:
[tiempos](../../../output/latency-chat11-20261017/timings.json),
[perfil y consultas](../../../output/latency-chat11-20261017/profile.json).
Los scripts adyacentes documentan cómo se obtuvieron.



## Optimización aplicada el 17 de octubre de 2026

El bootstrap profesional prepara el catálogo una sola vez. Instalaciones y
autorizaciones se leen con un JOIN vigente por operación. El SDK conserva una
copia independiente por ejecución, descartada con su backend; la ruta compatible
carga una vez y verifica el digest. Esta copia no concede autoridad: recursos,
herramientas e inferencias siguen validando permisos en servidor.

Privacidad agrupa lecturas, alias y escrituras. El contexto de empresa, permisos
y revisión vive solo durante esa operación. Las claves de usuario siguen pasando
por selección sensible y YARA; los campos estructurales conservan tipos y límites.
La prueba de escala mantiene 10 SELECT para objetos neutros de 1 y 200 claves
(antes 25 y 5.200). Con 1 y 80 valores sensibles mantiene 11 (antes 13 y 1.041).

La inferencia protege juntos los mensajes pendientes, con lotes limitados por
bytes serializados reales, expansión de alias y 4.096 fragmentos. YARA recibe los
textos originales separados. La caché de historial conserva ejecución, intento,
autoridad, política, máscaras y mensaje exacto en su clave, publica solo lotes
completos y devuelve copias independientes. No se amplió su alcance.

Los checkpoints agrupan ambas representaciones en una lista y reasignan sus
campos explícitamente. La prueba adversarial selecciona literalmente
`messages`/`wire_messages` y comprueba el registro persistido y la recuperación.
Se mantienen identidad, watermark, operaciones pendientes y autorización al
recuperar. La referencia del catálogo comprueba identidad y hashes sin proteger
otra vez todo el catálogo.

El worker usa LISTEN/NOTIFY transaccional, sin contenido en el aviso. Se suscribe
antes de comprobar la cola, espera sin transacción ni bloqueo y vuelve a verificar
estado y permisos. Hay un máximo de cuatro esperas por proceso, plazo de cinco
segundos y respaldo acotado de 500 ms. El claim duradero y su identidad de reintento
siguen evitando ejecuciones duplicadas. También se notifica al liberar capacidad.

No hay migraciones ni dependencias nuevas. No se modificó texto de interfaz.
Cada salida conserva validación actual, YARA, aislamiento y contabilidad.

## Medición y aceptación

Comparación con las imágenes originales y finales, copias del mismo backup,
SDK y dispatcher reales por HTTP y proveedor simulado en el límite de red.
Alterna `Hola` y un correo sintético; recorre `/chat/`, `/chat/send/` y
`/api/chat/send/`, con catálogo automático. Las 42 ejecuciones completaron
exactamente una inferencia y un checkpoint. Se bloqueó la red externa.

| Medida | Antes | Después |
| --- | ---: | ---: |
| Preparación caliente, p95 (18 por variante) | 23,152 s | 1,423 s |
| Preparación simple caliente, p95 (9) | 22,862 s | 1,318 s |
| Preparación fría de proceso, máximo (3) | 20,147 s | 2,740 s |
| Cola, p95 (21) | 0,521 s | 0,203 s |
| Primera inferencia desde creación, caliente p95 (18) | 23,607 s | 1,565 s |
| SELECT de preparación, mensaje simple | 15.922 | 525 |
| SELECT de preparación, mensaje sensible | 15.929 | 532 |
| Lectura directa de catálogo, SELECT (5) | 1.990 | 12 |
| Lectura directa de catálogo, mediana (5) | 2,004 s | 0,018 s |

Objetivos observados cumplidos: preparación simple p95 inferior a 3 segundos
(incluyendo las primeras ejecuciones) y cola p95 inferior a 500 ms con capacidad.
El banco independiente de cola con dos trabajos concurrentes pasa de 471,6 a
177,6 ms p95; excluye el transporte HTTP del claim. La prueba ASGI verifica que
dos claims en espera no bloquean una inferencia HTTP simultánea.

Se distinguen tres primeros mensajes de procesos nuevos y dieciocho mensajes
calientes por variante. Frío significa primera ejecución con Django inicializado;
no implica caché del sistema operativo o PostgreSQL vacía ni incluye el arranque
de la VM. El p95 usa rango más próximo. Con nueve muestras simples calientes
coincide con el máximo. Los pilotos y el perfil con stacks se excluyen.
Las consultas de preparación terminan en el primer acceso al proveedor y
excluyen admisión, claim y consultas del propio banco.

La suite final de PostgreSQL ejecutó 108 pruebas sin fallos, errores ni omisiones:
tres entradas, privacidad, YARA, revocaciones entre protección y salida, catálogo,
checkpoints, migraciones, idempotencia y dinero. La verificación adicional de cola
cubre carreras, replay, revocación, fallos de notificación, concurrencia y capacidad.
SDK: 12 pruebas de protocolo/validación y 11 de materialización Linux (3 de validación solapadas); todas pasan. Recuperación y limpieza: 22 pruebas pasan; una de socket Unix se omite en Windows. Los informes detallan comandos y límites.

## Instalación local y reversión

Aplicado a `regulai-v2-web` y `regulai-v2-worker`; ambos activos sin reinicios.
Las imágenes activas coinciden con las medidas y probadas:
web `9aa14268c576`, worker `fbdd3ceacfae`.
La URL existente `http://127.0.0.1:8800/static/js/skills.js` responde 200.

Se compararon huellas de las tablas y secuencias existentes, configuración Docker,
redes, configuración y claves realmente montadas. Todo se conserva.
Los checkpoints en base de datos están incluidos en la huella; el directorio
de checkpoints del worker estaba vacío y sigue igual. No se generaron llamadas
a proveedores durante la activación.

La copia de la base de datos previa al cambio y el manifiesto de checkpoints se
conservan privados bajo `/opt/regulai/updates/latency-20261017-a1` dentro de la VM.
Los originales detenidos se conservan como
`regulai-v2-web-before-latency-20261017-a1` y
`regulai-v2-worker-before-latency-20261017-a1`.
La reversión cambia contenedores por identidad; no restaura automáticamente una
base de datos que pueda haber recibido datos posteriores. Requiere ausencia de
trabajo activo y configuración compatible. La recuperación ante fallos parciales
de parada, renombrado y arranque está cubierta con inyección de fallos.

Desde `C:\Users\javi\Documents\Codex\regulai-privacy`:

```powershell
rtk proxy python ops/agent_chat/latency_local.py verify
rtk proxy python ops/agent_chat/latency_local.py tests
rtk proxy python ops/agent_chat/latency_local.py bench-after --count 7 --round 13
rtk proxy python ops/agent_chat/latency_local.py rollback
```

Se eliminaron todos los contenedores y bases temporales del banco. Los artefactos y copias privadas se conservan. Para limpiar repeticiones posteriores: `rtk proxy python ops/agent_chat/latency_local.py cleanup-benchmarks`.

El benchmark crea una copia nueva y usa proveedor simulado; cada repetición
requiere un número libre (0–19). `rollback` es una acción opcional de reversión,
no parte de las pruebas. No se hizo push ni publicación.

Pendiente de caracterizar, fuera de esta muestra: historiales largos, catálogos
mayores, carga sostenida y latencia del proveedor real. El coste residual medido
está principalmente en las validaciones vigentes de inferencia; se conserva para
respetar revocaciones y salidas. No se extrapola este p95 a esas cargas.

Evidencias y reproducción:
[resumen](../../../output/latency-optimization-20261017/summary.md),
[muestras agregadas](../../../output/latency-optimization-20261017/summary.json),
[pruebas finales](../../../output/latency-optimization-20261017/tests-0.json),
[SDK](../../../output/latency-optimization-20261017/sdk-verification.json),
[montajes Linux](../../../output/latency-optimization-20261017/sdk-linux-mount-verification.json),
[cola y concurrencia](../../../output/latency-optimization-20261017/worker-verification.json),
[recuperación](../../../output/latency-optimization-20261017/installer-verification.json),
[activación](../../../output/latency-optimization-20261017/apply-0.json),
[verificación](../../../output/latency-optimization-20261017/verify-0.json).
