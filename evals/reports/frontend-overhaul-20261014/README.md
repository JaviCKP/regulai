# Rediseño del chat y del modo agente — evidencia (2026-10-14)

Tarea: [59. Chat y agente: respuesta progresiva y actividad legible](../../../docs/plan-blackhat/tareas/59-chat-y-agente-streaming-ui.md).
Base: `fa375ad` (instantánea byte a byte de los cambios sin commitear de `codex/tasks-53-54`, tareas 55/56).
Entrega: parche sobre esa base (`entrega/frontend-overhaul.patch`), sin push ni despliegue.

Todo lo que aparece aquí se obtuvo en un laboratorio aislado: una BD SQLite sintética en
`%TEMP%`, un proveedor simulado en loopback y cuentas sintéticas. No hubo llamadas a
proveedores reales ni se tocaron cuentas, secretos o datos existentes.

## Cómo reproducir

Desde la raíz del repositorio (Python 3.12 del `.venv`; todos los comandos con `rtk`):

```
rtk proxy <python> ops/chat_ui_lab/fake_provider.py --port 8790            # en segundo plano
cd regulai
set DJANGO_SETTINGS_MODULE=regulai.ui_lab_settings
rtk proxy <python> ../ops/chat_ui_lab/seed.py --reset                       # con uvicorn parado
rtk proxy <python> -m uvicorn regulai.ui_lab_asgi:application --host 127.0.0.1 --port 8800
cd ..
set PLAYWRIGHT_MODULE=<ruta a node_modules/playwright>
rtk proxy node ops/chat_ui_lab/capture.cjs ops/chat_ui_lab/shots/baseline.json <carpeta>
rtk proxy node ops/chat_ui_lab/verify.cjs <carpeta>
```

- `REGULAI_UI_LAB_DIR` y `REGULAI_UI_LAB_PROVIDER` permiten otro directorio y otro puerto.
  En esta sesión se usaron `%TEMP%\regulai-ui-lab-57`, el proveedor en 8791 y los servidores
  en 8801 y 8802, para no tocar los procesos que dejó la sesión anterior.
- `REGULAI_UI_LAB_DRIVE=1` muestra el selector de Drive. El laboratorio no tiene concesión de
  Drive, así que la búsqueda responde «Conector no disponible».
- **Laboratorio sin generación (desde el 2026-10-14, 18:52).** `ui_lab_settings` activa
  `regulai.ui_lab_guard.RejectLabGeneration`. Todos los envíos de chat (`/chat/`,
  `/chat/<id>/`, `/chat/send/`, `/chat/<id>/send/` y `/api/chat/send/`) responden 503
  `real_generation_not_configured` sin llegar al pipeline. Leer conversaciones y el resto de
  acciones siguen funcionando.
- **Simulador retirado.** `ops/chat_ui_lab/agent_simulator.py` hacía avanzar las peticiones del
  agente con un documento de muestra fijo, no generado a partir de la petición. Se retiró
  porque podía hacerse pasar por un generador real. `main()` se niega a arrancar, y el bucle
  queda como `run_acceptance_simulator()`, solo para pruebas explícitas. Probar el agente de
  verdad necesita el worker real (`front.agents.worker`), PostgreSQL y E2B y el proveedor
  configurados y autorizados.
- **Verificación y capturas anteriores al bloqueo.** `verify.cjs` (13/13) y las capturas
  «después» se obtuvieron antes de él. Para repetir los flujos que envían mensajes hay que
  quitar el middleware de `ui_lab_settings` en una copia local.
- `EASY_ADMIN` en `seed.py` es una cuenta de administrador trivial, solo para el laboratorio.
  Tiene el agente de documentos y su propia copia de las conversaciones de demostración, que
  con el bloqueo sirven solo para consulta.
- La semilla vuelve a vincular `authorization_digest` después de añadir la entrada del
  documento, como hace `document_jobs.candidate`. Antes, confirmar la revisión visual de la
  conversación sembrada respondía 409 (`authorization_changed`).
- El proveedor elige el escenario por una palabra del último mensaje: `pausa`, `lento`,
  `caída`, `corta`, `error`, `json`, `secreto`, `correo` o `largo`. `pausa` retiene el stream
  hasta `POST /control/release`.
- El inicio de sesión está limitado a unos 5 por minuto e IP. `capture.cjs` y `verify.cjs`
  inician una sesión por usuario.

