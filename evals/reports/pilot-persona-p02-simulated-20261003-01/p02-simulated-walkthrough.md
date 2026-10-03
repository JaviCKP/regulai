# Recorrido P02: H1/H2 y controles de privacidad e incertidumbre

**Todo el comportamiento del perfil en este documento es simulado por un agente.** "Acción nueva" nombra solo trabajo realmente ejecutado en esta tarea; "evidencia previa" conserva su procedencia anterior. Ningún paso registra observación, opinión, ayuda requerida o tiempo de un participante humano. La fecha de elaboración es 3 de octubre de 2026, no la fecha de una sesión humana.

Las expectativas de H1/H2 proceden del [protocolo existente](../../../docs/plan-blackhat/documentos-y-ensayos-piloto.md); las documentales, de [expectations.json](../../../evals/documents/pilot-20261003/expectations.json); los umbrales P0/P1/P2, de [piloto-controlado](../../../docs/plan-blackhat/piloto-controlado.md). Los tests nuevos corresponden al commit `535eb9d8421006ea8476ea511427a7dcda9cee3b`: [22 tests aprobados](run-01/tests.log) y [suplemento conservado con tres subtests fallidos](run-02/tests.log). Los recibos históricos pertenecen al usuario sintético `community-demo`; nunca se presentan como recibos de Beta o acciones de P02.

## P02-PREP — alcance, revisión e identidad

- **Objetivo/entrada:** preparar el rol Admin de Beta y reconocer que la demo usa corpus y destinos sintéticos. Expectativa: preparación H1/H2 y entorno del piloto; el administrador no es operador global.
- **Evidencia previa examinada:** protocolos, manifiesto del corpus, informes documental/UI/operaciones10. La primera lectura del borrador de piloto citaba `d63731a`; el coordinador comunicó un candidato posterior.
- **Acción nueva real:** archivo Git y copia fija de `535eb9d`; validación de hashes y test del rol Admin sin flags globales. No se inició sesión UI ni cronómetro humano.
- **Observable:** 171 fuentes idénticas antes/después; ajustes privados no importados; pruebas solo en memoria. La carpeta incluye procedencia por hash.
- **Reacción hipotética, simulada:** P02 buscaría la revisión y comprobaría que ser administrador de Beta no le da permiso para leer Alpha.
- **Duda/incidencia y severidad:** P2 documental: versiones distintas entre borrador, evidencia histórica y candidato comunicado pueden inducir a trasladar conclusiones. Se mantienen separadas; la actualización global corresponde al coordinador. No es un fallo de aislamiento.

## H1-01 — saludo y significado de la ficha

- **Objetivo/entrada:** `Devuelve el saludo Hola.` en conversación nueva; distinguir destino, coste y verificaciones. Expectativa: H1.1.
- **Evidencia previa examinada:** informe de demo y banner visible en las capturas de conversación; se declara transporte, datos y jueces sintéticos.
- **Acción nueva real:** `ChatFlowTests.test_authorized_request_is_sent_once_and_duplicate_replays` envía una pregunta sintética mediante TestClient y usa respuesta `Hola` prefijada. No se escribió el texto del guion en un navegador.
- **Observable:** primer envío completado; repetición del mismo identificador conserva la respuesta y una generación. Esto comprueba flujo, no competencia lingüística.
- **Reacción hipotética, simulada:** P02 interpretaría el saludo como prueba de conexión del flujo offline y consultaría el destino efectivo antes de asumir que se puede usar información de Beta.
- **Duda/incidencia y severidad:** P2 de comprensión posible: `Verification: passed` y `quality` podrían leerse como garantía. No se observó una persona haciéndolo; se preserva la explicación de verificación limitada y juicio sintético.

## H1-02 — bloqueo obligatorio

