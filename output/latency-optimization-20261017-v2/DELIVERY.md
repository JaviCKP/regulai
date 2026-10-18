# Segunda optimización instalada — 18 de octubre de 2026

Aplicada y verificada en la instalación local existente, accesible en
`http://127.0.0.1:8800`. El commit de producto es `28e91e7`. Las imágenes activas
son web `dbd286f248ef3d3966cfc355df750d025bbbe8fdefeff460bce5cdd489975e9d`
y worker `67acfe365d0fef23bb555cf65a881487432dc3e563a62d4de8a4074c382f5b19`.
Son las imágenes de build5 medidas y probadas. La verificación posterior a la
limpieza está en [verify-1.json](verify-1.json): ambos servicios activos, cero
reinicios, fuentes verificadas, configuración privada y montajes conservados,
cero cambios de esquema y cero llamadas de generación durante la activación.

Se verificó primero la instalación anterior: 525/532 SELECT, preparación caliente
p95 1,322 s y cola p95 180 ms en la repetición inicial de 13 mensajes. La nueva
referencia formal usa 20 procesos por variante y las mismas entradas y copia de
datos. [summary.md](summary.md) publica medianas, p95 y tamaños de muestra;
[summary.json](summary.json) conserva identidades y comprobaciones. La preparación
simple caliente p95 baja de 1,411 a 0,992 s, la fría de 2,198 a 1,758 s, la cola
de 213 a 152 ms y la primera llamada caliente de 1,581 a 1,136 s. Los SELECT
simples bajan de 525 a 308 (41,3%). **Las tres metas temporales no se alcanzan.**

Se agrupan lecturas relacionadas, se reutilizan filas recién autorizadas dentro
de su propia operación, se evita materializar historial explícitamente vacío y
se conservan esquemas estáticos de herramientas en una caché de 11 entradas.
[CHANGES-AND-SAFETY.md](CHANGES-AND-SAFETY.md) documenta alcance, clave, límite,
invalidación y revocaciones. No hay caché de permisos entre fronteras, controles
retirados, cambios de contenido/modelos/políticas/máscaras ni persistencia diferida.

## Ensayos auxiliares y pruebas

| Ensayo | Muestra por variante | Antes mediana / p95 | Después mediana / p95 |
| --- | ---: | ---: | ---: |
| Preparación con historial, caliente | 29 | 1,268 / 1,537 s | 1,062 / 1,409 s |
| Cola concurrente con plaza libre | 40 | 0,348 / 0,471 s | 0,230 / 0,315 s |
| Cola concurrente esperando plaza | 10 | 2,630 / 3,130 s | 1,839 / 2,315 s |
| SELECT de catálogo directo | 5 | 12 / 12 | 10 / 10 |

El historial crece hasta 29 pares anteriores; la selección conserva el límite
existente de 20 pares y coincide entre variantes. Concurrencia: 50 trabajos por
variante, 20 grupos por variante; dos llamadas pueden progresar simultáneamente
y el tercer trabajo espera al liberar plaza. Todos los 280 trabajos formales,
60 de historial y 100 de concurrencia terminan con una llamada, una inferencia y
un checkpoint por trabajo. Los concurrentes tienen además un único claim.

La capacidad de proveedor se fija en 2 exclusivamente en esos procesos de ensayo;
la instalada sigue siendo 1 (global y por cuenta: 2). El conjunto de mensajes por
grupo coincide, pero la carrera cambia ligeramente qué entradas/textos consiguen
plaza primero: los percentiles por cohorte son descriptivos, no parejas exactas
por contenido. El intento de 10 lotes por proceso alcanzó el límite existente de
30 mensajes/minuto y se excluyó; las rondas 52/53 usan 5 lotes por proceso sin
cambiar ese control. Véanse [scenario-verification.json](scenario-verification.json)
y [concurrency-rate-limit-51.json](concurrency-rate-limit-51.json).

El catálogo de la ronda 6 identifica imágenes, banco y datos iguales. Sus cinco
muestras incluyen el primer uso: mediana/p95 14,4/83,3 → 17,3/66,7 ms. Esta muestra
pequeña acredita la reducción de consultas; no permite afirmar mejora temporal.

Pruebas finales: **137 PostgreSQL y 28 SDK pasan sin omisiones**; las herramientas
de medición/instalación ejecutan **43 pruebas, 42 pasan y una se omite** por socket
Unix no disponible en Windows. Cubren las tres entradas HTTP, datos sensibles,
YARA, permisos y revocaciones, aislamiento, recuperación de checkpoints, fallos y
reintentos, idempotencia, capacidad, migraciones y contabilidad. Los proveedores
son simulados y las conexiones externas están bloqueadas. Los informes
`tests-5.json`, `sdk-tests-5.json` y `tooling-verification.json` registran resultados.

## Coste restante y límites

El [perfil](PROFILE-ANALYSIS.md) conserva 13 autenticaciones y tres preflight por
mensaje. En la muestra diagnóstica simple caliente, SQL pasa de 352 a 292 ms y
autenticación de 449 a 327 ms inclusivos; estas cifras se solapan y no se suman.
El coste restante se concentra en autorización/protección y SQL del servidor.
El worker reduce CPU de 100 a 27,5 ms. Bootstrap/checkpoint HTTP tarda unos 475 ms,
prácticamente lo mismo que su trabajo de servidor: no indica que el transporte
sea el cuello principal. [QUEUE-ANALYSIS.md](QUEUE-ANALYSIS.md) separa admisión,
despacho y bloqueo; los locks observados no dominan el tiempo.

No se mide CPU interna de PostgreSQL: el tiempo SQL incluye driver, espera y
transporte. Los perfiles instrumentados se excluyen del p95 formal. Frío significa
primer mensaje tras inicializar Django/SDK, sin vaciar cachés de datos/SO ni medir
arranque de VM. Las tres entradas usan Django TestClient; worker/servidor usan HTTP
local real. Se mide hasta la primera solicitud al proveedor simulado, no hasta el
primer token del modelo real. No se extrapola a carga sostenida ni catálogos mayores.

## Conservación y reversión

La copia privada previa al cambio permanece en
`/opt/regulai/updates/latency-20261017-a2/before-switch-1792275187185343595.dump`
(31.006.324 bytes; SHA256
`cc2ec25e358115297dbed7ec4699f2e637918abc16708e3c81b7970a59da9573`).
Se conservan los contenedores anteriores con sufijo
`-before-latency-20261017-a2`. La reversión vuelve a la primera optimización sin
restaurar la base sobre datos nuevos ni sustituir claves; exige ausencia de trabajo
activo. `cleanup-benchmarks-0.json` y `cleanup-benchmarks-1.json` documentan la
retirada de bases y contenedores temporales propios, con cero pendientes. Los
artefactos, copias privadas y contenedores de reversión se conservan.

Desde `C:\Users\javi\Documents\Codex\regulai-privacy`:

```powershell
rtk proxy python ops/agent_chat/latency_local.py verify --series second
rtk proxy python ops/agent_chat/latency_local.py rollback --series second
```

El segundo comando cambia efectivamente los servicios. [REPRODUCE.md](REPRODUCE.md)
incluye los comandos de repetición y restauración del túnel local. No hubo push,
publicación, despliegue remoto ni llamadas de pago.