## Problemas de partida

### Observados (capturas `before/` y código de `fa375ad`)

| Problema | Evidencia |
|---|---|
| Markdown sin renderizar. Los marcadores de enmascarado se ven crudos (`[[REGULAI_EMAIL]]`) y el texto gris de las respuestas tiene poco contraste. | `before/desktop-02-markdown-answer.png` |
| Idiomas mezclados: «You», «Decision receipt», «Configured», «Supported: …», «Document evidence», «AI is thinking…». | `before/desktop-02`, `desktop-05`, `desktop-16` |
| Un recibo en cada mensaje («Decision receipt: completed») y «Document evidence» en respuestas sin documento. | `before/desktop-02-markdown-answer.png` |
| El estado del agente se repite: mensaje final, chip «Finalizado», línea de progreso y tarjeta. El panel aparece después del mensaje final, el coste parcial se ve mientras trabaja y «Usar un archivo de Google Drive» se muestra siempre, aunque `REGULAY_AGENT_MCP_ENABLED` esté desactivado. | `before/desktop-10-agent-completed.png`, `desktop-14-agent-active.png` |
| Al recargar se pierden las acciones de consentimiento: solo queda «Decision receipt: pending_consent», sin Confirmar ni Cancelar. | `before/desktop-05-pending-consent.png` |
| Al recargar se pierde la explicación del fallo: solo queda «Decision receipt: failed». | `before/desktop-07-provider-error.png` |
| El título de la barra lateral y de la cabecera muestra el secreto bloqueado (`Mi api_key = sk-proj-ABCDEF…`). | `before/desktop-04-blocked.png` |
| Lista de conversaciones estrecha, con fechas repetidas, y una cabecera cargada de botones y chips. | `before/desktop-02-markdown-answer.png` |
| Sin streaming ni parada: «AI is thinking…» y un spinner en el botón de enviar mientras el proveedor ya tenía un tercio del texto generado. | `before/desktop-16-generating.png`; en `fa375ad` el envío web solo pedía JSON |
| Modal de «reglas bloqueadas» muerto: la vista pasaba siempre `blocked = False` y `blocked_rules = []`. | `git show fa375ad:regulai/front/views.py` (`chat_view`) |

### No reproducido en esta sesión

- «Una regla de consentimiento que coincide con el propio entregable lo deja ilegible con un
  mensaje genérico»: viene de la sesión anterior. No hay captura que lo muestre y no se ha
  reproducido. El tratamiento actual del consentimiento (motivo, reglas que coinciden,
  avisos y Confirmar/Cancelar también tras recargar) está cubierto por pruebas, pero este
  caso concreto queda como hipótesis.

## Defectos encontrados y corregidos durante la verificación

Estos defectos estaban en el WIP de la sesión anterior (`e7c37b7`). Todos tienen prueba de regresión.

1. **Markdown con URL → recursión infinita.** Cualquier URL suelta o `<https://…>` volvía a
   analizarse como enlace dentro de su propia etiqueta. La respuesta no llegaba a pintarse y
   la hidratación de la página fallaba.
2. **Títulos con medio secreto.** Se enmascaraba el título guardado, que es el prefijo crudo
   de 50 caracteres, así que un valor cortado en esa frontera no se detectaba. Ejemplos:
   `…token urgente: sk-proj-ABCDE` y `…tarjeta 4111 1111 1111 11`. Se veía en la barra
   lateral, la cabecera, `<title>` y la página de borrado. Ahora se enmascara el primer
   mensaje entero (hasta 1000 caracteres), sin mostrar nunca un bloque de clave a medias, y
   después se recorta por palabras sin partir «[… protegido]». Un título explícito se conserva.
3. **Entradas JSON.** Un `PipelineStop` en la llamada de generación con `events=None`
   provocaba un `AttributeError` y se registraba como `provider_failed` en lugar de, por
   ejemplo, `deadline_exceeded`.
4. **Notificaciones de seguridad.** El carril nuevo había reducido las alertas recientes de la
   empresa a un contador (`test_backend_hardening` fallaba). Se restaura el desplegable con
   el mismo filtro por empresa.
