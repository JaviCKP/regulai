# Cambios y garantías de la segunda optimización

Estado final: **build5 aplicado y verificado localmente** el 18 de octubre de 2026
(Europe/Madrid). `apply-0.json`, `verify-0.json` y `host-health.json` identifican las
imágenes activas y la conservación de datos, claves y configuración. Las medidas
formales corresponden a `summary.md`/`summary.json`; los pilotos permanecen separados.

## Cambios de producto

| Cambio | Trabajo que evita | Frontera de seguridad conservada |
| --- | --- | --- |
| `_context` carga relaciones juntas y recibe la ejecución recién leída por `authenticate` | Lecturas repetidas de perfil, conexión, modelo, ejecución y cuenta dentro de la misma operación | Cada `authenticate` sigue leyendo el estado actual y validando usuario, cuenta, conversación, permisos, conexión, modelo y política |
| `BoundaryAuthorization` pasa al preflight las filas de su propia autenticación | Reconstruir el mismo contexto dentro de esa validación | Permanecen YARA, política, máscaras, identidad de destino y comprobaciones del contenido exacto; ninguna autorización se comparte entre salidas |
| `privacy.authorize` usa una consulta con `Exists` para la procedencia de conversación | Consultas separadas de perfil y pertenencia | Se conserva el filtro de cuenta, usuario activo y conversación autorizada |
| `history.for_prompt` recibe la ejecución actual; un snapshot con `pairs == []` no materializa historial | Lectura y construcción de mensajes que un snapshot explícitamente vacío no puede utilizar | Se conserva la autorización y vinculación de conversación; los snapshots no vacíos siguen comprobando los pares actuales y su identidad/digest |
| Las herramientas profesionales se filtran antes de construir sus esquemas | Generar esquemas de herramientas que no están concedidas | La lista procede del bootstrap actual; cada ejecución crea sus propias funciones y el servidor autoriza cada operación |
| Caché acotada de clases de argumentos de herramientas | Inferencia Pydantic repetida de la misma definición estática | No contiene autoridad ni contexto de ejecución; los wrappers y closures se crean de nuevo |
| `_begin_execution_with_context` permite reutilizar el contexto inicial en la admisión profesional | Una segunda lectura inmediata después de crear recibo y ejecución todavía sin trabajo | Se conserva `_context` fresco después de preparar historial, entradas, trabajo, skills y referencias, antes de confirmar la cola |

`begin_execution` mantiene su contrato público de dos valores `(execution, token)`.
El helper privado añade un tercer valor exclusivamente para la admisión profesional.
Entre la autorización inicial y la lectura eliminada sólo había escrituras locales
del recibo y la ejecución; no había salida de red. No se ha cambiado la admisión
general de documentos, que incorpora entradas entre sus validaciones.

El bloqueo de admisión no impide revocaciones administrativas: la validación final
sigue siendo necesaria y permanece. También permanecen las validaciones de descarga,
claim, checkpoint, herramientas e inferencia en sus fronteras correspondientes.

No hay migraciones ni cambios de modelos, políticas, máscaras, contenido enviado,
límites funcionales o texto de interfaz. Se conservan las optimizaciones anteriores
de catálogo, preparación protegida, checkpoints y notificación de cola. No se ha
diferido persistencia ni se han reducido los checkpoints para mejorar la medición.

## Estado reutilizado y caché

La única caché nueva entre ejecuciones es `_TOOL_SCHEMAS` en
`regulai/front/agents/professional_worker.py`.

| Propiedad | Contrato |
| --- | --- |
| Alcance | Un proceso worker; sólo clases Pydantic de argumentos de funciones profesionales |
| Clave | Nombre de función, identidad de su objeto de código, firma completa y documentación |
| Valor | `args_schema`; nunca la función, su closure, cliente HTTP, lease, token, grant, mensajes o contenido |
| Límite | 11 entradas LRU; acceso y primera construcción protegidos por un lock |
| Invalidación | Una definición distinta no coincide con la clave; expulsión LRU y reemplazo/recarga del proceso eliminan las entradas |
| Revocaciones | El filtrado por herramientas concedidas ocurre antes del acceso a la caché. Los wrappers se enlazan a la ejecución actual y el servidor vuelve a validar cada operación |

Las clases son estáticas y no se modifican después de guardarlas. Las pruebas
comparan los 11 esquemas JSON exactos, incluidos tipos, valores por defecto y
campos requeridos, también después de un hit. Comprueban inyección de runtime,
dos clientes y ejecuciones sucesivas independientes, ocho primeras construcciones
concurrentes, invalidación por firma y límite LRU. Referencias débiles verifican
que no quedan retenidos la función ni su marcador de contexto de ejecución.

