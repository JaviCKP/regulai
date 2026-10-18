El perfil final confirma que se elimina trabajo repetido antes del proveedor: **525 → 308 SELECT** para el mensaje simple, conservando 13 autenticaciones, tres preflight y la persistencia previa al modelo. El coste residual se concentra en el servidor: validaciones vigentes, protección de contenido y muchas esperas SQL pequeñas. La CPU local del worker baja; el transporte HTTP puro no aparece como coste dominante en la muestra observada.

Se comparan [baseline-9](bench-baseline-9-profile.json) y [after-9](bench-after-9-profile.json), con los mismos hashes de los tres archivos del arnés y del dataset. After-9 coincide exactamente con [build-5](build-5.json): web `dbd286f248ef`, worker `67acfe365d0f`. La tabla de operaciones utiliza la fila `index=2`: mensaje simple caliente por `/api/chat/send/`, conversación nueva, catálogo automático de una entrada y sin historial previo. Es **una observación por variante**, no una mediana ni un p95. Los perfiles están instrumentados y se excluyen de los percentiles de aceptación.

Cada perfil contiene tres filas: primer mensaje de proceso simple, ejecución caliente sensible y ejecución caliente simple. «Frío» significa primer mensaje con módulos importados y Django inicializado; no implica PostgreSQL ni sistema operativo sin caché. Las preparaciones observadas son respectivamente 1862,8 / 1176,4 / 1111,8 ms antes y 1336,2 / 818,5 / 976,6 ms después. Su dispersión impide convertir estas tres observaciones en una afirmación sobre las metas de p95; esas metas se comprueban con las rondas finales sin instrumentación.

Las etapas medidas conservan la siguiente trazabilidad. Los SELECT excluyen admisión, claim y consultas del driver; se cuentan desde claim hasta el primer acceso al proveedor.

| Código medido | Evidencia | Bootstrap | Checkpoint | Inferencia | Total simple | Total sensible |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Instalación anterior | baseline-0/9-profile | 152 | 106 | 267 | 525 | 532 |
| Build-0: JOIN y contexto fresco de cada preflight | after-0/3-profile | 132 | 91 | 212 | 435 | 442 |
| Build-2: resolución de cuenta y compañía dentro de la operación | after-5 | 114 | 79 | 185 | 378 | 385 |
| Build-4: permiso de privacidad en una consulta y esquemas SDK | after-7 | 108 | 76 | 176 | 360 | 367 |
| Build-5: selección vacía de historial y contexto de admisión | after-9-profile | 92 | 64 | 152 | 308 | 315 |

La primera etapa elimina 90 SELECT. La segunda elimina 57: 39 de las 13 reconstrucciones de contexto y 18 de las autorizaciones de privacidad. Build-4 agrupa perfil y permiso de conversación mediante `Exists`, eliminando otras 18 consultas sin ampliar su vigencia. Build-5 evita 52 SELECT al no materializar un historial cuya selección es vacía. El ahorro acumulado para el mensaje simple es **217 SELECT, un 41,3 %**. Reutilizar el contexto inicial de admisión ahorra trabajo anterior al claim, por lo que no se incluye en estos 217. Se conservan en todas estas etapas 20 SAVEPOINT, 20 RELEASE, 14 INSERT y 10 UPDATE para el mensaje simple: no se reduce latencia suprimiendo persistencia. Los archivos build registran hashes de fuentes e identidades inmutables; `changed_by_kind` enumera el paquete frente a la base original y no debe interpretarse como el diff entre etapas.

Las cifras siguientes son **pared / CPU del hilo / diferencia**, en milisegundos. La diferencia recoge espera y desplanificación; no equivale por sí sola a espera de PostgreSQL. Los tiempos son incluyentes: `authenticate` contiene `_context`; `preflight` contiene autenticación; privacidad contiene consultas, serialización y detectores; bootstrap e inferencia contienen varias de esas operaciones. **No se deben sumar las filas.** El coste propio del perfil descuenta únicamente hijos instrumentados.