5. **Selector de Drive.** No estaba disponible al empezar una conversación nueva en modo
   agente (en `fa375ad` sí lo estaba). Ahora aparece solo en modo Agente y con
   `REGULAY_AGENT_MCP_ENABLED`; al volver a Chat se cierra y descarta la selección.
6. **Streaming de listas y encabezados.** Un marcador abierto (`**15`) se veía en crudo.
7. **Otros:**
   - `plain()` (Copiar) solo sustituía el primer marcador.
   - Los enlaces con paréntesis (Wikipedia) se cortaban.
   - Un paso agrupado del agente mostraba la primera frase en vez de la última.
   - Un error terminal igual a la última frase del paso salía dos veces.
   - Un reenganche con 404 decía «sigue registrada».
   - Un recibo antiguo sin `calls` mostraba coste «0».
   - Había fallos de concordancia («1 superadas»).
8. **Contraste.** `#667085` daba 4,35:1 sobre el fondo de error y 4,51:1 sobre `#f2f4f7`
   (buscador y opciones del menú). Se cambia el color o el fondo.
9. **Teclado.** Con el cajón móvil abierto, el contenido de fondo queda inerte. El enlace de
   salto lleva el foco al compositor de forma explícita.

## Decisiones de diseño

- **La conversación es lo principal.** Cada turno muestra burbuja, respuesta Markdown y
  acciones mínimas (Copiar y Detalles). El recibo completo se carga solo bajo demanda y
  sigue pudiéndose exportar en JSON.
- **Estados con un único aviso.** Bloqueado, consentimiento, error, cancelado y en curso
  tienen cada uno un aviso con acciones que el servidor reconstruye al recargar
  (`chat_page.notice`). El consentimiento conserva la misma selección de proveedor y modelo
  (`decision['requested']`, `data-engine`/`data-model`).
- **Actividad del agente por petición.** Una cabecera de una línea muestra el estado, los
  pasos, las fuentes y la duración medida por el servidor. El detalle va plegado: petición
  interpretada, pasos con sus herramientas y frase del servidor solo en el último paso. Se
  abre mientras trabaja y respeta lo que abra o cierre la persona. No se inventa plan,
  porcentaje ni tiempo.
- **Entregables como tarjetas.** Miniatura, vista previa en `<dialog>`, descargas validadas,
  comprobaciones técnicas separadas de la revisión visual humana y de la autorización de
  exportación.
- **Movimiento.** Solo explica cambios de estado (bloque nuevo, paso activo, cajón,
  diálogo) y desaparece con `prefers-reduced-motion`. `forced-colors` mantiene los bordes.
- **Seguridad del renderizado.** Solo se crean nodos DOM; el arnés de pruebas hace que
  `innerHTML` lance un error. Los enlaces se limitan a http, https y mailto con
  `noopener noreferrer nofollow`, y los marcadores se convierten en chips.

## Contrato de eventos

`POST /chat/send/` y `POST /chat/<id>/send/` con `stream=1` responden `text/event-stream`. Cada
evento lleva `id: <seq>` y un `seq` creciente; solo existe en memoria del proceso y nunca se persiste.

| Evento | Datos | Uso en la página |
|---|---|---|
| `accepted` | `request_id`, `conversation_id` | Adopta la conversación (URL y lista) |
| `stage` | `stage` (`protecting`, `classifying`, `generating`, `verifying`, `waiting`), `attempt`, `model` | Línea de estado real |
| `delivery` | `mode` (`streamed`/`complete`), `reason` | Motivo de entrega completa |
| `delta` | `text`, `attempt` | Texto ya comprobado y enmascarado; siempre es prefijo de la respuesta final |
| `retract` | `reason`, `attempt` | Retira el texto mostrado (reintento, comprobación final fallida o parada) |
| `final` | `result`, `http_status` | El mismo JSON que las entradas sin streaming |

- `GET /chat/requests/<uuid>/stream/?after=<seq>` (o `Last-Event-ID`) reengancha solo al dueño
  y nunca inicia trabajo. Si no hay registro en memoria, espera el resultado guardado.
- `POST /chat/requests/<uuid>/cancel/` responde 202 si la petición estaba en curso.
- Sin `stream=1`, `/chat/send/`, `/chat/<id>/send/`, `POST /chat/<id>/` y `/api/chat/send/`
  mantienen su contrato JSON.

## Librerías evaluadas como referencia (no añadidas)

