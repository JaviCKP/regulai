# Cobertura manual de seguridad del diff fijo

Base `6c78cd396eb72713e85b72d8592970e4b6b66585`; candidato `febc8aa9b303070e82e3f27626371d5b67cb73f7`. Los 42 archivos modificados dentro de `regulai/`, `scripts/` y `ops/` se inspeccionaron. «Leído» no significa prueba de penetración exhaustiva. Los tests se ejecutaron en la copia fija de este directorio, con SQLite en memoria y sockets bloqueados.

| Archivo | Superficie revisada | Evidencia / alcance |
| --- | --- | --- |
| `regulai/front/chat_service.py` | D2, YARA original, contexto e historial, permisos, consentimiento, reserva previa, revalidación tras reserva, errores y liquidación | Lectura completa del flujo; suites focal y auth-state-logs; captura SDK propia de tres entradas |
| `regulai/front/masking.py` | Detección obligatoria `both`, cadena no vacía, URL sin credenciales, segmentos atómicos, redirects | Lectura completa; máscaras ausentes/inactivas/ajenas/fallidas/mutadas; sin conexión real |
| `regulai/front/policy.py` | Política obligatoria, restricted, YARA, destinos enumerados | Diff y funciones llamadas; suites focal/pipeline |
| `regulai/front/policy_simulator.py` | Rol/empresa, borrador sin permiso de salida, máscara antes de Jev, cambios de rol/configuración, costes | Diff y rutas de autorización/semántica; suites simulator/privacy/masking |
| `regulai/front/views.py` | Traslado de máscara; adaptadores HTTP; gestión de máscara limitada a seguridad/empresa | Diff y límites pertinentes; permisos POST/CSRF/empresa; URLs privadas son capacidad explícita del rol de seguridad |
| `regulai/front/templates/chat/chat.html` | Texto de consentimiento, HTML de contenido y atributos, datos de recibo | Diff y renderizadores; tests de HTML/JS; no navegador real independiente |
| `regulai/front/evaluation.py` | Aprobación, fuentes/ventana/destinos/modelos/tarifas, límites, ledger común, salida de informes | Lectura completa; suites pilot/smoke; SEC-1 reproducido en el SDK |
| `regulai/front/evaluation_budget.py` | Reserva SQLite transaccional, incertidumbre, estimación frente a cobro, identidades, reinicios | Lectura completa; tests concurrency/restart/overspend/zero/not_started |
| `regulai/front/management/commands/bootstrap_ai_policy.py` | Borrador que advierte máscara ausente o incompleta | Diff leído; no nueva autorización automática |
| `regulai/front/management/commands/evaluate_ai.py` | Entrada real unificada, fixtures offline, aislamiento de DB | Diff y delegación; suite smoke/pilot |
| `regulai/front/management/commands/run_demo.py` | Máscara sintética inmutable y transporte offline | Diff leído; no se arrancó servidor |
| `regulai/front/management/commands/smoke_ai.py` | Delegación en el mismo harness y ledger | Diff y archivo final completo; suite smoke/pilot |
| `regulai/regulai/pilot_lab_settings.py` | Host/DB internos, claves efímeras, cookies/HTTPS/CORS/media | Lectura completa; sin importar claves del laboratorio |
| `regulai/regulai/pilot_postgres_test_settings.py` | Overrides exclusivos de tests | Lectura completa; no se ejecutó PostgreSQL en esta revisión |
| `ops/pilot/Dockerfile` | Contexto de build, imagen fijada, entrypoint | Lectura completa; sin build/pull |
| `ops/pilot/images.json` | Identidades inmutables de imágenes | Lectura completa; no auditoría remota de imágenes |
| `ops/pilot/requirements.txt` | Dependencias de PG separadas | Lectura completa; no instalación ni auditoría de CVE repetida |
| `ops/pilot/manage_lab.py` | Guardas de settings/host/nombre DB; seed vacío; backup/rotación/concurrencia | Lectura completa; no DB de usuario ni operación destructiva ejecutada |
| `ops/pilot/nginx.conf` | HTTPS, Host, media privada y estáticos, logs | Lectura completa; laboratorio no arrancado por este revisor |
| `ops/pilot/synthetic_provider.py` | Transporte sintético, centinela original, registro sin cuerpo, límite de input | Lectura completa; servicio interno no arrancado |
| `scripts/pilot_lab.py` | Aislamiento Docker, copia/guardas, loopback, claves/backup/restore, propiedad de cleanup | Lectura completa; no se reutilizó como resultado propio evidencia previa del autor |
| `scripts/pilot_document_app_inventory.ps1` | Inventario de comandos/COM/registro sin lanzar apps | Lectura completa; no ejecución propia |
| `scripts/pilot_document_demo.py` | Workspace nuevo bajo .claude, SQLite nueva, loopback, transportes offline | Lectura completa; no se arrancó servidor |
| `scripts/pilot_human_report.py` | Validación de revisiones y output nuevo, sin red | Lectura completa y tests de `attach_reviews` |
| `scripts/prepare_pilot_manifest.py` | Manifiesto nuevo, hashes, no aprobación implícita | Lectura completa; no regeneración del manifiesto candidato |
| `scripts/verify_community.py` | Puertas locales, logs y hashes, test_settings, auditoría de dependencias | Lectura completa; no ejecución del lote completo ni red |
| `regulai/front/test_backend_hardening.py` | CSRF configurable; permisos y rotación | Diff leído; clases BackendHardeningTests y SecretRotationTests ejecutadas |
| `regulai/front/test_chat_flow.py` | Fixture con máscara, tres entradas, consentimientos, historial, replay | Diff leído y módulo ejecutado |
| `regulai/front/test_classification.py` | Adaptación del transporte y máscara obligatoria | Diff completo leído; módulo no ejecutado aquí |
| `regulai/front/test_document_fidelity.py` | Corpus sintético congelado y bloqueo/citas en tres entradas | Diff completo leído; corpus binario no ejecutado aquí |
| `regulai/front/test_evaluation_budget.py` | Proveniencia de coste y persistencia presupuestaria | Diff leído y módulo ejecutado |
| `regulai/front/test_evaluation_pilot.py` | Preflight sin DB/red, reportes sin aprobación/calidad automática | Archivo leído y módulo ejecutado |
| `regulai/front/test_frontend_chat.py` | Escapado, texto histórico y costes inciertos | Diff leído y módulo ejecutado |
| `regulai/front/test_onboarding.py` | Fixture de borrador con máscara y coste | Diff leído; módulo no ejecutado aquí |
| `regulai/front/test_pipeline.py` | Transporte SDK, intentos, YARA salida, historial y clasificación | Diff y casos leídos; módulo ejecutado |
| `regulai/front/test_pipeline_privacy.py` | Máscara completa, cambios concurrentes, minimización y presupuesto | Diff leído y módulo ejecutado |
| `regulai/front/test_policy_simulator.py` | Rol/empresa, borrador, coste desconocido, máscara previa | Diff leído y módulo ejecutado |
| `regulai/front/test_required_masking.py` | D2 y revalidación de motor/modelo/credencial tras reserva | Archivo completo leído y módulo ejecutado; diez mutaciones existentes pasan |
| `regulai/front/test_review_regressions.py` | Adaptación de máscaras/transportes a D2 | Diff leído; módulo no ejecutado aquí |
| `regulai/front/test_smoke.py` | Real-mode con HTTP/SDK falsos, aprobación/model drift, reinicios | Archivo completo leído y módulo ejecutado; fixture usada como base de PoC independiente |
| `regulai/front/test_state.py` | Consentimiento vinculado, historial y cambios de estado/migración | Diff leído y módulo ejecutado |
| `regulai/front/test_verification_flow.py` | Comprobaciones posteriores a máscara | Diff leído; módulo no ejecutado aquí |

Límites seguidos fuera del diff: `api/views.py`, `api/test_permissions.py`, `front/access.py`, `front/connectors.py`, `front/jev.py`, `front/test_operations.py`, `front/test_onboarding_migrations.py` y `regulai/settings.py`/`test_settings.py`. No se copió ni abrió `local_settings.py`; las únicas claves usadas fueron fixtures públicas sintéticas.