| Operación de servidor, antes del proveedor | Llamadas antes / después | Baseline-9: pared / CPU / diferencia, ms | After-9: pared / CPU / diferencia, ms |
| --- | ---: | ---: | ---: |
| `authenticate` | 13 / 13 | 449,2 / 288,8 / 160,3 | 327,3 / 200,2 / 127,1 |
| `_context`, incluido en autenticación | 13 / 13 | 377,7 / 259,9 / 117,8 | 250,0 / 166,3 / 83,7 |
| `preflight` | 3 / 3 | 170,9 / 118,1 / 52,8 | 94,5 / 64,0 / 30,5 |
| Política `evaluate_policy` | 16 / 16 | 78,1 / 70,0 / 8,1 | 71,6 / 62,6 / 9,0 |
| YARA `scan_rules`, incluido en política | 16 / 16 | 51,9 / 51,7 / 0,2 | 41,4 / 41,4 / 0,0 |
| Privacidad `authorize` | 18 / 18 | 73,3 / 52,3 / 21,0 | 52,6 / 41,1 / 11,6 |
| Privacidad `prepare_turn` | 18 / 18 | 164,3 / 97,3 / 67,0 | 153,3 / 90,2 / 63,2 |
| Protección agrupada `_protect_many` | 5 / 5 | 119,4 / 86,5 / 32,9 | 177,2 / 139,6 / 37,6 |
| Validación de salida `outbound` | 5 / 5 | 198,3 / 139,3 / 59,0 | 193,8 / 131,2 / 62,7 |
| Persistencia de usos `record_use` | 4 / 4 | 54,4 / 29,3 / 25,0 | 58,5 / 29,8 / 28,7 |
| Máscaras `mask_texts`, con sus controles | 1 / 1 | 124,1 / 80,9 / 43,2 | 99,2 / 62,3 / 36,9 |
| Detector local `detect_spans` | 1622 / 1622 | 70,5 / 70,4 / 0,1 | 72,4 / 72,3 / 0,1 |
| Bootstrap interno `_bootstrap` | 1 / 1 | 95,4 / 64,9 / 30,5 | 142,9 / 111,5 / 31,4 |
| Bootstrap profesional, incluido en anterior | 1 / 1 | 33,9 / 22,8 / 11,1 | 87,5 / 74,1 / 13,5 |
| Guardado de checkpoint | 1 / 1 | 94,0 / 61,9 / 32,1 | 76,5 / 49,4 / 27,1 |
| `infer`, cortado al acceder al proveedor | 1 / 1 | 478,5 / 326,6 / 151,9 | 392,8 / 258,8 / 134,1 |
| `json.dumps`, todas las rutas de preparación | 560 / 560 | 6,8 / 6,8 / 0,0 | 7,0 / 6,9 / 0,1 |
| `json.loads`, todas las rutas de preparación | 1203 / 1033 | 10,1 / 9,9 / 0,2 | 7,1 / 7,0 / 0,1 |

El coste propio de preflight baja de 30,4 a 2,6 ms: deja de reconstruir filas inmediatamente después de autenticarlas. Las 16 comprobaciones de política/YARA, 18 autorizaciones de privacidad y 1622 llamadas al detector permanecen. No se omite el control del texto exacto de cada salida. La mayor CPU del bootstrap y de `_protect_many` en esta observación no se atribuye a serialización: `json.dumps` mantiene 560 llamadas y unos 7 ms. El coste propio de `_protect_many` es 101,0 ms de pared y 77,2 ms de CPU después, frente a 42,3 y 23,9 antes. Haría falta instrumentar sus operaciones no cubiertas y repetir para identificar ese pico; esta muestra no justifica otra caché o una supresión de controles.

El tiempo SQL se mide alrededor del cursor y excluye la construcción posterior de objetos Django. CPU significa CPU del hilo cliente, **no CPU del servidor PostgreSQL**. Pared menos CPU incluye controlador, socket, planificador y ejecución de PostgreSQL; no separa bloqueo, red y CPU del servidor de base de datos.

