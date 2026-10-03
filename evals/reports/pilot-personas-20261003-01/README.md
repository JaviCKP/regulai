# Dos perfiles simulados — 3 de octubre de 2026

**Simulación solicitada completada: P01, empleado de Alpha, y P02, administrador de Beta.** Son perfiles artificiales. Sus recorridos y formularios distinguen evidencia anterior, comprobaciones nuevas e inferencias del agente. No se registran participantes, testimonios ni tiempos humanos; el banco reservado y los formularios humanos permanecen sin valoraciones inventadas.

| Perfil | Recorrido y formulario | Evidencia nueva y límites |
| --- | --- | --- |
| P01 | [Informe y recorrido H1/H2](../pilot-persona-p01-simulated-20261003-01/informe.md), [formulario simulado](../pilot-persona-p01-simulated-20261003-01/formulario-simulado.md) | Cancelación del Word visual en Chromium mediante Tab/Enter, descarga real de ficha, mismo request/documento, cero llamadas y respuestas. Identidad técnica `community-demo`, no una sesión de Alpha. Extracción 12/12 y 96 comprobaciones de archivos/coherencia, incluidos 73 hashes históricos; no son 96 tests de producto. |
| P02 | [Informe](../pilot-persona-p02-simulated-20261003-01/README.md), [19 pasos](../pilot-persona-p02-simulated-20261003-01/p02-simulated-walkthrough.md), [formulario simulado](../pilot-persona-p02-simulated-20261003-01/p02-simulated-form.json) | 22 tests HTTP/Django correctos y 15/15 controles sobre snapshot fijo; administrador Beta sin privilegios de plataforma, recursos ajenos 404 y catálogo global 403. Extracción 12/12 más TXT inglés. No hubo navegador nuevo en este perfil. |

P01 revisó inicialmente `535eb9d`; su nueva comprobación de navegador se ejecutó sobre `972edb8`. P02 trabajó en un snapshot inmutable de `535eb9d`. Cada informe conserva fuentes, comandos y fechas; la evidencia histórica no se atribuye a la versión posterior.

El suplemento P02 `run-02` permanece **fallido**: 23 tests, tres subtests de cancelación documental bloqueados antes del consentimiento por una fixture sin el destino Jev necesario. No se corrigió el producto ni se cambió la expectativa. La cancelación nueva de P01 aporta evidencia de navegador independiente, pero no convierte aquel suplemento en verde ni demuestra por sí sola las tres entradas HTTP.

Las hipótesis de comprensión P2 se concentran en etiquetas inglesas, distinguir texto leído de imagen omitida, localizar el primer intento rechazado y leer una ficha larga en móvil. No son problemas observados en personas. No se han medido satisfacción, autonomía, accesibilidad universal, calidad semántica ni ahorro.

**Decisión sustentada:** continuar con demostraciones locales de datos sintéticos y usar estas dudas como guion de observación; mantener detenido el ensayo pagado mientras se concilia su llamada incierta. La simulación está entregada. La comprensión por personas, H2 exacto sin ayuda y los guardados de Office nativo siguen sin validar.

El servidor nuevo quedó detenido y el navegador cerrado. No hubo llamadas reales, contactos, despliegue ni modificaciones del ledger en estas simulaciones.

[Inventario de 50 copias exactas](files.json) y [empaquetador](package.py). Las carpetas de cada perfil mantienen la profundidad de los originales para conservar sus enlaces. Solo se copiaron sus listas explícitas: se excluyeron bases, claves, cookies, sesiones, ZIP y medios privados. Los scripts son procedencia de ejecución y sus informes detallan qué fixtures aisladas hacen falta para repetirlos; no se distribuye una sesión autenticada.