- **Objetivo/entrada:** `SYNTHETIC_SECRET_DEMO`; localizar bloqueo y cero llamadas, sin intentar levantarlo por confirmación. Expectativa: H1.2 y P0 de salida prohibida.
- **Evidencia previa examinada:** guion offline y prueba operacional anterior de bloqueo local.
- **Acción nueva real:** tests del flujo con marcador `SYNTHETIC_SECRET`, regla inválida y destinos no autorizados. La regla inválida recorre las tres entradas HTTP; el marcador de la prueba no se confunde con la escritura literal en UI.
- **Observable:** bloqueo/indisponibilidad cerrados; generador no invocado. El texto bloqueado y el mensaje no vinculado se excluyen del contexto posterior.
- **Reacción hipotética, simulada:** P02 trataría el bloqueo como una decisión de política, sin buscar un botón para anularlo.
- **Duda/incidencia y severidad:** sin incumplimiento observado en las pruebas; una salida pese al bloqueo sería P0 según protocolo. La eficacia general del detector no queda validada por un marcador conocido.

## H1-03 — omisión visual y cancelación del documento

- **Objetivo/entrada:** `text-and-image.docx`, pregunta del precio, inspeccionar la imagen omitida y cancelar. Expectativa: H1.3 y caso `word-visual`.
- **Evidencia previa examinada:** `receipt-before-consent.json` conserva `complete_text_only`, `images_unread` y párrafo 3; la cancelación histórica de `receipt-cancelled.json` pertenece a otro request con marcador de consentimiento.
- **Acción nueva real:** intento de test adicional con ese DOCX exacto en `/chat/`, `/chat/send/` y `/api/chat/send/`; extracción nueva del corpus. No se alcanzó la cancelación: los tres subtests fallan al esperar `pending_consent` y recibir `blocked`.
- **Observable:** el suplemento se conserva como incompleto. Su fixture no configuraba Jev; el código exige destino y credencial del juez documental antes de `coverage_consent`. Esta explicación por código no se volvió a ensayar. El test previo de cancelación con marcador sí pasa y el número visual 73 no está en las fuentes textuales; no se unen para afirmar cancelación documental exitosa.
- **Reacción hipotética, simulada:** P02 podría cancelar si la imagen contuviera una condición importante, en vez de aceptar un precio basado únicamente en texto.
- **Duda/incidencia y severidad:** P1 de cobertura del ensayo suplementario: esta combinación no terminó, por preparación insuficiente del harness inferida del código; no es un defecto de producto confirmado. P2 posible de comprensión: `3 / 3` no equivale a cobertura visual total. Comprensión humana no medida.

## H1-04 — confirmación, dos intentos y cita

- **Objetivo/entrada:** volver a adjuntar el DOCX, confirmar y abrir la cita del precio. Expectativa: H1.4 y `word-visual`.
- **Evidencia previa examinada:** `receipt-postfix-completed.json`, captura `07-keyboard-citation.png` y estado completado tras renovación. Los dos intentos de generación están separados, el primero rechazado y el segundo con verificación sintética superada.
- **Acción nueva real:** lectura del JSON y de la captura; comprobación automática de ocho llamadas/dos generaciones, estados `failed`/`passed` y omisión retenida; tests de prueba de consentimiento firmada. No se pulsó Confirm ni Enter en UI.
- **Observable:** precio histórico `10 euros [1]`; evidencia en `word/document.xml/paragraph:2`, extracto `cuesta 10 euros.`; imagen del párrafo 3 sigue sin leerse. Las ocho llamadas incluyen máscara, clasificación y verificación, además de dos generaciones.
- **Reacción hipotética, simulada:** P02 contrastaría el extracto y distinguiría el intento descartado de la respuesta elegida.
- **Duda/incidencia y severidad:** P2 posible: interpretar ocho llamadas como ocho respuestas o el juez prefijado como garantía. No se midió esa confusión; el resultado no autoriza afirmar calidad real.

## H1-05 — exportación y recarga