| Ruta SQL, cualquier verbo | Cantidad antes / después | Baseline: pared / CPU / espera residual, ms | Final: pared / CPU / espera residual, ms |
| --- | ---: | ---: | ---: |
| Bootstrap | 167 / 107 | 105,4 / 26,1 / 79,3 | 98,5 / 21,6 / 77,0 |
| Checkpoint | 125 / 83 | 76,4 / 15,9 / 60,5 | 63,8 / 13,0 / 50,8 |
| Inferencia hasta proveedor | 297 / 182 | 170,6 / 42,8 / 127,9 | 129,4 / 30,1 / 99,3 |
| Total, rutas excluyentes | 589 / 372 | 352,4 / 84,8 / 267,6 | 291,8 / 64,7 / 227,1 |

Los contadores por primer llamador SQL son excluyentes, pero no representan todos los hijos de una operación. En el perfil final destacan `prepare_turn` con 74 sentencias, `_context` con 65, `required` con 24, catálogo `_entries` con 19, `privacy.authorize` con 18 y `effective_revision` con 18. Esas 19 consultas del catálogo suman las fronteras de preparación; no representan una lectura única del catálogo. Los 48 accesos atribuidos directamente a `authorized_history` en baseline pasan a cero para la selección vacía; las consultas de perfil asociadas se contabilizan aparte. No se ha demostrado un cuello de botella de plan de consulta que justifique añadir índices. Los 291,8 ms de SQL residual ya forman parte de las operaciones de servidor anteriores: no deben añadirse otra vez.

La partición siguiente usa intervalos consecutivos, sin sumar el tiempo del servidor a la espera HTTP que ya lo contiene. Corresponde a la misma ejecución simple caliente de cada perfil.

| Tramo de preparación | Antes, ms | Después, ms | Interpretación |
| --- | ---: | ---: | --- |
| Worker esperando bootstrap HTTP | 283,2 | 317,2 | Incluye trabajo de servidor y transporte |
| Worker esperando checkpoint HTTP | 187,3 | 157,3 | Incluye persistencia, respuesta protegida y transporte |
| Worker local antes de emitir inferencia | 96,4 | 25,4 | SDK/Python fuera de las dos esperas anteriores |
| Servidor desde llegada de inferencia hasta proveedor | 527,6 | 434,6 | Controles, privacidad, contabilidad y cliente proveedor |
| Residuo entre los puntos de medida | 17,3 | 42,2 | Despacho, transporte de inferencia, planificación y resolución de relojes |
| Total | 1111,8 | 976,6 | Puede diferir una décima por redondeo |

Las dos esperas HTTP finales suman 474,4 ms y 2,4 ms de CPU del worker. El servidor mide 474,7 ms para esas mismas peticiones. La diferencia submilisegundo y su signo muestran el límite de comparar bordes distintos de esos intervalos; no son una medida aislada de red. La coincidencia de magnitudes indica que optimizar solo la conexión HTTP no resolvería el coste dominante observado. El span `run_job` baja de 100,4 a 27,5 ms de CPU del hilo antes de la inferencia; dentro de ese total, `build_agent` pasa de 11,4 a 8,5 ms y la CPU propia de `run_job` de 84,4 a 16,3 ms. Son componentes incluidos, no tiempos adicionales. La medida separada de CPU del proceso completo es 100,5 → 27,6 ms; se distingue del hilo porque puede incluir otros hilos activos.

El experimento aislado del SDK usa la misma lista instalada de herramientas y el SDK real, con `InternalClient` simulado, sin base de datos ni red. Con 30 ejecuciones calientes por variante, preparar la primera petición de inferencia pasa de mediana **50,16 a 20,78 ms** y p95 **54,45 a 25,15 ms** reutilizando los esquemas estáticos. Las primeras ejecuciones son 59,53 y 64,18 ms, una muestra por variante; no demuestran mejora en frío. Estos tiempos Windows no se suman ni se trasladan directamente al perfil Linux. Evidencias: [sin caché](worker-sdk-installed-no-cache.json), [con caché](worker-sdk-installed-cache.json). La caché mantiene como máximo 11 clases de argumentos, nunca funciones, credenciales, leases ni permisos; la clave incluye nombre, código, firma y documentación. Las pruebas verifican callbacks independientes, liberación de contexto, primer acceso concurrente, límite, cambio de firma y herramientas revocadas.

