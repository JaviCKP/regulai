# Seguimiento de recibos y confirmación, 3 de octubre de 2026

El recibo de una petición ya completada conservaba `consent_reason=consent_expired`
y mostraba una instrucción para confirmar otra vez. La corrección presenta ese
motivo como antecedente: **Previous confirmation notice: A previous confirmation
expired.** Una petición `pending_consent` conserva su instrucción y botones.

## Pruebas y resultados conservados

| Evidencia | Resultado observado |
| --- | --- |
| `red.log` | El test nuevo falla: 1 test, 0,097 s. El primer envoltorio devolvió erróneamente exit 0; ese código no acredita una ejecución correcta ni es la prueba roja autoritativa. |
| `red-verified.log` | Repetición autoritativa: 1 test, 0,095 s, `FAILED (failures=1)`, exit 1 comprobado por el ejecutor. No encontraba `Previous confirmation notice`. |
| `green.log` | Tras la corrección: 7 tests, 4,286 s, `OK`, exit 0. |
| `integration-fixtures-green.log` | Primera integración: 44 tests, 21,524 s, un fallo en la aserción adicional de `test_local_classification_ignores_semantic_category_for_routing` (`blocked` frente a `completed`). Se conserva como fallo. |
| `integration-fixtures-final.log` | Resultado final de integración: 44 tests, 31,142 s, `OK`, exit 0. |

Los logs de PowerShell llevan BOM UTF-16; no se han convertido ni sobrescrito.
El manifiesto calcula los hashes de sus bytes originales. Los códigos indicados
proceden de las ejecuciones del agente raíz; esta revisión vuelve a leer y
verificar la evidencia, sin repetir la suite.

## Verificación visual real

[Observaciones](browser-observations.json), [fuentes y entorno](browser-environment.json)
y capturas `browser-*.png`. Chromium headless 154.0.0.0, Playwright CLI 0.1.22,
ventanas de 1280 × 720 y 375 × 812. Se abrió y examinó el recibo en la aplicación
Django; no se dedujo su apariencia a partir del HTML.

Se reutilizó exclusivamente la base sintética `browser04`. La petición
`e7c85964-6e98-4fcd-86dc-daa86d669dc0` había caducado y terminado en el recorrido
anterior; su fecha de actualización siguió siendo `2026-10-03 14:17:45.915112`.
No se reconstruyó, migró, sembró ni reseteó ese registro. Con las fuentes corregidas
el recibo muestra el aviso en pasado, sin `confirm again`, `Confirm sending` ni
`Cancel request`. Capturas `browser-completed-desktop-notice.png` y
`browser-completed-mobile-light.png`; el snapshot conserva el texto exacto.

La petición nueva de control `88f78237-1b17-4897-8a66-ab78432bac25` se creó desde
la UI con `SYNTHETIC_CONSENT_CANCEL`. En `pending_consent` mantuvo la instrucción
de revisar y los dos botones. Se canceló con Tab/Enter; los estados antes y
después conservan cero llamadas. No se repitió la espera de 300 segundos.

La pantalla no ofrece selector de tema. Además del aspecto claro predeterminado,
se forzó temporalmente `data-bs-theme=dark` para revisar los estilos Bootstrap
incluidos: el aviso y los controles seguían legibles en ambos anchos. Las capturas
`*-dark-css.png` identifican esa variación exploratoria; no acreditan un flujo
de tema soportado ni una auditoría general de accesibilidad. Otras superficies
conservan fondos claros y texto pálido heredado. El ancho del documento y cuerpo
en móvil fue de 375 px, igual al viewport; no se usó un teléfono físico.

## Procedencia, hashes y limpieza

`browser-runner.py` solo admite el workspace sintético conocido y comprueba el
identificador, estado, empresa y hash documental esperados. No ejecuta seed ni
migraciones y mantiene el transporte offline con protección de sockets/HTTP.
El entorno registra los hashes de plantilla, test, servicio y fixtures cargados,
con HEAD de referencia `a3bc67b25b341cb28172bebd5001ef48c5b8d34f` y cambios locales.
La comprobación final de esas fuentes no encontró discrepancias.

`browser-console.json` conserva cero errores de consola. `browser-cleanup.json`
registra sesión `pilotui` cerrada (exit 0), servidor propio detenido con Ctrl+C
(exit 1), puerto 8769 sin listener y `.playwright-cli` propio retirado después
de guardar la evidencia. La base sintética privada permanece local.

La revisión adicional de [secretos conocidos](../pilot-operations-20261003-summary-final/secret-review.json)
comparó en memoria 24 valores sintéticos del laboratorio en 440 archivos de
texto de UI/operaciones: cero coincidencias y ningún bloque PEM de clave privada.
No se imprimieron valores. Esto no constituye un detector general de secretos.

`evidence-sha256.json` incluye todos los archivos de este informe salvo su propio
índice. No hubo cambios de implementación, llamadas a proveedores reales,
contactos con participantes, publicación ni despliegue durante la revisión visual
o este cierre documental. La evidencia original anterior permanece intacta.
