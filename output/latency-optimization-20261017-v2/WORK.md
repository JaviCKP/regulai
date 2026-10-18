ESTADO FINAL: segunda optimización aplicada y verificada el 18-10-2026. Producto 28e91e7, build5. Formal completo 140/v; tres metas temporales no alcanzadas. PG137 y SDK28 pasan; tooling42 pasan/1 omitida. Limpieza completa sin pendientes, verify-1 confirma servicios y configuración. Túnel local 8800 activo intencionalmente. DELIVERY.md y REPRODUCE.md son las referencias vigentes. El registro cronológico siguiente conserva estados intermedios ya superados.

# Segunda optimización de latencia — trabajo activo

Objetivo: reducir preparación previa al proveedor; metas de investigación caliente p95 <700 ms, frío proceso <1,5 s y cola libre <100 ms. Preservar privacidad/YARA, revocaciones por salida, dinero, idempotencia y checkpoints. Sin red pagada ni despliegue remoto.

Estado inicial: HEAD a9e58ed, rama codex/proteccion-reversible; sólo archivos no rastreados previos (no tocarlos). Leídos AGENTS/RTK, tarea92, summary.md/json, docs agentes y glosario. Skills performance-investigation, root-cause-debugging, workmanship, codebase-orientation, context-checkpoint y data-loss-guard.

Verificado `latency_local.py verify --round 100`: imágenes web 9aa14268c576, worker fbdd3ceacfae; claves/config/montajes intactos, servicios activos sin reinicios, HTTP200. `bench-after --count 13 --round 13` sin modificar producción: SELECT525/532, primer proceso1.705881s, warm p95 1.321756s, cola p95 .179944s (n13, nearest rank). Artefactos anteriores preservados.

Plan:
1. Nueva serie aislada latency-20261017-a2, baseline imágenes actualmente instaladas, backup privado y hashes reproducibles.
2. Perfil nuevo por operación CPU/SQL/espera, sin incluir instrumentación pesada en muestra formal.
3. Mejoras mínimas medidas tras cada etapa. Nada de caché de autorización entre fronteras.
4. Comparación formal misma copia/entradas, >=20 primeros procesos y >=60 simples calientes por variante; historia, 3 HTTP, sensible, capacidad y fallos en cohortes separadas.
5. Suite invariantes y revisión independiente; aplicar imágenes probadas localmente con rollback conservando datos/claves, limpiar sólo recursos propios.
6. Actualizar tarea92, summary.json/md y comandos de verificar/revertir.

Delegación: context_profile owns service.py/governance.py/history.py/access.py/capabilities.py/views.py y test_agent_context*. worker_transport inspecciona SDK/queue y owns tests propios; cambios jobs/worker/adapter coordinados. benchmark_review owns latency_benchmark_server.py/worker.py y latency_profile.py. Root owns latency_local.py/latency_remote.py, ejecución serial de bancos y aplicación.

## Estado 21:40 UTC aprox.

Instalador extendido con `--series second` (default first conservado): identidad latency-20261017-a2, stage privado /opt/regulai/updates/latency-20261017-a2; rollback vuelve a a1 actual. Init guardó backup nuevo de31MB SHA256 f59da15091cfa540bb02dbac8bc44e847fb5044e1f8720edbeafab5605a24efc. Producción aún NO cambiada.

Cambios producto actuales congelados y revisados por benchmark_review/context_profile sin hallazgos:
- service._context JOINs, execution fresh pasada a history, resolve grant/account helper, grant_binding intacto. governance preflight BoundaryAuthorization fresco SOLO de su authenticate, ninguna auth retirada.
- access._conversations_for_company helper comparte filtro exacto con cuenta fresca. privacy.authorize single SQL Profile+Exists scope actual, sin cache.
- professional_worker filtra tools antes schema; cache bounded11 args_schema por nombre/code/signature/doc, ninguna closure/client/authority retenida. 7 tests especificos+12 runtime Windows y equivalencia11 schemas, micro instalado50→21ms mediana (n30).
- No cambios a UI/modelos/políticas/límites instalación, no migraciones.

Etapas medidas: build0 queries525→435; paired1 n13 cambió hash server entre variantes (excluir formal), paired2 n7 hash fijo pero primeras baseline se solapan final suite (piloto sólo). build2 añade resolución perfil y privacy2queries: after5 n13 SELECT378/385, warm mediana~1.02, outlier1.98. Build3 añade privacy Exists +cache SDK (espera360/367). Build4 sólo incluye archivo test_p0_runtime faltante en imagen SDK, mismo producto que build3.

Imágenes FINALES candidato build4: web f722ca60687b865561281a24527fdaf4f2edf5a1cf03341e0eb913b7df07476d, worker f6566fdb461eb9d002bb146445fcd0d386c6c8e3828aca805df6ccfe7af03a57. Tags regulai-v2-{web,worker}:latency-20261017-a2. No reconstruir durante formal.

Pruebas: build0 suite114:108existingOK,6testnuevo error fixture CSV (corregido). Build2 suite1160fallos. Build3 suite1290fallos0skips incl capacity. Build4 sdk-tests28OK Linux --network none. Build4 tests129 en curso exec session58679, con bloqueo socket externo añadido. tests installer+profile+report34,33OK y1skip Unix socket Windows. Nuevos9tests context pasan SQLite (.venv app plataforma).