- **Objetivo/entrada:** guardar el JSON, recargar y recuperar ficha/evidencia. Expectativa: H1.5.
- **Evidencia previa examinada:** informe original, `receipt-completed.json`, captura `08-mobile-reloaded-receipt.png` y observación histórica de descarga desde el enlace.
- **Acción nueva real:** tests de endpoint de exportación y representación de conversación recargada, filtro de campos privados y permisos. No se hizo una descarga de navegador nueva.
- **Observable:** exportación de propietario con 200 y `Content-Disposition: attachment`; campos privados de la fixture excluidos; la conversación vuelve a contener enlaces de ficha/evidencia. El recibo histórico conserva destino, cobertura y dos intentos.
- **Reacción hipotética, simulada:** P02 conservaría la ficha para explicar una decisión y evitaría tratar el archivo exportado como una factura.
- **Duda/incidencia y severidad:** sin fallo observado del contrato comprobado. El exportado contiene metadatos de decisión y requiere custodia; no se comprobó cómo un humano lo comparte ni su política externa de retención.

## H1-06 — fórmula sin caché y recuperación

- **Objetivo/entrada:** pedir total de `formula-uncached.xlsx`; recuperar con `formula-cached.xlsx`. Expectativa: H1.6, `xlsx-uncached` y `xlsx-cached`.
- **Evidencia previa examinada:** expectativas redactadas antes de extracción y límites de caché OOXML inyectada.
- **Acción nueva real:** extracción de ambos archivos y test del archivo sin caché en las tres entradas HTTP.
- **Observable:** sin caché: `partial`, `formula_coverage_unknown`, bloqueo `input_unreadable` sin llamadas; la fórmula solo aparece en texto de seguridad. Con caché: `complete`, valor `C2: 10` en la fuente; no se ejecutó Excel ni se generó una respuesta con este archivo.
- **Reacción hipotética, simulada:** P02 pediría un documento con resultado verificable en lugar de considerar que el sistema recalculó la hoja.
- **Duda/incidencia y severidad:** sin fallo observado; falta una observación humana del paso de recuperación. Confundir caché inyectada con recálculo sería un problema P2 de comprensión, no un cálculo medido aquí.

## H1-07 — ficha y controles móviles

- **Objetivo/entrada:** inspeccionar a 375 px y encontrar acciones. Expectativa: H1.7.
- **Evidencia previa examinada:** capturas `browser-pending-mobile-light.png` y `browser-completed-mobile-light.png`, dimensiones registradas por el seguimiento anterior.
- **Acción nueva real:** apertura e inspección de ambas imágenes locales. No se redimensionó una ventana nueva ni se usó un teléfono.
- **Observable:** botones Confirm/Cancel separados y legibles en el estado pendiente; aviso histórico de caducidad en pasado en completado. La ficha completada tiene scroll vertical interno, y una sola captura no muestra su totalidad. El ancho de 375 px sin overflow procede de la medición anterior.
- **Reacción hipotética, simulada:** P02 podría necesitar descubrir el scroll interno antes de encontrar costes y destino más abajo.
- **Duda/incidencia y severidad:** P2 de descubrimiento posible, sustentado por longitud visible de la ficha. No se infiere ayuda requerida, duración ni conformidad WCAG completa.

## H2-01 — comenzar sin guía durante el paso

- **Objetivo/entrada:** obtener precio, fuente y decisión guardada sin instrucciones paso a paso; empezar por saludo y teclado. Expectativa: H2.1.
- **Evidencia previa examinada:** guion H2 y capturas/snapshots de una automatización de navegador anterior.
- **Acción nueva real:** revisión de etiquetas y tests del flujo; ninguna sesión limpia de navegador ni observación de descubrimiento sin ayuda.
- **Observable:** las superficies documentadas existen en evidencia anterior y el flujo HTTP se verifica de nuevo. No hay dato que permita declarar que P02 encontró la ficha por sí solo.
- **Reacción hipotética, simulada:** el perfil buscaría primero el banner offline y luego `Decision receipt`; podría asociarlo con una factura por el término inglés.
- **Duda/incidencia y severidad:** P2 de comprensión posible por mezcla de idiomas. Ayudas, aciertos espontáneos y tiempo quedan sin medir.

## H2-02 — pendiente y cancelación en otra pestaña

