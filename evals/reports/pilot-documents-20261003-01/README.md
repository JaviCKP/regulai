# Evidencia documental y navegador, 3 de octubre de 2026

Alcance: datos sintéticos locales, extractor público y vistas reales de Django;
transportes de proveedores sustituidos en el límite HTTP y salida del servidor
bloqueada. Ningún resultado mide calidad de proveedores reales. No se usó una base
de usuario, no se gastó en APIs y no se realizaron ensayos humanos.

## Resultado verificable

| Comprobación nueva | Resultado y evidencia |
| --- | --- |
| Expectativas previas del corpus | 12/12 en `extraction-results-final.json`; hashes y fragmentos exactos incluidos |
| Reproducibilidad | 12 archivos y manifiesto iguales byte a byte; `reproducibility.json` |
| Documentos y UI Django | 65 tests, 38.684 s, exit 0; `tests-documents-ui-final.log` y `test-run-final.json` |
| Tres entradas de envío | Tests nuevos comprueban bloqueo scan/blanco/XLSX sin caché y cita final página 3 en `/chat/`, `/chat/send/` y `/api/chat/send/` |
| Navegador | Chromium headless real 154.0.0.0 mediante Playwright CLI 0.1.22; acciones sobre DOM/UI real, no ensayo humano |
| Consentimiento | Imagen omitida y localizador visibles; `receipt-before-consent.json`, cero llamadas antes de confirmar |
| Cancelación | Tab/Enter cancelan; `receipt-cancelled.json`, estado `cancelled`, cero llamadas |
| Caducidad real | Más de 300 s de reloj; `state-after-real-expiry.json`, mismo identificador/archivo, `pending_consent` y cero llamadas |
| Renovación hasta completar en código final | 316,599294 s; `state-postfix-pending.json`, `state-postfix-expired.json` y `state-postfix-completed.json`: mismo id/SHA256/mensaje, cero llamadas hasta reconfirmar, luego `completed` y una respuesta |
| Generación y citas | `receipt-completed.json`; dos intentos, verificación sintética final superada y cita de 10 euros en párrafo 2 |
| Teclado, recarga y móvil | Capturas 06–10: Tab/Enter abren evidencia y cita; recarga conserva ficha/evidencia; viewport 375 × 812 sin desbordamiento horizontal del documento |
| Exportación | JSON descargado mediante el enlace de la ficha y conservado, sin transcribir valores a mano |
| Resultado incierto | Captura 09 y JSON: reconstrucción persistida `outcome_unknown`, coste de llamada y total desconocidos, ninguna respuesta; test dedicado |
| Contraste nuevo reproducido | Controles sin foco y enlace poco legibles en la burbuja original; CSS acotado, capturas 11–12 y medidas en `browser-observations.json` |

Los 302 tests y 150 casos offline históricos no son ejecuciones de esta entrega.
`tests-documents-ui.log` registra una ejecución anterior de 64 tests; el test
de coste desconocido eleva el recuento final a 65. Los errores HTTP deliberados
de los tests aparecen en el log; el resultado final del runner es `OK`.

## Procedencia y límites

`application-availability.json` registra PATH, COM, carpetas de instalación y
registro de desinstalación. No se detectaron Word, Excel ni LibreOffice; solo
un complemento Teams para Office. El intento de renderizado nativo de DOCX
terminó con `FileNotFoundError: LibreOffice soffice.exe was not found on PATH`.
No se crearon archivos guardados desde esas aplicaciones ni se recalcularon
fórmulas en Excel. Las nueve páginas PDF se renderizaron con Poppler, exit 0,
y se inspeccionaron visualmente en `pdf-contact-sheet.png`.

El corpus se creó con Python y modificaciones OOXML explícitas. El PDF raster
no procede de un escáner. La caché 10 del XLSX se inyectó y no es un cálculo
nativo. Las revisiones aceptadas y numeración prueban los casos concretos del
manifiesto, no toda la compatibilidad con Word. La tabla PDF conserva su texto,
sin prometer reconstrucción general de tablas.

La máscara del transporte offline es identidad sobre texto sintético y se
registra como `obfuscation`; no valida anonimización de un servicio real. Los
costes de la ficha son estimaciones del fixture, no facturas ni ahorro medido.
La inspección móvil es viewport Chromium, no teléfono físico ni auditoría WCAG
completa. La ficha larga tiene su propio desplazamiento vertical; una captura
de página completa no muestra necesariamente toda esa región interna.

