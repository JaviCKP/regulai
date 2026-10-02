# Estado observado de la implementación

2 de octubre de 2026. Rama local `codex/community-blackhat`, base `6a0f667`. Sin push, despliegue ni publicación. Los planes conservan la especificación original y anotan su implementación. [Arranque y guion](arranque-y-demo.md); [tracker local](tareas/00-base.md).

## Entorno y datos

Python 3.12.11; Django 5.2.17 LTS; DRF 3.18.1. Una lista raíz de 45 paquetes fijados; la interior remite a ella. Se sincronizó el entorno con `uv pip sync`. La auditoría inicial encontró 96 avisos en 12 paquetes; tras actualizar, `pip-audit` informó cero vulnerabilidades conocidas. No es una garantía de ausencia de vulnerabilidades. [Versiones y auditoría](dependencias-verificadas.md).

Preparación histórica: el primer test esperaba una alerta del validador puro y falló `0 != 1`; se corrigió para comprobar coincidencias y ausencia de efectos. Las alertas se prueban ahora desde HTTP. `scripts/bootstrap_local.py` creó configuración y SQLite de desarrollo una sola vez, sin sustituir bases o secretos existentes. `MESAS_RETIRO.pdf` permanece ajeno a la implementación.

Migraciones 0026–0028 añaden procedencia/estados, configuración IA, catálogo y empresa de auditoría. Las pruebas de migración conservan mensajes legacy sin autorizarlos para contexto. No se cambian claves de cifrado. Credenciales guardadas en campos cifrados; nunca en los ejemplos JSON.

## Implementación disponible

- Las tres entradas web/API/POST antiguo llaman al servicio compartido. YARA inválida, documento ilegible, política ausente y destino denegado detienen la salida. `consent_confirmed` no autoriza: confirmación firmada vinculada a contenido, empresa, archivo, contexto y destinos; `request_id` estable para confirmar, cancelar y repetir.
- Solo turnos enlazados y autorizados entran en el historial. El propietario ve los mensajes legacy, con aviso, pero no se envían a proveedores. Prompt/AuditLog legacy sin procedencia de empresa quedan fuera de los listados de personal; se conservan en la base.
- Extracción acotada con cobertura, digest y fragmentos estables. PDF textual, DOCX, XLSX, CSV y textos admitidos; archivos corruptos/cifrados, bombas y límites producen estados explícitos. Imágenes y XLS no admitidos; sin OCR ni ruta visual implícita.
- Clasificación Jev, router y verificación integrados: contrato HTTP estricto, catálogos activos de la empresa, calidad configurada, capacidad, precio, presupuesto y plazo. Máximo dos generaciones; ambas se verifican. Bloqueos locales se aplican también antes del juez y de la integración de enmascarado existente.
- Ficha pública de decisión y evidencia con filtrado de campos, costes desconocidos explícitos y permisos de propietario/empresa actual; descargas preservadas. Las citas deben pertenecer al archivo y tener extractos reales; el respaldo semántico requiere un juicio específico.
- Simulador con borradores JSON/YARA temporales y señales sintéticas explícitas que no rebajan el mínimo local de sensibilidad. La ruta reserva también el coste de clasificación y jueces obligatorios. Modo semántico opcional bajo la política vigente y presupuesto acotado, sin generador. Activación separada revalida destinos y versión/digests; la auditoría de empresa conserva configuración y fuentes YARA antes/después para recuperación, sin muestra ni credenciales.
- Administración global/Django admin limitada a operadores activos con `is_staff`, `is_superuser` e ID en `PLATFORM_ADMIN_USER_IDS`. Administradores de empresa usan ámbitos propios y no pueden resetear ni borrar el perfil del operador. Archivos privados y avatares validados por rutas autenticadas; sin alias público de media.

## Evidencia automatizada

Suite final: `rtk proxy .venv/Scripts/python.exe regulai/manage.py test front api --settings=regulai.test_settings`: **129 pruebas correctas en 19,891 s**. `makemigrations --check --dry-run --settings=regulai.test_settings`: sin cambios. `rtk proxy uv pip check --python .venv/Scripts/python.exe`: 45 paquetes compatibles. Los resultados parciales siguientes se observaron en distintas revisiones y no deben sumarse como tests únicos:

Reproducción desde cero: `rtk proxy uv venv --python 3.12.11 .claude/reproduction-venv-20261002` y sincronización de la lista raíz instalaron los mismos 45 paquetes. Desde ese intérprete, `test front api --settings=regulai.test_settings`: **129 correctas en 39,764 s**; `check --settings=regulai.test_settings`: cero incidencias; `run_demo --settings=regulai.demo_settings --seed-only`: correcto. El bootstrap se repitió y preservó los settings locales existentes. `migrate --check` terminó con código 0. Esta comprobación no reemplaza el recorrido visual, realizado con el entorno original.

| Comando desde la raíz, con `rtk proxy .venv/Scripts/python.exe regulai/manage.py` | Resultado observado |
| --- | --- |
| `test front.test_policy_simulator --settings=regulai.test_settings` | 14 correctas; incluye mínimo local de sensibilidad, reserva de jueces y fuentes YARA para recuperación |
| `test front.test_documents front.test_chat_ui front.test_policy_simulator --settings=regulai.test_settings` | 27 correctas |
| `test front.test_policy_simulator front.test_pipeline front.test_chat_flow --settings=regulai.test_settings` | 40 correctas |
| `test front.test_demo front.test_evaluation api front.test_runtime --settings=regulai.test_settings` | 21 correctas |
| `test front.test_policy_simulator front.test_smoke front.test_evaluation_budget --settings=regulai.test_settings` | 21 correctas: 14 simulador, seis smoke y una de presupuesto/concurrencia |

Se probaron las tres entradas HTTP, el límite de proveedor HTTP/SDK, migración legacy, confirmaciones solapadas, idempotencia, cambios de empresa/contexto/política, coste incierto y ausencia de reintentos ocultos. Las pruebas usan SQLite aislado y proveedores simulados, sin llamadas pagadas.

El [JSON de configuración](ai-config-example.json) se validó mediante `AIConfig.model_validate_json` en `manage.py shell --settings=regulai.test_settings`: correcto, sin destinos y con presupuesto cero. No activa llamadas ni contiene claves.

Banco final [offline-2026-10-02-04](../../evals/reports/offline-2026-10-02-04/report.md), ejecutado tras los últimos cambios Jev/simulador/smoke: 50 casos × tres configuraciones = **150 ejecuciones**, 150 controles correctos, cero salidas prohibidas y cero llamadas reales. Casos de desarrollo/reservados, manifiesto, hashes SHA-256 de los bytes exactos de los archivos ejecutados, resultados por caso y resúmenes conservados. Se volvieron a comprobar los seis hashes y coinciden con los archivos actuales; no normalizan saltos de línea. El commit del manifiesto (`023c7ef`) era el HEAD al ejecutar sobre cambios locales; los archivos probados quedaron después en `cfa29fa`. Los informes 01–03 se conservan como ejecuciones previas. Costes y respuestas son fixtures; latencia local. **No demuestra precisión de Jev, calidad factual ni ahorro real.**

La regresión de metadatos Jev se reprodujo en rojo y pasó tras aceptar `provider_metadata` y `providerMetadata` con la misma validación; si ambos aparecen y discrepan, se rechaza la respuesta. No se convierten metadatos inválidos en uso/coste de confianza.

## Pruebas reales acotadas y límite de cuenta

Presupuesto histórico conjunto autorizado: **1 USD**, con registro persistente `.claude/real-provider-budget.sqlite3`. Las instrucciones vigentes excluyen nuevas llamadas pagadas, compra de créditos y recargas automáticas. No se harán nuevas llamadas reales Jev.

Una llamada sintética DeepSeek resolvió `2 + 2` como `4`: 25 tokens de entrada y uno de salida, estimación superior con tarifa punta **0,00000870 USD**. Es una comprobación de integración y contabilidad, no un benchmark. [Informe real 01](../../evals/reports/real-smoke-2026-10-02-01/report.json).