Los contextos de autenticación y admisión reutilizados son variables locales a una
operación. No tienen TTL ni caché entre peticiones; su vigencia termina en esa
operación y cada nueva frontera vuelve a autorizar. Las cachés previas de contenido
protegido y catálogo mantienen sus controles y no se amplían con este cambio.

La medición SDK aislada con las 12 herramientas efectivamente concedidas al perfil
instalado dio, en 30 observaciones calientes por variante, mediana 50,2 → 20,8 ms y
p95 54,5 → 25,2 ms. El primer uso fue 59,5 → 64,2 ms: no se atribuye mejora fría a
esta caché. Son datos sintéticos de Windows, no latencia del modelo ni evidencia
suficiente por sí solos de la mejora completa en Linux. Véanse
`worker-sdk-installed-no-cache.json`, `worker-sdk-installed-cache.json`,
`worker-sdk-cache-all.json`, `worker-schema-comparison.json` y
`WORKER-INVESTIGATION.md`.

## Pruebas ejecutadas sobre build5

`tests-5.json`: **137 pruebas PostgreSQL, 0 fallos, 0 errores y 0 omitidas**.
`sdk-tests-5.json`: **28 pruebas SDK, 0 fallos, 0 errores y 0 omitidas**.
Ambos informes identifican las imágenes inmutables probadas:

```text
web:    sha256:dbd286f248ef3d3966cfc355df750d025bbbe8fdefeff460bce5cdd489975e9d
worker: sha256:67acfe365d0fef23bb555cf65a881487432dc3e563a62d4de8a4074c382f5b19
```

La selección exacta de `latency_remote.py:tests` para la segunda serie fue:

```text
front.test_agent_context_performance
front.test_agent_admission_context
front.test_agent_capacity
front.test_agent_message_batch
front.test_privacy_batch
front.test_privacy_batch_revocation
front.test_agent_queue_wakeup
front.test_agent_skills_runtime
front.test_privacy_service
front.test_privacy_policy
front.test_privacy_boundaries
front.test_privacy_http
front.test_privacy_agent
front.test_privacy_vertical
front.test_privacy_migrations
front.test_agent_inference.AgentInferenceTests
front.test_agent_professional.ProfessionalTests.test_three_entries_real_account_free_text_and_http_idempotency
```

La selección exacta de `latency_remote.py:sdk_checks` fue:

```text
test_p0_runtime
test_p1_skills_runtime
test_queue_dispatch
test_professional_tool_preparation
```

Estas selecciones cubren, entre otros comportamientos:

- Las tres entradas HTTP, el texto libre, datos sensibles y la idempotencia HTTP.
- YARA antes de reemplazar alias y en cada superficie; cambios de usuario, cuenta,
  permisos, conexión, modelo, política y máscaras; denegación entre pasos y durante
  una llamada. El historial protegido reutilizado sigue comprobando contenido nuevo
  o cambiado y cambios de autorización.
- Recuperación desde checkpoints protegidos, identidad de revisiones de skills,
  restauración de compacción, contenido canónico único, reanudación sin preparar
  otra vez el workspace y reconciliación de ejecuciones terminadas sin otro modelo.
- Replay de inferencia con un solo cargo; incertidumbre del proveedor sin reenvío
  automático ni coste cero inventado; reconciliación de capacidad sin modificar
  resultado ni dinero. Pruebas representativas:
  `test_native_roundtrip_replay_and_single_charge`,
  `test_provider_uncertainty_never_resends_or_invents_zero_cost` y
  `test_uncertain_provider_requires_operator_evidence_without_changing_result_or_money`.
- Identidad de claim conservada tras pérdida de respuesta de transporte, replay
  idéntico, una sola asignación concurrente, notificación sólo tras commit y silencio
  tras rollback. La nueva prueba de cola saturada comprueba liberación confirmada,
  despertar y ausencia de claim duplicado.
- Límites atómicos de capacidad global, por cuenta y proveedor, aislamiento entre
  cuentas y alias equivalentes de conexión; un chat puede progresar mientras otro
  permanece retenido. Migraciones aditivas existentes preservan ciphertext y
  valores por defecto al avanzar y revertir.