## Sesiones y resultados no convertidos en éxitos

Los entornos `.claude/pilot-document-browser-20261003-01` a `04` fueron nuevos
y exclusivos de esta prueba. El primero migró/sembró, pero el runner falló al
buscar una ruta de plantilla incorrecta; se corrigió la ruta antes de navegar.
No se reutilizó ni se tocó `community-demo.sqlite3`.

El proceso `02` conservó código cargado antes de cambios paralelos en los
fixtures de demo. Sí mostró caducidad real a los 314 s; la siguiente confirmación
acabó en `classification_failed` después de la máscara. Se conserva como fallo
en `receipt-stale-process-failed.json`, no como renovación completa satisfactoria.
`browser-run-environment.json` contiene sus hashes. Se detuvo el proceso y se
creó `03` desde los archivos vigentes (`browser-final-environment.json`). Allí
confirmación, respuesta, cita, exportación y recarga funcionaron. Un intento
de repetir caducidad se confirmó a unos 298 s y fue éxito normal; no se cuenta
como caducidad. El proceso `04` carga el CSS corregido y su evidencia final
queda separada en `browser-postfix-environment.json` y observaciones.
En `04`, la primera confirmación ocurrió a los 316,599294 s y renovó sin
llamadas; la siguiente completó con una respuesta, ocho llamadas sintéticas y
dos generaciones, conservando id, archivo y mensaje. Capturas 15–16 y exportación
`receipt-postfix-completed.json`. La ficha completada conserva el motivo histórico
`consent_expired`, cuya frase «Review and confirm again» sigue en presente aunque
ya no hay botones de confirmación. Se comunica esa ambigüedad de texto para revisión;
no se oculta ni se atribuye a una nueva petición.

La captura 09 usa `replay_interrupted_receipt.py`, que solo admite un workspace
aislado con metadatos concordantes y rotula sus filas como reconstrucción
sintética. **No es una interrupción real de proceso.** La interrupción real
ejecutada por el agente de operaciones pertenece a otro informe. Aquí se
verifica únicamente la representación persistida sin total: «unknown», nunca
éxito ni coste cero.

## Comandos principales

Todos se ejecutaron desde la raíz con `rtk`. Los comandos generadores y de
verificación rechazan sobrescribir su salida; usar un nombre nuevo al repetir.

```powershell
rtk proxy powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pilot_document_app_inventory.ps1
rtk proxy C:/Users/javi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe evals/documents/pilot-20261003/generate_corpus.py --output .claude/pilot-corpus-new
rtk proxy .venv/Scripts/python.exe evals/documents/pilot-20261003/verify_corpus.py --output .claude/pilot-extraction-new.json
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_documents front.test_document_fidelity front.test_frontend_chat front.test_chat_ui front.test_frontend_resources --settings=regulai.test_settings --verbosity=1
rtk proxy .venv/Scripts/python.exe scripts/pilot_document_demo.py --workspace .claude/pilot-browser-new --port 8768
rtk proxy npx.cmd --yes --package @playwright/cli@0.1.22 playwright-cli -s=pilotdoc open http://127.0.0.1:8768/login/
rtk git diff --check -- regulai/front/templates/chat/chat.html regulai/front/test_document_fidelity.py regulai/front/test_frontend_chat.py
```

Inventario, generación final, verificación, tests y diff-check: exit 0. Los
servidores propios terminan con Ctrl+C (exit 1 por interrupción voluntaria).
El primer intento `npx --no-install` no tenía CLI instalada; se usó 0.1.22
mediante npx. Un `--help` inicial tuvo una aserción libuv al salir; las acciones
del navegador posteriores sí se ejecutaron. Errores exploratorios de lectura
DOM/SQL se corrigieron sin modificar datos ni producto y no cuentan como checks.

## Trabajo humano y aplicaciones pendientes

[Dos protocolos completos](../../../docs/plan-blackhat/documentos-y-ensayos-piloto.md)
y [formularios sin respuestas inventadas](human-rehearsal-form.md). H1 y H2
requieren participantes, fecha, tiempos, ayudas y observaciones reales. La
comparación con documentos guardados en aplicaciones nativas requiere disponer
de Word/Excel o LibreOffice y guardar una muestra equivalente. Esas tareas
siguen pendientes; no impiden reproducir el corpus técnico ya entregado.
