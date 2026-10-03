# Evidencias conservadas de revisiones independientes

Captura documental del 3 de octubre de 2026: **65 archivos de evidencia y seis informes antes de actualizar sus enlaces**, copiados byte a byte. [Inventario completo](manifest.json): origen, destino, tamaño, SHA-256 de origen y copia y refs fijas para cada archivo. Los 71 pares coinciden. No se ejecutó producto, proveedor, Docker ni nuevas pruebas funcionales durante este empaquetado; las cifras siguientes pertenecen a las ejecuciones originales identificadas.

| Revisión | Fuente fija | Dictamen conservado | Evidencia |
| --- | --- | --- | --- |
| [Standards inicial](../../../docs/plan-blackhat/revisiones-piloto/standards-c1e3a36.md) | `c1e3a360e7ba3051bb8f0bda487b005dd29834a0` | S1: revalidación de motor/modelo/credencial incompleta después de reservar | [Inventario](standards/review-manifest.json), [probe](standards/probe_tests.py), [salida](standards/probe-output.txt) |
| [Standards cierre](../../../docs/plan-blackhat/revisiones-piloto/standards-a3bc67b.md) | `a3bc67b25b341cb28172bebd5001ef48c5b8d34f` | S1 cerrado; conserva rojo previo y 60 tests del seguimiento | [Fuentes y hashes](standards/followup-a3bc67b/source-manifest.json), [rojo](standards/followup-a3bc67b/red-baseline.txt), [verde](standards/followup-a3bc67b/green-followup.txt) |
| [Spec inicial](../../../docs/plan-blackhat/revisiones-piloto/spec-c1e3a36.md) | `c1e3a360e7ba3051bb8f0bda487b005dd29834a0` | S2: temperatura distinta del manifiesto; S3: guía de máscara opcional | [Comandos y hashes](spec/evidence.json), [captura HTTP](spec/temperature-observed.json), [fuente](spec/snapshot.json) |
| [Spec cierre](../../../docs/plan-blackhat/revisiones-piloto/spec-8731129.md) | `87311294631d9ffdf6b76ccf3fcb9140018a0977` | S2/S3 cerrados; tres pruebas focales | [Comandos y hashes](spec/followup-8731129/evidence.json), [deriva rechazada](spec/followup-8731129/option-drift.json), [fuente](spec/followup-8731129/snapshot.json) |
| [Security inicial](../../../docs/plan-blackhat/revisiones-piloto/security-febc8aa.md) | `febc8aa9b303070e82e3f27626371d5b67cb73f7` | SEC-1: aprobación revocada durante reserva permite una llamada | [Cobertura](security/coverage.md), [PoC](security/review_cases.py), [rojo](security/approval-race.log), [fuente](security/snapshot-manifest.json) |
| [Security cierre](../../../docs/plan-blackhat/revisiones-piloto/security-700389c.md) | `700389c216592db1e0c8725749bb4fd02cf3fa10` | SEC-1 cerrado; 26 métodos entre PoC, pruebas adicionales y regresiones | [Informe original](security/followup-700389c/review.md), [integridad](security/followup-700389c/integrity.json), [fuente](security/followup-700389c/snapshot-manifest.json) |

La base de las revisiones iniciales es `6c78cd396eb72713e85b72d8592970e4b6b66585`. El nombre S1 de los adjuntos Security identifica **SEC-1**, independiente de S1 Standards. El probe Standards inicial afirma el defecto observado: su salida `OK` demuestra reproducción, no corrección. Los cierres posteriores mantienen visibles esos resultados iniciales.

## Preservación y auditoría

Los directorios originales `.claude/review-standards`, `.claude/review-spec` y `.claude/review-security` permanecen intactos. Solo se copiaron los archivos de nivel superior de Security y de su seguimiento cerrado `followup-700389c`; no se incluyeron otros trabajos en curso. Se excluyeron árboles `snapshot`/`candidate`, cachés y bytecode. Sus manifiestos y refs permiten recuperar el código sin duplicar checkouts. Las [seis copias originales de informes](reports-at-capture/) permiten comprobar las revisiones de enlaces; sus hallazgos, dictámenes, comandos y resultados no se cambiaron.