Las cinco pruebas nuevas de admisión verifican el contrato público, una autorización
inicial más la final y revocaciones de grant/conexión/política introducidas entre
ambas. Cada revocación provoca 403, rollback sin nuevas filas de prompt/entrada/
ejecución, cero trabajos en cola y cero llamadas al proveedor. Es una intercalación
determinista dentro de la prueba, no un ensayo de dos sesiones administrativas
independientes. La suite de contexto incluye además una prueba negativa que detecta
la materialización innecesaria del historial vacío; `context-verification.json`
documenta esa comprobación local previa, sin sumarla como pruebas únicas a las 137.

Las pruebas de aplicación usan una base PostgreSQL de prueba separada y bloquean
sockets externos, permitiendo sólo loopback para la infraestructura local. Las SDK
usan un contenedor sin red y bloquean `socket.connect`/`connect_ex`. Los proveedores
son simulados. `test_p1_skill_materialization.py` se incluye en la imagen, pero no
está seleccionado por `sdk-tests-5`; tampoco se selecciona la clase
`AgentSDKHTTPTests` del archivo de inferencia. No se atribuye su cobertura a estos
resultados. Las pruebas del instalador tienen su propio registro y no forman parte
de los totales 137/28.

## Capacidad y transporte

La configuración instalada mantiene capacidad de proveedor **1** y capacidad
activa global/por cuenta **2**. El ensayo dedicado de concurrencia usa capacidad de
proveedor **2 sólo en su fixture de proceso**, igual antes y después; no cambia la
configuración viva. Esto permite comprobar dos salidas simultáneas y, por separado,
tres trabajos compartiendo dos plazas. No se mezcla la espera deliberada por
saturación con la meta de cola cuando hay capacidad libre.

`bench-after-6-concurrency.json` es un piloto intermedio y no acredita el candidato
final. Las rondas 52 y 53 completaron 50 trabajos por variante, cada uno con un claim,
checkpoint, inferencia y llamada. `scenario-verification.json` registra esas cohortes
auxiliares. La carrera de admisión cambia ligeramente qué entradas y textos sensibles
obtienen plaza primero: sus percentiles libres/saturados son descriptivos, no parejas
exactas por contenido. El conjunto de entradas y mensajes sí coincide por grupo.

El dispatcher ya reutilizaba su cliente HTTP de claims; cada ejecución conserva su
propio cliente para bootstrap/checkpoint/inferencia/finalización. No se comparten
tokens entre ejecuciones ni se ha sustituido el transporte. La cola conserva su
definición desde la creación de la ejecución; se informa por separado la parte
anterior al commit y el despacho posterior, sin ocultar el coste de admisión.

## Límites de evidencia

Los proveedores simulados permiten comparar preparación, SQL y primera salida, no
el tiempo de inferencia de un modelo real. El primer mensaje de proceso no equivale
a arrancar una VM o vaciar la caché del sistema operativo/PostgreSQL. Los perfiles
instrumentados y pilotos se excluyen de los percentiles formales; el tiempo SQL
incluye driver y espera de base/transporte, no mide por sí solo CPU de PostgreSQL.

Las pruebas de recuperación, carreras y dinero cubren los casos enumerados y no
constituyen una prueba de todos los fallos posibles. No se han introducido llamadas
pagadas para validar proveedores reales. Los artefactos contienen medidas e
identidades de imagen, no valores de claves privadas.

## Verificación y reversión local

Desde `C:\Users\javi\Documents\Codex\regulai-privacy`, verificar la instalación
sin invocar el proveedor:

```powershell
rtk proxy python ops/agent_chat/latency_local.py verify --series second
```

Para repetir las suites aisladas, fuera de una medición de latencia en curso, usar
un número de ronda nuevo para conservar los artefactos anteriores:

```powershell
rtk proxy python ops/agent_chat/latency_local.py tests --series second --round 101
rtk proxy python ops/agent_chat/latency_local.py sdk-tests --series second --round 101
```

La reversión preparada vuelve a las imágenes conservadas de la primera optimización:

```powershell
rtk proxy python ops/agent_chat/latency_local.py rollback --series second
```

El instalador comprueba identidades, ausencia de trabajo activo o incierto,
configuración privada compatible, montajes y checkpoints antes de sustituir
servicios. Conserva los contenedores originales por identidad y prepara respaldo
con servicios detenidos; ante fallo parcial recupera los nombres originales.
La reversión no restaura automáticamente la base de datos, para no sobrescribir
datos nuevos, y conserva las claves. El stage privado de esta serie es
`/opt/regulai/updates/latency-20261017-a2`. No ejecutar `rollback` como comprobación
inofensiva: cambia los servicios locales. No hay push, publicación ni despliegue
fuera de la instalación local autorizada.
