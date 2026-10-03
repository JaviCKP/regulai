# Evaluación adversarial offline

**No mide calidad semántica, clasificación de un LLM ni resistencia real a prompt injection.**

Detector local: 5/5 casos cumplen todas las anotaciones exactas.
Controles HTTP con transportes simulados: 30/30 ejecuciones cumplen los controles congelados.
Casos con valores sensibles conservados localmente: ninguno.
Casos con contenido a preservar perdido localmente: ninguno.
Intentos de sockets/DNS: 0. Coste externo real: 0 USD.

Cada entrada JSON conserva input, resultado transformado, expected/observed, decisiones, costes de fixture, cobertura y citas.
`http-results.jsonl` contiene los cuerpos UTF-8 y base64 recibidos por HTTPAdapter/httpx y el registro persistido antes de cada llamada.
Las etiquetas del corpus expresan expectativas del autor. El clasificador y el juez devuelven fixtures estáticos, identificados por fila.
Una omisión o falso positivo del detector no se oculta porque los controles del pipeline funcionen.

Archivos: `plan.json`, `source-manifest.json`, `corpus-hashes.json`, `local-results.json`, `http-results.jsonl`, `summary.json`, `execution.json`.

## Ejemplos observados

### HARNESS-PLAIN

Entrada sintética:
```text
Calcula 2 + 2. Correo test.person@example.invalid.
```
Salida real del detector local:
```text
{"prompt": "Calcula 2 + 2. [[REGULAI_PERSON]]."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### HARNESS-CSV

Entrada sintética:
```text
Resume la tabla.
```
Salida real del detector local:
```text
{"prompt": "[[REGULAI_PERSON]] la tabla.", "document": "item,price,contact\nservice,25.00,[[REGULAI_EMAIL]]\n"}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### HARNESS-CONSENT

Entrada sintética:
```text
Lee ADVERSARIAL_CONSENT. Correo test.person@example.invalid.
```
Salida real del detector local:
```text
{"prompt": "[[REGULAI_PERSON]]. [[REGULAI_PERSON]]."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### HARNESS-RESTRICTED

Entrada sintética:
```text
Contenido sintético restringido.
```
Salida real del detector local:
```text
{"prompt": "Contenido sintético restringido."}
```
Estado HTTP/servicio: 403 / {'status': 'blocked', 'error_type': 'restricted_content', 'generation_calls': 0}.
Transportes simulados: .

### HARNESS-REVOKED

Entrada sintética:
```text
Calcula 2 + 2.
```
Salida real del detector local:
```text
{"prompt": "Calcula 2 + 2."}
```
Estado HTTP/servicio: 503 / {'status': 'validation_error', 'error_type': 'authorization_changed', 'generation_calls': 0}.
Transportes simulados: classification.

## Límites

- All prompts, documents, credentials, users and responses are synthetic.
- Classifier and semantic judge outputs are injected static fixtures; classifications are not measured.
- Neutral/adversarial responses are transport fixtures, not answers produced by a live model.
- Exact-string annotations do not establish entity-level recall, anonymity or complete PII detection.
- HTTP uses Django Client in-process, with real adapters/services and SDK/requests serialization.
- Prepared requests are captured before offline transports; no external sockets or DNS are allowed.
- Reported application costs use synthetic usage; actual external cost is zero.
- Only synthetic in-memory SQLite is used; private settings and persistent budget ledgers are not loaded.
