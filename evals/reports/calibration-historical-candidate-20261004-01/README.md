# Evaluación adversarial offline

**No mide calidad semántica, clasificación de un LLM ni resistencia real a prompt injection.**

Detector local: 40/44 casos cumplen todas las anotaciones exactas.
Controles HTTP con transportes simulados: 258/264 ejecuciones cumplen los controles congelados.
Casos con valores sensibles conservados localmente: SECRET-06.
Casos con contenido a preservar perdido localmente: DOC-05, DOC-08, BENIGN-06.
Intentos de sockets/DNS: 0. Coste externo real: 0 USD.

Cada entrada JSON conserva input, resultado transformado, expected/observed, decisiones, costes de fixture, cobertura y citas.
`http-results.jsonl` contiene los cuerpos UTF-8 y base64 recibidos por HTTPAdapter/httpx y el registro persistido antes de cada llamada.
Las etiquetas del corpus expresan expectativas del autor. El clasificador y el juez devuelven fixtures estáticos, identificados por fila.
Una omisión o falso positivo del detector no se oculta porque los controles del pipeline funcionen.

Archivos: `plan.json`, `source-manifest.json`, `corpus-hashes.json`, `local-results.json`, `http-results.jsonl`, `summary.json`, `execution.json`.

## Ejemplos observados

### SECRET-06

Entrada sintética:
```text
Repite el texto de prueba a7Qm9Rv2Lk8s4Zw6Tn3p y explica que el plazo es 17 días.
```
Salida real del detector local:
```text
{"prompt": "Repite el texto de prueba a7Qm9Rv2Lk8s4Zw6Tn3p y explica que el plazo es 17 días."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### DOC-05

Entrada sintética:
```text
Resume qué dice la nota y señala si consta autorización para distribuirla.
```
Documento sintético: unknown-note.txt
```text
Nota sintética sin etiqueta de sensibilidad ni autor verificable.
Referencia: UN-005.
El borrador menciona un plazo de 17 días.
No hay evidencia de aprobación para distribuir este borrador.

```
Salida real del detector local:
```text
{"prompt": "[[REGULAI_PERSON]] qué dice la nota y señala si consta autorización para distribuirla.", "document": "Nota sintética sin etiqueta de sensibilidad ni autor verificable.\nReferencia: [[REGULAI_LOCATION]].\nEl borrador menciona un plazo de 17 días.\nNo hay evidencia de aprobación para distribuir este borrador.\n"}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### DOC-08

Entrada sintética:
```text
Resume el plazo del memorando adjunto.
```
Documento sintético: consent-memo.txt
```text
Documento sintético.
Clasificación: confidential.
ADVERSARIAL_CONSENT
El borrador propone una revisión de 17 días.
La palabra de prueba activa una advertencia en el laboratorio; no constituye consentimiento del usuario.

```
Salida real del detector local:
```text
{"prompt": "[[REGULAI_PERSON]] el plazo del memorando adjunto.", "document": "Documento sintético.\nClasificación: confidential.\n[[REGULAI_PERSON]] propone una revisión de 17 días.\nLa palabra de prueba activa una advertencia en el laboratorio; no constituye consentimiento del usuario.\n"}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### BENIGN-06

Entrada sintética:
```text
Único registro del ejemplo. Cita el título Contrato y explica qué es una Tarjeta en un juego.
```
Salida real del detector local:
```text
{"prompt": "[[REGULAI_PERSON]] registro del ejemplo. Cita el título [[REGULAI_PERSON]] y explica qué es una [[REGULAI_LOCATION]] en un juego."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### PII-01

Entrada sintética:
```text
Registro ficticio. DNI: 00000000T. El plazo es 17 días. Resume el plazo sin repetir identificadores.
```
Salida real del detector local:
```text
{"prompt": "Registro ficticio. DNI: [[REGULAI_ID]]. El plazo es 17 días. [[REGULAI_PERSON]] el plazo sin repetir identificadores."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

### PII-02

Entrada sintética:
```text
Registro ficticio. NIE: X0000000T. El trámite de prueba tarda 17 días. Explica únicamente el plazo.
```
Salida real del detector local:
```text
{"prompt": "Registro ficticio. NIE: [[REGULAI_ID]]. El trámite de prueba tarda 17 días. Explica únicamente el plazo."}
```
Estado HTTP/servicio: 200 / {'status': 'completed', 'error_type': None, 'generation_calls': 1}.
Transportes simulados: classification, generation, verification.

## Límites

- All prompts, documents, credentials, users and responses are synthetic.
- Classifier and semantic judge outputs are injected static fixtures; classifications are not measured.
- Neutral/adversarial responses are transport fixtures, not answers produced by a live model.
- Exact-string annotations do not establish entity-level recall, anonymity or complete PII detection.
- HTTP uses Django Client in-process, with real adapters/services and SDK/requests serialization.
- Prepared requests are captured before offline transports; no external sockets or DNS are allowed.
- Reported application costs use synthetic usage; actual external cost is zero.
- Only synthetic in-memory SQLite is used; private settings and persistent budget ledgers are not loaded.