- **Objetivo/entrada:** dejar DOCX pendiente y cancelar `SYNTHETIC_CONSENT_CANCEL` en otra conversación. Expectativa: H2.2.
- **Evidencia previa examinada:** snapshots y JSON del seguimiento con request `88f78237-1b17-4897-8a66-ab78432bac25`, que pasó de pendiente a cancelado con cero llamadas mediante Tab/Enter.
- **Acción nueva real:** verificación de integridad de esos archivos y test aprobado de reenvío de cancelado con marcador. El suplemento documental no llegó al consentimiento, como registra H1-03. No se abrieron pestañas ni se esperaron 300 segundos.
- **Observable:** la cancelación histórica y la pendiente documental son requests distintos. Los resultados no se fusionan en una sesión humana multitarea.
- **Reacción hipotética, simulada:** P02 usaría identificadores y nombres de archivo para no creer que cancelar una pestaña cancela la otra.
- **Duda/incidencia y severidad:** P2 potencial de asociación equivocada entre conversaciones. No hay evidencia nueva de confusión ni de fallo del aislamiento entre pestañas.

## H2-03 — caducidad, renovación y segunda confirmación consciente

- **Objetivo/entrada:** confirmar después de caducar y volver a confirmar el mismo contenido/archivo. Expectativa: H2.3.
- **Evidencia previa examinada:** estados `state-postfix-pending/expired/completed.json`: espera real anterior de 316,599294 s, mismo request/SHA/mensaje y cero llamadas hasta reconfirmar.
- **Acción nueva real:** comparación de invariantes históricas y test del token con reloj simulado a +301 s. No se repitió espera por reloj real.
- **Observable:** token nuevo utilizable y mismo mensaje; tras confirmar de nuevo se permite una generación en el test. La ficha final histórica muestra el aviso en pasado; no ofrece nuevos botones de confirmación.
- **Reacción hipotética, simulada:** P02 revisaría otra vez porque la autorización temporal caducó, sin pensar que la segunda confirmación anula una prohibición.
- **Duda/incidencia y severidad:** el imperativo antiguo estaba corregido en el seguimiento y en el test nuevo; no se cuenta como P1/P2 abierto del producto. Comprensión del motivo queda sin medir.

## H2-04 — cita, exportación y vuelta a la evidencia

- **Objetivo/entrada:** usar teclado, guardar decisión y volver a localizar evidencia tras recargar. Expectativa: H2.4.
- **Evidencia previa examinada:** captura `07-keyboard-citation.png`, exports y observaciones anteriores de Tab/Enter/recarga.
- **Acción nueva real:** lectura de imagen y JSON; test de evidencia para propietario y representación de enlaces después de la carga HTTP.
- **Observable:** extracto de precio y localizador conservados; el test comprueba permisos. No se ha probado de nuevo el foco de un navegador ni la secuencia de teclas.
- **Reacción hipotética, simulada:** P02 tomaría la cita como evidencia de ese texto concreto, manteniendo fuera de la conclusión la imagen omitida.
- **Duda/incidencia y severidad:** P2 potencial si una cita se interpreta como validación de todo el contrato. No hay cita inválida marcada válida en el alcance comprobado; eso constituiría P0 según el protocolo.

## H2-05 — escaneo y cláusula final con página blanca

- **Objetivo/entrada:** subir `simulated-scan.pdf`; comprobar manualmente el control de 17 días en página 3 de `blank-and-final-clause.pdf`. Expectativa: H2.5, `pdf-scan` y `pdf-final`.
- **Evidencia previa examinada:** expectativas y hoja de contacto renderizada previamente, inspeccionada ahora. El escaneo simulado muestra `VISUAL ONLY 73`; la última página textual dice 17 días.
- **Acción nueva real:** extracción nueva y tests HTTP de bloqueo del escaneo y cita exacta de página 3 en las tres entradas.
- **Observable:** escaneo `partial` con `page_without_text`/`images_unread`, sin salida. El PDF con página blanca sigue `complete`, conserva `blank_page` informativo y cita `page:3`. La respuesta de ese test está prefijada.
- **Reacción hipotética, simulada:** P02 distinguiría una página blanca de una imagen con texto que el extractor no puede leer.
- **Duda/incidencia y severidad:** sin incumplimiento observado; no se promete OCR, fidelidad visual general ni una respuesta semántica nueva de la demo.