| Proyecto | Licencia y pila | Fuentes |
|---|---|---|
| AI Elements | Apache-2.0, v1.9.0; React 19 + Tailwind 4 + shadcn | https://ai-sdk.dev/elements · https://github.com/vercel/ai-elements |
| assistant-ui | MIT; runtime React | https://www.assistant-ui.com · https://github.com/assistant-ui/assistant-ui |
| Motion | MIT | https://motion.dev · https://github.com/motiondivision/motion |

Licencias y versiones son las de la evaluación previa de esta tarea; no se volvieron a
consultar en esta sesión. Se eligió CSS y WAAPI nativos y un renderizador Markdown propio que
solo crea nodos DOM. Así no entra ninguna dependencia nueva en una arquitectura Django,
plantillas y JS nativo, y el renderizado queda bajo control: sin HTML ni esquemas de URL no
permitidos.

## Pruebas ejecutadas (resultados reales)

### Pruebas de aplicación

- **Módulos del chat:**
  - `test_frontend_chat` 19;
  - `test_agent_frontend` 17;
  - `test_chat_page` 7;
  - `test_chat_streaming` 20;
  - más `test_chat_ui` y `test_pipeline`.

  Todos OK. Las de navegador cargan la plantilla real renderizada por Django y los tres
  scripts en `front/offline_browser.cjs`: DOM mínimo, temporizadores falsos y red guionizada.
- **Invariantes conservados de las pruebas antiguas:**
  - juez 0.72/0.2;
  - límites nulos;
  - aviso histórico frente a pendiente;
  - resultado desconocido sin «0»;
  - destino escalado en vivo, exportado y restaurado (en las tres entradas);
  - consentimiento con petición, archivo y token renovado;
  - lo informativo no aparece como omitido;
  - «No verificado» sin evidencia;
  - Jev frente a política local;
  - secuencia de llamadas y lectura sin modelo;
  - tarjeta con descargas únicas y comprobaciones honestas;
  - revisión visual con todas las páginas y los digests exactos;
  - error una sola vez;
  - subtotal estimado;
  - instantáneas antiguas o fallidas;
  - eventos deduplicados y `revoked`;
  - sin recibo duplicado en el agente.
- **Pruebas nuevas:**
  - Markdown seguro;
  - SSE: orden y deduplicación por `seq`, `retract`, `final` sin duplicar, reenganche
    desde `after`, parada, petición no registrada y recarga;
  - consentimiento tras recargar: el formulario exacto que envía la página lo acepta el
    servidor como la misma petición, con una sola inferencia;
  - `chat_page`;
  - `run_data`/`_events` con fechas;
  - selector de Drive;
  - envío en modo agente con revisión;
  - regresión de las entradas JSON.

### Suite completa en serie (SQLite de test)

- `fa375ad`: 675 pruebas, 46 fallos + 23 errores preexistentes, de módulos que exigen PostgreSQL.
- Rama: 700 pruebas, 23 fallos + 31 errores en el punto `a0a5078`.
- Las 51 pruebas distintas que fallan se ejecutaron sobre una copia `git archive fa375ad` y
  **fallan igual allí**: ningún fallo nuevo.
- El único fallo nuevo fuera de esos módulos (`test_backend_hardening`, notificaciones) se
  corrigió.
- Final sobre `dd7dba9`: 700 pruebas, 23 fallos + 31 errores (52 pruebas distintas).
  - 51 son las preexistentes de `fa375ad`.
  - 1 es intermitente bajo carga: `LiveStreamingTests.test_stop_closes_a_silent_provider_stream_at_once`.
    El servidor simulado tardó más de 5 s en detectar el socket cerrado, aunque la parada
    en menos de 5 s se cumplió. Pasó en `a0a5078`, 3/3 veces aislada y 20/20 con su módulo.

### Navegador real (Chromium con Playwright)

`ops/chat_ui_lab/verify.cjs` dio **13/13** (`after/verification.json`):

- texto visible antes del final (105 caracteres con el proveedor en pausa) y parada con
  retirada;
- recarga con reenganche y 1 solo envío;
- cambio de conversación durante la generación;
- móvil;
- teclado: foco inicial en el compositor, enlace de salto, menú de modelo con flechas y
  Escape, actividad con Enter, diálogo con foco dentro y retorno del foco;