Los scripts, logs y JSON conservan exactamente sus bytes, incluidos CRLF, UTF-16 cuando existe y rutas originales. Las rutas dentro de metadatos registran el lugar de la ejecución histórica; el campo `destination` de [manifest.json](manifest.json) identifica la copia versionable. Los hashes de informes incluidos en metadatos previos corresponden a sus versiones originales, conservadas en `reports-at-capture`. La regla existente `evals/reports/pilot-*/** -text -whitespace` evita normalizar estos bytes en Git.

Auditoría de lectura, sin cargar Django:

```powershell
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/verify_archive.py
rtk proxy .venv/Scripts/python.exe evals/reports/pilot-independent-reviews-20261003-01/verify_archive.py --compare-originals
```

La primera orden comprueba las 71 copias desde cualquier checkout que contenga el paquete. La segunda comprueba además los 65 originales de evidencia si todavía existen en `.claude`. Los informes ya enlazados se auditan por separado en [packaging-verification.json](packaging-verification.json). [preserve_evidence.py](preserve_evidence.py) y [append_security_followup.py](append_security_followup.py) registran cómo se creó esta captura; rechazan sustituir una captura existente.

## Reconstrucción en otro checkout

Usar un checkout local separado que contenga las refs completas de la tabla y un entorno Python con las dependencias fijadas por la revisión. Restaurar **solo los scripts `.py`** de cada grupo en sus ubicaciones relativas originales `.claude/review-standards`, `.claude/review-spec` y `.claude/review-security`, manteniendo los subdirectorios de seguimiento. Elegir directorios nuevos: varios runners escriben logs junto al script; no ejecutarlos directamente dentro de este archivo de evidencias ni sobre las carpetas históricas.

Spec conserva [su preparador inicial](spec/prepare_snapshot.py) y [el de 8731129](spec/followup-8731129/prepare_snapshot.py), que extraen el SHA fijo a `candidate/`. Security conserva [prepare_snapshot.py](security/prepare_snapshot.py) y [prepare.py del cierre](security/followup-700389c/prepare.py), que extraen a `snapshot/`; reconstruir también la fuente inicial cuando el audit del cierre la requiera. Estos preparadores excluyen la configuración local y bases del usuario. Sus refs están fijadas en el propio script.

Standards no tenía un preparador autónomo guardado. Reconstruir desde Git `regulai/`, `evals/` y `requirements.txt` del candidato inicial en `.claude/review-standards/snapshot/`, y del corrector en `.claude/review-standards/followup-a3bc67b/snapshot/`; excluir configuración local, bases, medios y cachés. Se puede extraer cada archivo con `rtk proxy git show <SHA>:<ruta>` o exportar las rutas permitidas mediante `rtk proxy git archive`. El runner del seguimiento selecciona el snapshot inicial con `--baseline`. El [manifiesto](standards/followup-a3bc67b/source-manifest.json) registra la diferencia CRLF/LF observada y los hashes de blobs y fuentes probadas; no confundir equivalencia de finales de línea con igualdad de bytes.

Después ejecutar los comandos de los informes correspondientes sobre esas copias nuevas. No se repitió esta reconstrucción ni las suites durante el empaquetado. Los preparadores y runners conservados son los originales; sus límites de SQLite en memoria, transporte simulado y sockets bloqueados forman parte de la evidencia.

## Alcance

Estos dictámenes corresponden únicamente a los commits indicados. **No verifican el nuevo detector local solicitado**, no cierran su fase de privacidad ni sustituyen su futura revisión. Tampoco autorizan llamadas pagadas, participantes, despliegue o publicación. Office real, calidad semántica y del enmascarador vivo, PostgreSQL/HTTPS/backup no repetidos por estos revisores y aceptación final conservan los límites de cada informe.
