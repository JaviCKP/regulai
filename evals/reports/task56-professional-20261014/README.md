# Evidencia de la tarea 56

Implementación local del 14 de octubre de 2026. No hay despliegue, push,
habilitación de cuentas existentes ni llamadas a APIs de pago. Ver
[operación y activación](../../../ops/agent_chat/PROFESSIONAL.md) y
[tarea](../../../docs/plan-blackhat/tareas/56-agente-profesional-web-codigo.md).

## Alcance de la evidencia

- **Contratos:** Django/PostgreSQL reales, tres entradas HTTP, proveedor simulado
  en la frontera HTTP, claves sintéticas. Los tests de unidad impiden sockets
  inesperados. El recorrido combinado usa el SDK real y comandos reales dentro
  de namespaces Linux; sustituye únicamente el transporte administrativo E2B.
- **Componentes reales:** código Python/Node/shell nuevo, error/reparación,
  instalación offline de paquetes descargados de registros públicos, Chromium
  con JavaScript y recursos mediados, LibreOffice/Poppler, archivos y revisiones.
  El broker también abrió tres dominios públicos reales con redirección.
- **Autonomía viva:** no probada. Las respuestas del modelo y el buscador del
  recorrido integrado son una secuencia controlada. El informe cuántico es un
  fixture explícito, no un informe investigado por un modelo vivo. Tampoco se
  construyó/desplegó la nueva imagen E2B.

## Matriz de aceptación

«Configurada: laboratorio» significa habilitada con datos sintéticos en los tests;
los interruptores del producto y los permisos de cuentas existentes no cambiaron.

| Capacidad | Implementada | Configurada | Verificada con simulación | Verificada en entorno real | Requisito pendiente |
| --- | --- | --- | --- | --- | --- |
| 1. Web general y citas | Sí, consultas y URLs libres | Laboratorio; Tavily no en cuenta real | Tres temas, dominios nuevos, redirección, PDF, referencias/cobertura | Broker HTTP a python.org, eia.gov y unwto.org → untourism.int | Búsqueda y selección autónoma con Tavily/modelo vivos |
| 2. Código nuevo y reparación | Sí, herramientas SDK conectadas | Laboratorio Linux | Tool call → autorización → resultado → siguiente inferencia | Python falla, se lee NameError, se edita y calcula 42; Node calcula 42; shell/archivos | Repetir en nueva imagen E2B y con modelo vivo |
| 3. Dependencia ausente | Sí, broker y versiones/hashes | Laboratorio | Especificaciones/URLs/digests rechazados cuando no cumplen | humanize 4.13.0 e is-number 7.0.0 descargados, instalados offline y utilizados | Verificar imagen nueva; paquetes con scripts/sdists fuera de alcance |
| 4. Dataset → código → gráfico → informe | Sí | Laboratorio | Descubrimiento/descarga controlados; nueve inferencias y ocho operaciones por HTTP | CSV procesado en namespace: total 54 MWh y media 18; gráfico, DOCX/PDF y XLSX reales | Selección y ejecución autónoma con proveedores vivos |
| 5. Word/PDF español de cinco páginas | Sí, publicación/render automático | Laboratorio | Petición desde chat, cinco páginas, Word/PDF derivados juntos | DOCX/PDF editables/renderizados; cinco PNG inspeccionados | Calidad factual y planificación del informe con modelo vivo |
| 6. Datos heterogéneos | Sí | Laboratorio | CSV con columnas arbitrarias, XLSX de varias hojas; originales cifrados íntegros | Tres hojas, fórmulas, gráfico y hashes del CSV | Ampliar corpus del piloto; sin afirmar cobertura universal |
| 7. Edición y revisiones | Sí | Laboratorio | Base vigente, un escritor, historial, entrega solo de última revisión reparada | Word: cambia document.xml; XLSX: sheet2.xml; PPTX: slide2.xml; resto idéntico | Calidad semántica de ediciones autónomas |
| 8. Errores y veracidad | Sí | Laboratorio | Sin clave, 429, fallo de buscador, 403, PDF parcial/sin OCR, contradicciones, presupuesto | Límites y errores de ejecución reales; cobertura pública registrada | OCR no instalado; no inferir resolución autónoma de contradicciones |
| 9. Fronteras | Sí | Laboratorio | SSRF/DNS/redirects, inyección de estado, empresas, salida de datos y fórmulas activas | Namespaces sin host/metadata/red; symlinks rechazados; browser sin salida ni WebSockets | Repetir sondas/recursos agregados sobre kernel E2B real |
| 10. Continuidad, Jev y dinero | Sí | Laboratorio | Duplicados, revocación, checkpoints, reanudación sin reiniciar consumo, Jev/costes | Timeout mata comando e hijos; archivos recuperados en namespace nuevo, enlaces solo al runtime inmutable | Destrucción/caída de microVM nueva; cargos reales de proveedores |
| 11. Interfaz | Sí | Loopback con estados simulados | Fuentes, detalles de código/costes, cancelación/reanudación, errores | Edge real: escritorio/móvil, claro/oscuro, teclado, preview/descarga | Piloto autenticado contra infraestructura desplegada |
| 12. Entradas y configuración | Sí, migración 0041 y grants explícitos | Base PostgreSQL aislada | Tres rutas, frontera de proveedor, usuario sin prefijo, sin DEBUG, migración ida/vuelta | Aplicación HTTP+SDK+Linux real, descarga privada; dry-run sin mutaciones | Activación autorizada de la cuenta existente |

## Resultados guardados