## H2-06 — bloqueo, móvil y regreso al guion seguro

- **Objetivo/entrada:** secreto sintético bloqueado, inspección móvil y regreso al guion sin alterar política, claves o presupuesto. Expectativa: H2.6.
- **Evidencia previa examinada:** protocolo y capturas móviles del seguimiento; informe de bloqueos de operaciones.
- **Acción nueva real:** lectura visual y tests ya identificados de fallo cerrado y destino no autorizado. No se modificaron reglas del checkout ni configuración de usuario.
- **Observable:** los tests limitan salida; la propuesta de recuperación mantiene la decisión cerrada. No hay una acción nueva de operador que reanude un caso vivo.
- **Reacción hipotética, simulada:** P02 cambiaría a una entrada sintética autorizada y dejaría la configuración al operador responsable.
- **Duda/incidencia y severidad:** sin incumplimiento en el alcance observado. Cambiar reglas para conseguir una captura favorable violaría la preparación del piloto; no se hizo ni se presenta como solución.

## P02-PRIV — otro propietario y otra empresa

- **Objetivo/entrada:** comprobar que Admin de Beta no lee conversación, ficha, cita o fichero de un compañero de Beta ni de Alpha, y no modifica catálogo global. Expectativa: aislamiento del piloto, [control de acceso](../../../regulai/front/access.py) y [contrato de fichas](../../../regulai/front/test_chat_ui.py); los bytes realmente probados son los de la revisión fija del manifiesto.
- **Evidencia previa examinada:** operaciones10 acredita aislamiento Alpha/Beta en HTTPS local; no es una navegación hecha por P02.
- **Acción nueva real:** `BetaAdministratorIsolationTests` crea usuarios/empresas sintéticos en SQLite de test, hace 12 GET y un POST global. El código del test está en [p02_checks.py](p02_checks.py).
- **Observable:** propietario propio: cuatro 200. Otro propietario de Beta: cuatro 404. Alpha: cuatro 404. Cambio global: 403, nombre del modelo intacto. Se afirma permiso de política de empresa y se niega rol de operador, staff y superusuario.
- **Reacción hipotética, simulada:** P02 entendería que administrar reglas de Beta no convierte todas las conversaciones de Beta en conversaciones propias.
- **Duda/incidencia y severidad:** ningún cruce observado en estas rutas. Cualquier 200 indebido sería P0; no se extrapola a una auditoría integral de todos los endpoints.

## P02-UNCERT — resultado y dinero desconocidos

- **Objetivo/entrada:** inspeccionar una llamada interrumpida sin atribuirle éxito, fallo definitivo ni coste cero. Expectativa: apartado de estado/dinero y parada P1 del piloto.
- **Evidencia previa examinada:** captura `09-outcome-unknown-synthetic-reconstruction.png` y su JSON son una reconstrucción UI explícita. `operations10/restart-result.json` pertenece a una terminación real anterior de Gunicorn. Se mantienen como evidencias distintas.
- **Acción nueva real:** comprobaciones JSON y test de renderizado JavaScript offline; test de timeout y repetición de request. No se desconectó un navegador ni se mató un proceso nuevo.
- **Observable:** `outcome_unknown`, `success=false` en el recibo operacional, generación `started`, coste `null`, total ausente. UI offline muestra `unknown`, no 0 ni `completed`; el mismo request no invoca otra vez al generador.
- **Reacción hipotética, simulada:** P02 detendría ese caso, anotaría request_id y pediría al operador revisar el estado antes de considerar otro envío.
- **Duda/incidencia y severidad:** no se observó incertidumbre presentada como éxito. El riesgo sería P1. Los costes 0 de API de máscara local, coste externo incierto y coste sintético estimado pertenecen a conceptos diferentes; no implican cómputo gratis ni factura real.

## P02-DUP — doble envío y repetición