Tres intentos Gateway/Jev devolvieron HTTP 403. El diagnóstico explícito fue «Free tier users do not have access to this model. Upgrade to paid credits…», con `providerAttempts: 0`. Que el catálogo enumere el modelo no demuestra acceso de la cuenta. La contabilidad conserva **0,03 USD de reservas inciertas** y no las convierte en gasto confirmado ni en cero. El [export final seguro de presupuesto](../../evals/reports/real-budget-2026-10-02.json) conserva límite de 1 USD, estimación conocida de 0,00000870 USD y reservas de 0,03 USD. Los informes reales 01/02 recogen los dos primeros intentos; el tercero fue diagnóstico de acceso. [Contrato y resultado Gateway](jev-gateway.md).

Quedan bloqueados externamente: calibración real de sensibilidad y jueces, comparación real de economy/strong/router, ahorro observado y respuesta documental con citas verificada de extremo a extremo en vivo. Los umbrales y calidades sintéticos no se publican como calibración.

## Navegador y demo

Servidor local normal: `127.0.0.1:8765`; usuario sintético `community-local-demo`, contraseña pública local `Local-demo-only-2026!`. La configuración de IA se restauró a `{}` para impedir gasto accidental. En navegador se confirmó `policy_configuration_invalid`, HTTP 503, ficha y cero llamadas.

Demo separada: `run_demo --settings=regulai.demo_settings`, `127.0.0.1:8001`, base `regulai/community-demo.sqlite3`, medios y cookies propios. Usuario `community-demo`, contraseña pública sintética `community-demo-only`. Siembra repetida sin resetear datos; un fixture modificado se conserva y causa error. Proveedores simulados y salida HTTP/socket del servidor bloqueada solo dentro de ese comando. El navegador puede pedir glifos a Iconify; no se afirma aislamiento completo de red del navegador.

En navegador offline `8001` se comprobó adjuntar el contrato, respuesta de 10 euros y cita de la línea 2, dos generaciones/cinco llamadas simuladas, y persistencia al recargar. `SYNTHETIC_SECRET_DEMO` quedó bloqueado con cero llamadas. La advertencia de consentimiento mostró cero llamadas antes de confirmar. Cancelar terminó en `cancelled`, sin respuesta; confirmar con el archivo original devolvió `10 euros [1]`, con una única burbuja de usuario y evidencia de línea 2. Capturas: [evidencia documental](../../evals/reports/ui-2026-10-02/document-evidence.jpg), [bloqueo](../../evals/reports/ui-2026-10-02/blocked.jpg) y [documento confirmado/interfaz adaptable](../../evals/reports/ui-2026-10-02/confirmed-document.jpg). Son resultados de la demo offline, no proveedores en vivo.

La escena sencilla devolvió `Hola`, con ruta automática y tres llamadas simuladas. El simulador se probó en otra empresa local sin claves ni destinos: comparación interna/restringida con bloqueo y sus motivos, semántica no evaluada y cero llamadas reales; activación separada correcta, revisión 2. La auditoría SQLite conservó revisión anterior 1 y nueva 2 para recuperación, cero intentos semánticos y cero `Prompt`. [Captura](../../evals/reports/ui-2026-10-02/simulator-activated.jpg) y [registro visual](../../evals/reports/ui-2026-10-02/README.md).

Teclado: Enter envió el mensaje y abrió la ficha; Espacio alternó la ruta automática, restaurada activa. **Pendientes:** apertura de citas con teclado y dos ensayos completos con otra persona. La herramienta de navegador rechazó reabrir la URL local y no permitió cerrar la comprobación de citas; no se atribuye ese resultado al producto. Los ensayos humanos son un requisito externo aún no realizado. No hay despliegue autorizado.

## Revisiones locales conservadas

`18ecca7` preparación; `75ec867` Django LTS/dependencias únicas; `b99434a` dependencias vulnerables/pypdf; `853d495` documentos; `48a25e8` Jev/router/verificación; `2a5bd40` estados/configuración/procedencia; `023c7ef` recursos locales; `bbb86a5` runtime compartido; `6496ef7` presupuesto/smoke; `cfa29fa` evaluación/demo; `9e438fc` evidencia final y README. Son commits locales, sin push; la documentación final se revisa por separado. El [registro de verificación final](../../evals/reports/release-verification-2026-10-02.json) conserva comandos, resultados de ambos entornos y pendientes.