- [Pruebas de aplicación](application-tests.json), [salida completa](application-tests.log).
  **141 pruebas correctas en 147,535 s**. Incluyen permisos, HTTP, dinero,
  documentos, UI y migraciones sobre PostgreSQL 18.6 aislado en loopback:55456.
- [Runtime y SDK](runtime-tests.json), [salida completa](runtime-tests.log):
  **14 pruebas, todas correctas**; ocho de ejecución real Linux y seis de SDK/pool.
- [Recorrido HTTP+SDK+namespace](http-sdk-namespace.json): completado, nueve
  inferencias simuladas, ocho operaciones, cinco páginas, cuatro formatos de
  descarga y una fuente controlada. No es una prueba de autonomía.
- [Red pública y paquetes](public-network.json): respuestas reales, fecha,
  redirecciones, tamaños, versiones y SHA256. No invoca buscador ni modelo.
- [UI y revisión visual](ui-review.json): observaciones del navegador y límites.
- [Comprobaciones estáticas](static-checks.json): compilación, sintaxis, migración
  sin drift, whitespace e inspección de la base OCI.

Artefactos de prueba: [Word revisado](artifacts/quantum-v2.docx),
[PDF de cinco páginas](artifacts/render-quantum-v2.docx/quantum-v2.pdf),
[Excel revisado](artifacts/analysis-v2.xlsx), [PowerPoint revisado](artifacts/deck-v2.pptx),
[gráfico](artifacts/chart.png) y [cálculos](artifacts/analysis.json). Las revisiones
v1 se conservan en la misma carpeta. El manifiesto [artifact-hashes.json](artifact-hashes.json)
permite comprobar los bytes de estos archivos. Los hashes del recorrido HTTP
pertenecen a sus propios artefactos generados, no a otra ejecución del fixture.

Capturas: [escritorio claro](../../../output/playwright/task56-desktop-light.png),
[escritorio oscuro](../../../output/playwright/task56-desktop-dark.png),
[móvil claro](../../../output/playwright/task56-mobile-light.png),
[móvil oscuro](../../../output/playwright/task56-mobile-dark.png),
[preview](../../../output/playwright/task56-preview-desktop.png),
[error](../../../output/playwright/task56-error.png),
[cancelación](../../../output/playwright/task56-cancelled.png).

La inspección visual detectó un solapamiento real en el primer render de la
diapositiva 2; se corrigieron las coordenadas/medidas del fixture y se volvió a
renderizar e inspeccionar. No se trató el éxito estructural como prueba visual.

## Reproducción sin gasto

Entorno observado: Windows/WSL Ubuntu, Python 3.12.13, Node 24.21.0, bubblewrap
0.11.1, LibreOffice 26.2.6.3, Poppler 26.01, PostgreSQL 18.6; Deep Agents 0.6.12,
LangChain 1.4.3, langchain-core 1.6.7, langchain-e2b 0.0.6 y E2B 2.53.1. Playwright
1.64.0 usa Chromium 1248. Las versiones Debian del Dockerfile son distintas y
están fijadas: no se presenta WSL como una construcción de esa imagen.

Usar los entornos Python del repositorio/SDK y sus locks. En WSL se requieren uv
en `~/.local/bin`, bubblewrap, LibreOffice, Poppler, PostgreSQL 18 y dependencias de
Chromium. El script no instala paquetes del sistema ni toca una base existente.
Prepara exclusivamente `/tmp/regulay-task56-20261014` y sus cachés de herramientas.
En otra cuenta Windows/WSL se deben ajustar las rutas y, para los tests,
`REGULAY_TEST_BROWSER_CACHE` / `REGULAY_TEST_RUNTIME` si difieren.

Desde la raíz del checkout:

```powershell
rtk proxy wsl -d Ubuntu -- python3 /mnt/c/Users/javi/Documents/Codex/regulai-platform/ops/agent_chat/prepare_professional_lab.py prepare-runtime
rtk proxy wsl -d Ubuntu -- python3 /mnt/c/Users/javi/Documents/Codex/regulai-platform/ops/agent_chat/prepare_professional_lab.py start-postgres
rtk proxy .venv/Scripts/python.exe ops/agent_chat/verify_professional_public.py
rtk proxy ops/agent_probe/.venv/Scripts/python.exe ops/agent_chat/run_professional_runtime_tests.py
rtk proxy .venv/Scripts/python.exe ops/agent_chat/run_professional_tests.py
rtk proxy .venv/Scripts/python.exe regulai/manage.py makemigrations --check --dry-run --settings=regulai.agent_professional_test_settings
rtk proxy .venv/Scripts/python.exe ops/agent_chat/preview_professional_ui.py
```

El último proceso sirve únicamente en `127.0.0.1:8766`. La UI usa las plantillas,
CSS y JS reales con snapshots marcados como simulados. Revisar escritorio/móvil,
fuentes, preview, PDF, edición, detalles, teclado y estados `error`, `active`,
`cancelled` y `deck`. Detenerlo con Ctrl+C. Para cerrar el PostgreSQL desechable:

```powershell
rtk proxy wsl -d Ubuntu -- python3 /mnt/c/Users/javi/Documents/Codex/regulai-platform/ops/agent_chat/prepare_professional_lab.py stop-postgres
```

Los comandos generan evidencia y sobrescriben solo sus informes de prueba. No
importan settings productivos ni ejecutan el worker contra un proveedor vivo.
La activación y el ensayo de autonomía siguen el procedimiento separado del
manual y requieren las autorizaciones que el encargo actual excluye.
