# Integración del enmascarado local — 2026-10-03

Agente A. Inicio `700389c216592db1e0c8725749bb4fd02cf3fa10`. Código integrado por el coordinador en `3e4d9d2`; ajuste visual en `da836e3`. Detector y dependencias: coordinador; ledger, evaluación y demo: agente C. Ninguna llamada a proveedores vivos, cambio de secretos, migración de base de usuario, staging ni commit realizado por este agente.

## Resultado

Backend explícito `local`/`http`, conservación de registros HTTP, formulario por empresa con alta local por defecto, URL obligatoria solo para HTTP y bootstrap de política local con cota API cero. El wrapper mantiene el lote y su orden, falla cerrado y delega al detector sin ruta HTTP alternativa. Se incluye el backend en identidad de autorización/consentimiento.

Chat y simulador utilizan cotas por paso: local cero, HTTP cota configurada. La cadena solo local exige cero explícito. Las intenciones se persisten antes del observador con `transport`, y las locales incluyen `cost_scope=api`, `cost=0`, `cost_bound=0`, `cost_kind=configured_zero`. Un fallo local no crea gasto API incierto; un fallo HTTP conserva incertidumbre. La identidad pública sigue siendo `obfuscation:<id>`, modelo nulo.

## Verificaciones y códigos de salida

Todos los comandos se ejecutaron mediante `rtk`; las pruebas usan exclusivamente `--settings=regulai.test_settings` y bases SQLite sintéticas aisladas. Los `.txt` de la redirección PowerShell conservan su codificación original UTF-16LE.

| Evidencia | Comando principal (tras `rtk proxy`) | Resultado |
| --- | --- | --- |
| `red-contract.txt` | `.venv/Scripts/python.exe regulai/manage.py test front.test_local_masking_integration.LocalMaskingContractTests --settings=regulai.test_settings --verbosity=2` | 3 tests; 2 fallos + 1 error; exit 1, esperado antes del cambio |
| `green-contract.txt` | Mismo selector, `--verbosity=1` | 3 OK; exit 0 |
| `config-migration-gate.txt` | Selectores `LocalMaskingContractTests LocalMaskingConfigurationTests LocalMaskingMigrationTests` del módulo nuevo | 10 OK, 0,423 s; exit 0 |
| `integration-real-detector-01.txt` | `front.test_local_masking_integration.LocalMaskingIntegrationTests` | 11 tests; 2 fallos de aserción del harness al recibir bytes; exit 1 |
| `integration-real-detector-02.txt` | Tests `test_json_citations_survive_real_local_detector_and_real_sdk_transport` y `test_semantic_simulation_masks_locally_and_audits_api_zero_before_judge` | 2 tests; simulación OK, cita falla `unknown_citation` por alias `S1` transformado; exit 1 |
| `privacy-policy-gate-01.txt` | `test front.test_local_masking_integration front.test_required_masking front.test_pipeline front.test_pipeline_privacy front.test_policy_simulator front.test_classification front.test_onboarding front.test_onboarding_migrations --settings=regulai.test_settings --verbosity=1` | **137 OK, 47,006 s; exit 0**, detector real corregido y proceso nuevo |
| `ui-final-config-tests.txt` | `test front.test_local_masking_integration.LocalMaskingConfigurationTests --settings=regulai.test_settings --verbosity=1` | 3 OK, 0,144 s; exit 0 tras ajuste visual final |
| `final-checks.json` | `check`, `makemigrations --check --dry-run`, `git diff --check` | Exit codes conservados en el archivo |

El gate final incluye 24 pruebas nuevas: contratos, tres entradas HTTP con SDK OpenAI real sobre `httpx.MockTransport`, detector realmente instalado, fallos/timeout, modelo ausente (nombre de paquete inexistente), YARA antes del detector, restricted, empresa ajena, revocación del backend en reserva o durante transformación, no reenvío de la misma petición, consentimiento invalidado, simulador real, citas JSON y migración reversible. Los tests bloquean `socket.socket.connect`; los jueces y transportes HTTP son respuestas sintéticas.

La migración prueba 0031 → 0032 → 0031 con URL remota, configuración, actividad e idioma conservados, sin alterar política ni AuditLog. No se ejecutó esta migración en una base de usuario. Las cotas mixtas se prueban en el límite 0,06 y justo por debajo, 0,059; la transformación local no consume cota remota y el recibo no convierte una máscara HTTP de coste desconocido en gratuita.

## Interfaz observada

`browser-runner.py` creó una base nueva `.claude/pilot-local-mask-ui-20261003-01/synthetic.sqlite3`, con red de proveedores bloqueada, servidor `127.0.0.1:8777` y credenciales públicas sintéticas. `--resume` solo reabre esa misma base tras comprobar ruta/metadatos/empresa, sin migrar ni regenerar. Se reinició para vaciar la caché de plantillas antes de verificar cada cambio visual. Base y capturas no contienen datos de usuario.

Se probaron alta local sin URL, error HTTP sin URL con borrador conservado, selección explícita del backend, creación HTTP inactiva, edición HTTP y Tab de nombre a backend. Chromium real, `@playwright/cli 0.1.22`, anchos 1440 y 390. Las capturas de alta, error, creación y resultados finales se inspeccionaron visualmente.

La captura `ui-mixed-overloaded-mobile.png` conserva el desbordamiento de 2655 px con nombre de 200 caracteres. El primer ajuste redujo el ancho pero comprimió excesivamente la columna (`*-fixed.png`); el ajuste final fija un ancho mínimo y conserva saltos legibles (`*-final.png`). El aviso ya no ensancha la página; tabla con desplazamiento horizontal interno. El margen global residual de 3 px existe también en el formulario normal y no se corrigió en la maqueta base.

`*-dark-css.png` es una exploración forzando `data-bs-theme=dark`, no un flujo de tema ofrecido por la aplicación. El CSS heredado mantiene fondos claros y texto secundario demasiado pálido. No se afirma soporte completo del tema oscuro ni accesibilidad auditada. Consola final: cero errores/avisos; el login emitió únicamente una sugerencia VERBOSE sobre autocomplete. Navegador cerrado y servidor detenido al finalizar.

## Límites

- Transporte real de SDK con HTTP simulado, sin probar eficacia de un proveedor pagado.
- Eficacia NLP/patrones, falsos positivos/negativos y límites operativos se miden en la evidencia del detector del coordinador. Integrar el detector no garantiza que encuentre todos los secretos o datos personales.
- PostgreSQL/HTTPS y reinicios de procesos pertenecen al ensayo del coordinador; aquí no se atribuyen resultados ajenos.
- No se activó ningún backend ni política para empresas reales. Los registros existentes siguen apuntando a su servicio HTTP hasta una edición expresa.

`source-sha256.json` congela los archivos relevantes y `evidence-sha256.json` los artefactos de esta carpeta. Los snapshots de Chromium están en `browser-snapshots/`; la copia temporal `.playwright-cli` de esta sesión se limpió después de conservarlos.