- **Objetivo/entrada:** repetir un request_id, solapar dos confirmaciones y cambiar contenido con el mismo identificador. Expectativa: un envío por request_id y parada P1 ante generación duplicada.
- **Evidencia previa examinada:** resultado de operaciones10 y pruebas de solapamiento documentadas en PostgreSQL.
- **Acción nueva real:** tests de repetición secuencial y confirmaciones simultáneas en SQLite en memoria; el segundo reutiliza estado/respuesta.
- **Observable:** una llamada al generador; la confirmación solapada devuelve 202/`processing`; luego un `completed`, dos mensajes y una respuesta. Cambiar contenido con mismo id devuelve 409. No es un doble clic humano.
- **Reacción hipotética, simulada:** P02 esperaría y consultaría el mismo request, sin crear otro para borrar la incertidumbre.
- **Duda/incidencia y severidad:** no se reprodujo duplicación. P1 si ocurriera; la prueba no cubre toda topología de producción ni garantiza idempotencia si se inventa un identificador nuevo.

## P02-OPS — recuperación del operador

- **Objetivo/entrada:** explicar cómo se conserva estado coherente y se recupera una copia sintética. Expectativa: [operación y recuperación](../../../docs/plan-blackhat/operacion-y-recuperacion-piloto.md).
- **Evidencia previa examinada:** operaciones10, inventarios antes/después/reversión y hashes de comandos; prueba real anterior de PostgreSQL y claves sintéticas.
- **Acción nueva real:** comparación de los tres inventarios y 67 hashes de log. No se abrieron backups privados, no se leyeron claves, no se lanzó Docker ni una restauración nueva.
- **Observable:** 27 tablas y dos medios coinciden; los inventarios registran credenciales descifrables. El recibo de interrupción no reenvía. Es consistencia de evidencia histórica, no habilidad de un operador observada ahora.
- **Reacción hipotética, simulada:** P02 dejaría detener escrituras y restaurar base/medios/claves al operador, conservando el request incierto para revisión.
- **Duda/incidencia y severidad:** no se demuestra competencia humana ni recuperación en otra máquina. Usar solo la base sin medios/clave sería una recuperación incompleta; no se realizó ese cambio ni se atribuye una incidencia real.

## P02-EN — documento inglés, pregunta en español

- **Objetivo/entrada:** [english-contract.txt](english-contract.txt) y pregunta española sobre precio/preaviso; conservar cita literal inglesa. Expectativa creada antes de extraer: [english-expectations.json](english-expectations.json).
- **Evidencia previa examinada:** contrato de extracción TXT en las fuentes fijas; el corpus congelado de doce archivos permanece separado. No se usó el banco humano reservado.
- **Acción nueva real:** creación de un TXT sintético adicional y extracción pública; comparación exacta de texto y localizador. No se obtuvo respuesta de modelo ni una traducción validada por persona.
- **Observable:** `complete`, 6/6 líneas, sin avisos, `lines:1-6`; conserva `The contract price is 10 euros per month.` y `The required termination notice is 17 days.`. Hash de archivo `6a7897def7a11f0d2f8a6cfb67814f066ea2a0ba222fa1336f7e66d914146a53`.
- **Reacción hipotética, simulada:** P02 leería 10 euros al mes y 17 días, mantendría ambas citas en inglés y señalaría que se trata de un contrato ficticio.
- **Duda/incidencia y severidad:** sin fallo de extracción; comprensión bilingüe sin medir. Confundir la ausencia de avisos del TXT con validez jurídica o comercial del contenido sería una inferencia injustificada, no un hallazgo medido del producto.

## Cierre simulado

P02, como perfil ficticio, habría revisado salida permitida, omisiones, consentimiento, citas, aislamiento y estado incierto. Esta frase resume el papel simulado; **no afirma que una persona lo entendió**. Las respuestas literales, ayudas y tiempos de H1/H2 permanecen vacíos. La decisión de este trabajo es conservar las dudas P2 y el suplemento documental incompleto para revisión, y dar por terminada la revisión simulada, con 22 tests aprobados y los tres subtests fallidos posteriores documentados; no cerrar participación humana ni calibración semántica.
