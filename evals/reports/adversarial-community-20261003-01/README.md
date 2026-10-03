# Construcción del arnés (no es el corpus adversarial de 44 casos)

Las dos ejecuciones preservan cinco casos sintéticos creados únicamente para comprobar el arnés: texto, CSV, consentimiento firmado, restricción hacia destino privado y revocación del permiso antes de generar. Cada caso recorrió tres entradas HTTP y dos perfiles de transporte, por tanto 30 ejecuciones por corrida.

- `run-01`: primera comprobación; 30/30 controles, 5/5 anotaciones del detector local; exit 0; sockets/DNS de proceso principal y parsers: 0.
- `run-02`: añade assertions HTTP, suma/completitud monetaria, cita desconocida rechazada localmente, privacidad por frontera y hashes de fuentes al finalizar; 30/30 controles, 5/5 anotaciones del detector local; exit 0; sockets/DNS: 0; fuentes sin cambios durante la ejecución.

Estos datos no son la evaluación final de los 44 casos y no se agregan a sus métricas. Ninguna de las corridas mide calidad semántica, clasificación por un modelo ni resistencia de un LLM a prompt injection. Los generadores, clasificador y juez son fixtures, rotulados en cada fila. Los cuerpos preparados por el código real se conservaron en `http-results.jsonl`.

Comandos de ejecución (desde la raíz del repositorio):

```powershell
rtk proxy .venv/Scripts/python.exe scripts/run_adversarial_community.py --dataset evals/reports/adversarial-community-20261003-01/preflight-corpus/cases.jsonl --output evals/reports/adversarial-community-20261003-01/run-01
rtk proxy .venv/Scripts/python.exe scripts/run_adversarial_community.py --dataset evals/reports/adversarial-community-20261003-01/preflight-corpus/cases.jsonl --output evals/reports/adversarial-community-20261003-01/run-02
```

Las mejoras posteriores de procedencia conservan además una copia del runner y el diff de runtime en futuras carpetas. Las salidas anteriores siguen intactas y sus manifests mantienen el hash exacto del runner que las produjo.