La cola se descompone en 87,8 ms desde creación hasta commit de admisión y 60,8 ms de commit a asignación antes; después son 60,5 y 68,8 ms. Son subintervalos de la cola, no de la preparación. La mejora de admisión reutiliza el contexto inicial solo durante la preparación local y conserva una validación fresca después de guardar inputs, job, skills y referencias, antes del commit. Las pruebas revocan grant, conexión o política entre ambas comprobaciones y verifican rollback sin filas ni trabajos en cola. Estas dos observaciones de cola no determinan su p95 bajo capacidad libre o saturación; esos escenarios se miden separadamente.

La optimización del historial devuelve `[]` únicamente cuando el snapshot fresco contiene exactamente `pairs == []`; las selecciones no vacías siguen recorriendo y validando todos los pares autorizados. `_context` conserva antes de esa llamada la lectura y validación de usuario, cuenta, grant, conversación y procedencia de compañía. Una selección vacía no autoriza conversaciones; el snapshot sigue formando parte del digest. No se añade caché ni se cambia contenido seleccionado o límites. El ahorro previsto de 13 × 4 SELECT queda confirmado por el cambio **360 → 308**.

La prueba local crea un par válido disponible, comprueba que la selección sigue siendo `[]` sin consultas cuando se suministra ejecución y con una sola consulta cuando hay que leerla. Conserva denegaciones por usuario, cuenta, grant, propietario y procedencia mixta. Seleccionar después un par válido reconstruye ese par e invalida la siguiente autenticación con el digest anterior. Las 12 pruebas locales pasan. El [control negativo reproducible](empty-history-regression-probe.py) elimina solo el retorno anticipado en memoria y la prueba falla con **4 consultas frente a 0**, sin modificar producción. Véase [evidencia](context-verification.json). Las suites finales aportan además [137 pruebas PostgreSQL](tests-5.json) y [28 pruebas SDK](sdk-tests-5.json).

Los primeros perfiles quedan como evidencia de diagnóstico, sin mezclarlos con la comparación final: [baseline-0](bench-baseline-0-profile.json) y [after-0](bench-after-0-profile.json) tienen el mismo arnés y muestran autenticación 412,7 → 383,3 ms, contexto 345,5 → 310,4 ms y preflight 160,5 → 131,6 ms para su fila simple caliente. [After-3](bench-after-3-profile.json) añade instrumentación del worker y ejecuta **build-0**, no build-3; sus tiempos no se comparan como si tuvieran idénticas condiciones. Permitió localizar espera HTTP coincidente con servidor y coste SDK. Los perfiles baseline-9/after-9 anteriores sustituyen esas cifras como diagnóstico de la imagen final.

Las rondas formales 20–39, sin instrumentación, no alcanzan las tres metas: preparación simple caliente p95 **1,411 → 0,992 s** (60 observaciones por variante), preparación fría p95 **2,198 → 1,758 s** (20 por variante) y cola p95 **213 → 152 ms** (140 por variante). Véanse `summary.md` y `summary.json`; los percentiles no proceden de las tres filas diagnósticas de este documento.

El residuo medido combina SQL, reconstrucción de autoridad, protección de contenido y CPU Python. No se elimina recuperación, contabilidad o validación para alcanzar una meta. El siguiente trabajo justificado es perfilar los componentes de CPU dentro de protección y las esperas SQL restantes con más resolución, conservando las comprobaciones en cada frontera. Ninguna cifra de este documento mide latencia de un modelo real: el punto final es la primera petición al proveedor simulado, y las conexiones externas están bloqueadas.