Harness server/worker/profile CONGELADOS hashes en artefactos. Cada ronda DB copia,3HTTP entradas Django Client (sin transporte socket público), SDK/internalHTTP real, MockTransport + external sockets denied. BENCH_PROFILE=1 diagnóstico excluido formal. Nuevas queue_admission_s (created→commit) y queue_dispatch_s (commit→claim), history scenario creciente y datosreused, worker perfiles CPU/HTTP.

Concurrencia: pilotoafter4 falló porque instalada provider capacity1 (no race). Script dedicado actual configura SOLO proceso fixture provider2 (activeglobal/company2), preserva configuración viva; after6 piloto5jobsOK:2free concurrentes +3saturados,terceroespera, todos1claim/checkpoint/inference/provider. No modificar capacidad live.

Siguiente secuencia concreta:
1. Poll session58679 tests4; si OK correr after7 n13 (stage3) o formal primera pareja para medir360/367. No más tests pesados simultáneos con latencia.
2. Recoger perfil final after9 --profile --count3 (y baseline9 mismo harness para CPU diagnóstico) y avisar context_profile para actualizar PROFILE-ANALYSIS.md.
3. Piloto history after8 n11, si funciona formal history baseline/after round50 n30, historias0..29; concurrency baseline/after round51 count10 =>50jobs/v. Ajustar si límite/bug banco; nunca producción por fixture.
4. Formal n140/v: `rtk proxy python ops/agent_chat/latency_sweep.py --start 20 --rounds 20 --count 7` (AB alterno por ronda). ~20firstprocess+60simplewarm+60sensitivewarm/v. Raw timestamps añadidos remote para verificar orden. Script reporte `latency_report_v2.py` requiere20..39 exactamente7 e imágenes/hashes/inputs/mismosdump, excluye pilotos; aún no ejecutar como final hasta datos completos.
5. Generar summary y analizar metas reales, actualizar tarea92 y docs/cache/límites. Si ninguna mejora p95 demostrada revisar antes conservar.
6. Verificar/revisar final source/diff, installer tests después últimaedición, candidate tests status matchingbuild4. `latency_local.py apply --series second` autorizado (localonly), después verify, conserva datos/claves/montajes/CP, originalsretained porID. Guardar backup+rollback.
7. cleanup-benchmarks --series second sólo recursos strictowned (0..199names predef,matchingimages/mounts/command), conserva artefactos. También limpiar nuevo a1bench-after13 usando original cleanup antes applysecond o manual estricto porque a1verify fallará tras segundoapply. No tocar untracked previos.
8. Pequeños commits autorizados sólo nuestros archivos y evidence (no push). Final español tabla breve antes/después+n, mejoras/pruebas/límites, comandos verificar/revertir --series second.

Agentes: benchmark_review escribe reporte y revisión ya sinhallazgos; context_profile haciendo PROFILE-ANALYSIS.md pendiente after9final. worker_transport terminado. Venv app C:/Users/javi/Documents/Codex/regulai-platform/.venv/Scripts/python.exe; venv SDK ops/agent_probe/.venv/Scripts/python.exe allí. Todos comandos rtk.


## Estado build5 congelado
Web sha256:dbd286f248ef3d3966cfc355df750d025bbbe8fdefeff460bce5cdd489975e9d; worker sha256:67acfe365d0fef23bb555cf65a881487432dc3e563a62d4de8a4074c382f5b19. History [] shortcut y helper admission terminados/revisados sin hallazgos. SDK28/28, tooling36/37 con1skipUnix; testsPG5 en curso. baseline9perfil y baseline50history30 completos. Próximo after9perfil, after10piloto13, formal20..39 paired20x7. No rebuild duranteformal.

PG137/137 (tests5) ySDK28/28 finalOK. after9perfil confirma308/315SELECT; baseline9sameharness. Perfilafter9frio1.336,simpleswarm.977s; no aceptaciónp95. Pilotoafter10n13 enejecución session4671.

Formal paired20..39x7 ejecutándose session4877, no otros bancos/tests pesados. SDK/PGfinalpass, reviewproducto final3agentes sin hallazgos. CHANGES-AND-SAFETY yREPRODUCE redactados, pendiente actualizar aplicación. Sourcehash build5 frozen.

Formal avanzado hasta35pareado y36baseline. Session4877 continúa; NO iniciar otro banco hasta exit0. Restan afterhistory50n30, concurrencypaired51count10, catalogafter5reps; report --build5, aplicar/verify/cleanup. Fecha local cruzó18oct, identidadartefactos17octsepreserva. Ningúnarchivo producto difiere31sourcehashbuild5.

FORMAL COMPLETE20..39 140/v issues[] (--build5). warm simplemedian1.116/.816p951.411/.992; coldp952.198/1.758; queuep95.213/.152; firstinferwarmp951.581/1.136. Metas3false. afterhistory50session7598; next pairedconcurrency51n10 then catalogafter round5; refreshreport. apply/verify/cleanupstillpending; sourcefrozen.

Aux complete: history50 n30/v chosen0..20same; concurrency52/53 n25each =>50/v,40free10blocked,all1claim/cp/provider/infer. After51failed429after30posts; AuditLog2rate_limit_exceeded, excluded. catalogafter5SELECT10 vsbaseline12. Tooling37=36pass1Unixskip rerunOK. Productcommit28e91e7. APPLYsecond session11394 running, next poll thenverify/cleanup.
