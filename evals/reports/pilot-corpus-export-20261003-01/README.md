# Preservación de bytes en export Git

El revisor Spec reprodujo un problema preexistente al detector local: Git con `core.autocrlf=true` exportaba a CRLF `expectations.json`, `generate_corpus.py` y `files/quoted.csv`, aunque sus hashes congelados corresponden a LF. Root lo reprodujo en `4c7695e`: [rojo](red.json), test exit1 y tres hashes distintos.

`4494e85` fija atributos `-text` para el corpus y manifiestos. El primer [ensayo](green.json) ya pasó la prueba documental, pero mostró que el índice aún retenía bytes normalizados de los manifiestos de autorización. El segundo [ensayo](green-02.json) repite ese mismo SHA: el commit de bytes había quedado detenido por la comprobación de whitespace del JSON capturado con CRLF. Se conservan ambos como resultados parciales con exit1, sin llamarlos cierre verde.

`d63731a` registra los bytes originales con `git add --renormalize` y exceptúa de whitespace únicamente el manifiesto de corpus congelado, como los demás artefactos con hashes. No cambió datos, etiquetas ni expectativas. El [export definitivo](green-03.json) termina exit0: un test que recorre los 12 documentos, todos los hashes de archivos/expectativas/generador correctos y hashes de manifiestos idénticos a los referenciados por la autorización pendiente.

`run_check.py` conserva la reproducción. Los ZIP y checkouts de prueba quedan en `.claude/pilot-corpus-export-*`; no se versionan copias completas del repositorio. Los informes registran SHA del ZIP, commit, órdenes, resultado y hashes de logs. Ninguna prueba usa proveedores reales o datos del usuario.
