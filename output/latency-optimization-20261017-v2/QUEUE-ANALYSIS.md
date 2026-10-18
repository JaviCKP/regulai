# Residuo de cola y despacho

Inspección de código y artefactos existentes; no se han modificado producto,
configuración ni bancos. Fuentes: `bench-baseline-9-profile.json` y
`bench-after-9-profile.json`. Son **tres muestras diagnósticas instrumentadas** por
variante; no estiman p95 ni sustituyen la comparación formal.

La cola medida empieza en `AgentExecution.created_at` y termina en `started_at`.
El banco registra además un callback `transaction.on_commit` para separar admisión
y despacho. `started_at` se asigna después de autorizar el claim, antes de escribir
su evento, guardar el estado y responder HTTP. Por ello el coste completo de la
ruta de claim no es idéntico a `queue_dispatch_s`.

| Muestra | Antes: admisión / despacho / total (ms) | Después: admisión / despacho / total (ms) |
| --- | ---: | ---: |
| `/chat/`, primer mensaje de proceso, simple | 108,14 / 48,51 / 156,65 | 88,75 / 55,85 / 144,60 |
| `/chat/send/`, caliente, sensible | 98,85 / 64,62 / 163,47 | 54,02 / 43,53 / 97,54 |
| `/api/chat/send/`, caliente, simple | 87,84 / 60,78 / 148,63 | 60,48 / 68,80 / 129,28 |

En la muestra simple caliente final, la admisión y el despacho todavía aportan
60,48 y 68,80 ms. El span de `_context` fresco dentro del claim ocupa 45,65 ms de
ese despacho (23,61 ms de CPU del hilo). Los otros 23,15 ms incluyen las lecturas
y decisiones previas, entrega de notificación y planificación; no existe un span
que permita separar cada componente exactamente. Los tres spans finales de
`_context` duran 34,75 / 25,47 / 45,65 ms. El resultado no justifica atribuir el
residuo a un periodo fijo de polling ni eliminar la revalidación.

## Consultas y trabajo de la ruta

La ruta `/internal/agents/claim/` pasa de **35 a 24 SELECT** por muestra. Además
registra 1 SAVEPOINT, 1 INSERT, 1 RELEASE, 2 UPDATE, 1 LISTEN y 1 UNLISTEN: 31
sentencias registradas en la variante final. El desglose de sus 24 SELECT es:

| Operación | SELECT por petición de claim |
| --- | ---: |
| `reap`: ejecuciones vencidas | 2 |
| Adquisición del advisory lock de admisión | 2 |
| `_claim`: cola vencida, replay por claim_id y selección de candidato | 6 |
| Comprobación de capacidad activa global y de cuenta | 2 |
| Autorización actual: `_context` directo | 8 |
| Binding de skills, reglas activas y binding de grant | 3 |
| Persistencia ordenada del evento de claim | 1 |

Los duplicados en las tres primeras filas corresponden a dos comprobaciones
durables: una vacía antes de esperar y otra tras la notificación. La primera usa
5 SELECT; la que encuentra el trabajo usa 19. Dentro de estos últimos, el SELECT
del evento y las escrituras ocurren después de fijar `started_at`.

El coste SQL acumulado de **toda** la petición de claim final fue 60,54 / 39,20 /
69,64 ms, con 9,20 / 4,58 / 9,87 ms de CPU del hilo dentro del driver. Incluye
ambas comprobaciones y la persistencia posterior a `started_at`; no se puede sumar
todo a la fase posterior al commit. La diferencia entre wall y CPU del hilo
incluye espera del driver/base de datos/transporte y planificación; **no mide CPU
de PostgreSQL**. La instrumentación añade coste y estos valores no son percentiles
de producción.

Las rutas de entrada también reducen SELECT: `/chat/` 101 → 62, `/chat/send/`
127 → 82 y `/api/chat/send/` 125 → 80 en estas muestras. `jobs.accepted` todavía
protege y construye la respuesta dentro de la transacción de admisión; sus spans
finales son 41,23 / 23,15 / 20,71 ms. Moverlo tras el commit requeriría otra prueba
de atomicidad y exposición de mensajes; no se ha hecho para alcanzar la meta.

## Bloqueos, notificaciones y HTTP

`capacity.admission_lock` usa una transacción y un advisory lock PostgreSQL global
compartido por los caminos de admisión. `_claim` bloquea las filas de cola vencida
y el replay de claim, y selecciona candidatos con `select_for_update(skip_locked=True)`.
`reap` tiene una transacción anterior separada y también usa `skip_locked=True`.
Estas exclusiones conservan límites atómicos, replay e identidad del intento.

Las dos llamadas al advisory lock de cada petición final acumulan sólo
2,42 / 1,28 / 1,72 ms de wall SQL. Los perfiles no muestran evidencia de que la
contención en este lock domine el residuo de cola libre; tampoco miden su tiempo
de posesión completo ni permiten extrapolar a saturación sostenida.

`queue_wakeup.listen` se registra antes de comprobar la cola durable. `NOTIFY`
se entrega tras commit; esperar no mantiene una transacción ni su lock. Hay un
máximo de cuatro listeners de petición y un fallback acotado si no puede usarse
LISTEN. El worker solicita hasta cinco segundos de espera y conserva el claim_id
si pierde una respuesta de transporte.

La duración HTTP de claim final fue 442,81 / 2122,07 / 1853,68 ms. Esas peticiones
ya estaban esperando antes de encolar el mensaje; incluyen el long poll y **no
son latencia de despacho**. LISTEN/UNLISTEN sumaron 1,48 / 0,43 / 2,20 ms de SQL.
No se ha medido por separado la latencia pura de entrega del NOTIFY o del socket.

El dispatcher reutiliza su cliente HTTP. Su espera `FIRST_COMPLETED` sólo se usa
cuando las plazas de ejecución están ocupadas; no introduce un sleep de 250 ms
con capacidad libre. El banco confirma la ruta de notificación y recheck, pero
no cuantifica todas las decisiones del planificador del sistema operativo.

La evidencia disponible sitúa el coste restante en la admisión transaccional y
la secuencia de comprobaciones actuales del claim, con autorización/SQL y espera
local. No identifica una llamada de proveedor, una nueva conexión HTTP por cada
paso ni una pausa fija del dispatcher como causa demostrada de este residuo.