- cajón móvil con foco dentro y fondo inerte;
- movimiento reducido (animaciones a 1 ms y sin pulso);
- contraste AA de 489 elementos con texto en 7 conversaciones, sin fallos;
- adjuntos: txt, formato no admitido, arrastrar y soltar, y CSV/XLSX en modo agente;
- selector de Drive solo con la opción activada;
- envío real en modo agente;
- consola sin errores. El único 403 esperado, la búsqueda de Drive sin concesión, se
  filtra de forma explícita.

## Capturas

`before/` y `after/` comparten nombres:

| Nombre | Escritorio | Móvil |
|---|---|---|
| Vacía | `desktop-01-empty` | `mobile-01-empty` |
| Markdown | `desktop-02-markdown-answer` | `mobile-02-markdown-answer` |
| Larga | `desktop-03-long-conversation` | — |
| Bloqueada | `desktop-04-blocked` | — |
| Consentimiento | `desktop-05-pending-consent` | `mobile-03-consent` |
| Truncada | `desktop-06-truncated` | — |
| Error | `desktop-07-provider-error` | — |
| Documento | `desktop-08-document-answer` | — |
| Legacy | `desktop-09-legacy` | — |
| Agente completado | `desktop-10`, `desktop-11` | `mobile-04`, `mobile-05` |
| Revisión visual | `desktop-12`, `desktop-12b` | — |
| Agente fallido | `desktop-13-agent-failed` | — |
| Agente en curso | `desktop-14-agent-active` | — |
| Profesional | `desktop-15-professional` | — |
| Generando | `desktop-16-generating` | — |
| Generado | `desktop-17-generated` | — |

Solo en `after/`:

- `desktop-18-streaming-mid`: texto parcial con el proveedor en pausa;
- `desktop-19-stopped`;
- `desktop-20-rejoined-after-reload`;
- `desktop-21-preview-keyboard`;
- `desktop-22` y `desktop-23`: movimiento reducido;
- `desktop-24-attachment-answer`;
- `desktop-25-drive-picker`;
- `desktop-26-agent-send-sqlite`;
- `mobile-06-streaming-mid`;
- `mobile-07-drawer`.

## Limitaciones

- **Entrega completa cuando el control necesita el texto entero:**
  - verificación semántica;
  - citas de documento;
  - JSON;
  - enmascarado remoto;
  - proveedores sin streaming verificado;
  - reglas YARA no decidibles por prefijo.

  La interfaz muestra la etapa real y el motivo.
- **Retención del texto en directo.** Siempre se retienen 96 caracteres (normalizados) y
  cualquier línea con una etiqueta de contacto o nombre abierta. Por eso el texto aparece
  algo después de generarse.
- **El texto parcial nunca se persiste.** Si una comprobación final falla, se retira y
  queda registrado en el recibo (`withdrawn`).
- **Registro de eventos en memoria del proceso.** Con varios workers, el reenganche desde
  otro proceso solo ve el resultado final guardado (espera hasta 60 s) y no los parciales.
  Se conserva 120 s después de terminar.
- **Detener.**
  - En streaming es inmediato porque se cierra el stream del proveedor.
  - En entrega completa se aplica cuando vuelve la llamada al proveedor.
  - En ambos casos el proveedor puede cobrar lo generado, así que el coste queda
    desconocido y nunca 0.
- **El agente no tiene un plan explícito.** No hay `write_todos`: solo se muestran los
  eventos registrados y la petición interpretada por el servidor. Las duraciones son las
  medidas por el servidor. Si duran menos de 1 s, no se muestran.
- **SSE del agente.** Necesita ASGI; sin él, se consulta cada 2,5 s.
- **Envío real en modo agente.** En SQLite y sin worker, la ejecución queda «En cola» (el
  worker exige PostgreSQL). No se probó una ejecución real del agente en esta sesión.
- **Título provisional.** Mientras llega la primera respuesta de una conversación nueva,
  la lista y la cabecera dicen «Nueva conversación». El título enmascarado aparece al
  recargar.
- **No es una certificación de accesibilidad.** Solo se comprobaron teclado, foco,
  contraste del texto, movimiento reducido y `forced-colors` por CSS. No se probaron
  lectores de pantalla.
- **Fuera de alcance, preexistente.** Al borrar una conversación, `log_action` guarda el
  título crudo, que puede contener datos sensibles.
