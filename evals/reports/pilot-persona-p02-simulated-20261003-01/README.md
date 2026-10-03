# P02 simulado: administrador de la empresa ficticia Beta

**Simulación de un perfil, no participación humana.** Este paquete recorre H1 y H2 mediante revisión documental, inspección nueva de capturas históricas y controles automáticos nuevos offline. No hubo inicio de sesión en navegador, acciones Tab/Enter, espera de 300 segundos, exportación desde navegador ni entrevistas nuevas. Las reacciones atribuidas al perfil son hipótesis redactadas por el agente y están rotuladas como tales.

Perfil supuesto: administrador de Beta, español como idioma de trabajo, lectura de un documento inglés, atención a privacidad y a la incertidumbre. La persona ficticia no recibe privilegios de plataforma. En el control nuevo su usuario tiene `Role=Admin`, `is_staff=False` e `is_superuser=False`.

El [recorrido de 19 pasos](p02-simulated-walkthrough.md) conserva objetivo/entrada, expectativas enlazadas, evidencia previa, acción nueva real, observable, reacción hipotética y duda/severidad por paso. El [formulario separado](p02-simulated-form.json) deja vacíos los datos y resultados humanos. El [formulario humano original](../../../evals/reports/pilot-documents-20261003-01/human-rehearsal-form.md) no fue editado.

## Qué se verificó ahora

Código efectivo: copia de Git del commit **`535eb9d8421006ea8476ea511427a7dcda9cee3b`**, extraída bajo esta carpeta. No se ejecutaron las correcciones concurrentes del checkout. El candidato del ensayo vivo `698e8f0` se recibió como contexto del coordinador, no se volvió a ejecutar. La procedencia antes/después conserva 171 archivos Python/HTML idénticos en la copia fija; el historial del repositorio y los archivos de otros agentes quedaron fuera de esta tarea.

| Control nuevo | Resultado y límite |
| --- | --- |
| Suite HTTP/Django seleccionada | [run-01/tests.log](run-01/tests.log): 22 tests OK en 8,460 s, sin omisiones; 15/15 controles. SQLite en memoria, medios y temporales propios. Incluye consentimiento, expiración por reloj simulado, bloqueo y citas en las tres entradas, aislamiento, doble envío, timeout y representación de coste desconocido. |
| Administrador Beta | Cuatro recursos propios con HTTP 200. Conversación, ficha, evidencia y descarga de otro propietario Beta y de Alpha: HTTP 404. Intento de cambio del catálogo compartido: HTTP 403. No demuestra todas las superficies administrativas. |
| Cancelación del DOCX visual | Suplemento [run-02/tests.log](run-02/tests.log): 23 tests, tres subtests fallidos en 8,296 s, exit 1; 14/15 controles. En las tres entradas se recibió `blocked` antes de lo esperado (`pending_consent`). La fixture de texto no configuraba destino/credencial Jev que exige el flujo documental antes del consentimiento. No se verificó de nuevo esa hipótesis ni se declara cancelación documental nueva satisfactoria. |
| Corpus congelado | 12/12 expectativas satisfechas por extracción nueva; [resultado](run-02/extraction-results.json). No mide Office nativo, OCR, calidad de proveedor o comprensión. |
| Documento inglés | [Texto adicional](english-contract.txt), [expectativas previas](english-expectations.json), [extracción](run-02/english-extraction.json): seis líneas, `complete`, sin avisos, localizador `lines:1-6`. No se añadió al corpus aprobado ni se envió a un modelo. |
| Integridad histórica | Los 49 archivos indexados del informe documental y los 24 del seguimiento de UI coinciden con sus hashes y tamaños. Coinciden también los hashes de los 67 logs indexados de operaciones10. |
| Consentimiento histórico | El mismo request, archivo y mensaje conserva cero llamadas antes de reconfirmar; después, una respuesta y ocho llamadas sintéticas, dos de generación. La espera de 316,599294 s es evidencia anterior. |
| Incertidumbre y recuperación históricas | La reconstrucción UI y el recibo posterior a una terminación real anterior conservan generación `started`, coste `null` y total ausente. Inventarios de origen/restauración/reversión coinciden en 27 tablas y dos medios. No se repitió la restauración. |

[Controles aprobados](run-01/checks.json), [suplemento incompleto](run-02/checks.json), [procedencia de entradas](run-02/input-provenance.json), [comandos](commands.json) y [hashes de este paquete](evidence-sha256.json). `run-01` conserva la primera ejecución de 22 tests; `run-02` intentó añadir la cancelación documental en las tres entradas y mantiene su fallo. Los archivos `.executed.py` conservan cada harness realmente ejecutado. La causa del suplemento se acota por lectura del código fijo: `semantic = ... or document is not None` añade `jev` a los destinos antes de `coverage_consent`. No se cambió el producto, el corpus ni las expectativas para obtener un pase.

Las pruebas sustituyen `regulai.local_settings` por un módulo vacío antes de inicializar Django; solo usan ajustes sintéticos de test y una base en memoria. El guard de sockets y de transporte HTTP real registró cero intentos. Los mocks existentes responden dentro del proceso. El extractor abre subprocesos locales de parsing; no llama a proveedores. Las pruebas JavaScript usan Node con un DOM mínimo offline, no Chromium. Las fechas de 2027 que aparecen durante la prueba de token son consecuencia de su reloj simulado, no fechas de una sesión ni duración humana.

## Lectura simulada y límites

No se reprodujo un P0 en estos controles acotados. Las capturas previas muestran etiquetas inglesas junto a avisos españoles y un recibo móvil largo con scroll interno: se registran dos riesgos de comprensión P2, sin atribuir confusión observada a una persona. La frase de caducidad en presente de la evidencia antigua ya aparece en pasado en el seguimiento: no se reporta como defecto vigente. El borrador de `piloto-controlado.md` identificaba `d63731a` en la primera lectura, mientras el coordinador había comunicado revisiones posteriores; es un desfase documental comunicado a raíz, no un hallazgo UI.

El resultado es **revisión simulada completa, 22 controles de test aprobados y un suplemento de cancelación documental incompleto**, no "dos participantes superaron el piloto". No se rellenaron valoraciones del banco humano, referencias reservadas, comentarios literales ni tiempos de participantes. No se leyó o cambió el ledger del ensayo vivo, no se usaron claves del usuario, no se inició servidor y no se publicaron archivos. No hay commit propio: la asignación excluía el índice Git; el commit revisado es el indicado arriba.

Siguen sin medirse: descubrimiento sin ayuda, esfuerzo cognitivo, lectura inglesa por una persona, accesibilidad con tecnología de apoyo o teléfono físico, eficacia real del enmascarado, calidad semántica y ahorro. Una futura sesión humana requiere sus observaciones reales; esta simulación no sustituye ese registro.

## Repetición local

Conservar esta carpeta y su `snapshot` aislado. El harness actual conserva la prueba suplementaria fallida; repetirlo no implica que ese test esté arreglado. Elegir un nombre nuevo, pues el harness no sobrescribe resultados:

```powershell
rtk proxy .venv/Scripts/python.exe -B .claude/pilot-personas/p02/run_checks.py --output-name run-03
```

El ZIP fue producido con `git archive` del commit fijo para `regulai` y el corpus documental. `Expand-Archive` falló al cargar su módulo de PowerShell; se conserva ese fallo en comandos. La extracción posterior con el módulo estándar `zipfile` terminó exit 0. Las lecturas exploratorias de rutas inexistentes y el `git diff --check` sobre una carpeta ignorada no se cuentan como puertas del producto.
