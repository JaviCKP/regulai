# Chat de regulAI en React — informe de entrega (17-10-2026)

Rama `claude/regulai-chat-redesign-cc9805`, sobre la instantánea `2bfb930` del trabajo
P0/P1 del checkout principal. Sin push, publicación, despliegue, cambios de datos reales
ni llamadas de pago. Encargo: [prompt de renovación](../chat-ui-research-20261017/prompt.md)
(está en el checkout principal); estados: [inventario](../../docs/plan-blackhat/chat-react-estados.md);
tareas [79](../../docs/plan-blackhat/tareas/79-chat-react-base.md),
[80](../../docs/plan-blackhat/tareas/80-chat-react-recorridos.md),
[81](../../docs/plan-blackhat/tareas/81-chat-react-verificacion.md) y
[82](../../docs/plan-blackhat/tareas/82-chat-react-retirada-legado.md).

## Qué cambia

Para quien usa el chat:

- La conversación y el compositor ocupan el centro; el estado vacío es una línea y el
  compositor, sin sugerencias redundantes ni etiquetas técnicas fijas.
- Compositor de una sola superficie: escribir, adjuntar, `/` para skills y
  enviar/detener. Conserva borrador, Enter/Mayús+Enter, IME y Escape.
- La respuesta crece donde está la persona: sigue el final mientras está abajo; si sube
  a leer, no la arrastra y aparece «Ir al final». Sólo se pinta lo que llega por el
  transporte, una vez por fotograma; el historial no se reanima.
- Adjuntos con estado visible (elegido y comprobado, «Enviando», «Recibido»,
  «Rechazado», «No enviado»), comprobación local de tipo y tamaño y actividad
  indeterminada, sin porcentajes.
- Actividad del agente tipo Trace: paso actual con icono y detalle plegable con fases
  observables del servidor; aviso pequeño de skill activada, sin robar el foco.
- Entregables en tarjeta compacta (nombre, tipo, tamaño si existe) y visor aislado:
  lateral desde 1100 px, modal por debajo, `iframe` sin permisos.
- Errores cortos con acción (reintentar con la misma identidad, comprobar estado,
  volver a enviar) y detalle bajo demanda; recibos de uso y coste sólo bajo demanda.
- Áreas táctiles de 40–44 px, foco visible, Escape y retorno de foco, anuncios
  accesibles sin leer cada token y movimiento reducido sin pérdida de información.

Técnico:

- Isla React 19 + TypeScript + Vite servida por Django desde `regulai/static/chat-app/`
  (manifest con JS, CSS y chunks importados; visor, selectores, detalles y Motion se
  cargan al primer uso). Django sigue siendo la autoridad de sesiones, CSRF, permisos,
  archivos, ejecución, estado y dinero.
- Bootstrap JSON con campos explícitos (`chat_bootstrap.py`); transporte, estado y
  presentación separados sobre los endpoints actuales (POST, reenganche por `seq`,
  cancelación; snapshot + EventSource con cursor para el agente).
- ChatMarkdown único: port a TypeScript del renderer actual. Streamdown no se adoptó:
  falla 1 de 7 comprobaciones del contrato y añade 142 KB gzip
  ([evidencia](streamdown/)).
- Reversión local: `REGULAI_CHAT_FRONTEND=legacy` sirve el chat anterior; un solo
  frontend por página. Si falta el build, Django vuelve al anterior y lo registra.
- CI: Node desde `.node-version`, `npm ci`, typecheck, pruebas, build y comprobación de
  que el build commiteado es exactamente el de las fuentes.

## Cómo aplicarlo

En `entrega/` (en el worktree) hay dos parches contra `2bfb930` y el script que los
genera:

- `chat-react-codigo.patch`: código, pruebas, documentación y build.
- `chat-react-evidencias.patch`: capturas, grabación y medidas (`output/`).
- `make_delivery.py`: los vuelve a generar desde la rama y los comprueba con
  `git apply --check` contra el checkout principal.

El checkout principal tiene trabajo en curso fuera del índice y sigue cambiando
(durante la entrega cambió `docs/plan-blackhat/README.md`): conviene comprobar justo
antes de aplicar. Algunos archivos tienen allí CRLF en la copia de trabajo y LF en el
repositorio (hoy, `.github/workflows/ci.yml` y `regulai/front/test_review_regressions.py`);
el parche copia línea a línea esos finales de línea, así que basta un `git apply`
normal (no `--3way`: los cambios del checkout no están en el índice). Si la
comprobación falla, `python entrega/make_delivery.py entrega` lo regenera desde el
worktree. Para volver al chat anterior sin desinstalar nada:
`REGULAI_CHAT_FRONTEND=legacy`.

## Pruebas ejecutadas

Sobre el código final (`8d0f526`):

| Prueba | Resultado |
| --- | --- |
| Typecheck y pruebas unitarias de la isla (Vitest) | 47/47 |
| Recorridos en Chromium contra el build servido por Django (laboratorio) | 10/10 |
| Suite Django completa, 88 módulos, PostgreSQL desechable | Sin fallos atribuibles a la isla; 5 módulos fallan igual en la base `2bfb930` y uno es intermitente también en la base (ver límites) |
| Copia limpia (`git archive 2bfb930` + parche): árbol, `npm ci`, verify y build | Byte a byte igual a la rama; build idéntico al commiteado |
| Pruebas Django del chat y del instalador en esa copia | 150/151 (el fallo es el icono preexistente) y 4/4 |
| `git apply --check` contra el checkout principal | Código y evidencias aplican |

Los recorridos cubren streaming y lectura hacia arriba, copiar, detener, recarga sin
reenvío, adjunto comprobado y rechazado, selector de skills, actividad con aviso de
skill y visor aislado, consentimiento con su token, teclado y movimiento reducido.

## Capturas y grabación

[capturas-fixture/](capturas-fixture/README.md): 65 capturas de 22 estados a 1440, 768 y
360 px y `video/recorrido-1440.webm`. Todo es del laboratorio (datos sintéticos,
proveedor simulado): no muestra la latencia, la calidad ni el coste de un proveedor real.

## Mediciones

Chat anterior frente a la isla, mismo laboratorio, corpus y máquina, CPU ×4, 5 pasadas
([datos](medidas/medidas-8d0f526.json), [script](../../frontend/chat/e2e/measure.mjs)):

| | Chat anterior | Isla React |
| --- | --- | --- |
| Peticiones al cargar | 19 | 10 |
| Transferido (gzip) | 236–238 KB | 264–266 KB (JS +98, CSS −65) |
| Primer contenido pintado (FCP) | 340–404 ms | 496–624 ms |
| Bloqueo total (tareas largas) | 0–50 ms | 165–215 ms |
| Evento → DOM, chat (mediana / p95) | 9,5 / 17,1 ms | 9,1 / 17,1 ms |
| Evento → DOM, agente (mediana / p95) | 9,7 / 23,5 ms | 11,7 / 25,2 ms |

La primera carga empeora: la isla pinta tras ejecutar su JS y la página no trae HTML
inicial. El streaming queda igual; en el agente la isla agrupa el texto en un pintado
por fotograma. Son costes del cliente en esta máquina, no latencia de un proveedor.

## Revisión independiente

Dos revisores de solo lectura (contratos y acabado visual), cada uno con un
verificador escéptico ([detalle](revision-independiente.md)). Contratos: 6 defectos
confirmados y corregidos; dos eran regresiones frente al chat anterior: un envío sin
confirmar podía reenviarse con otra identidad, y una página de error HTML dejaba el
turno sin acciones. Visual: 7 hallazgos confirmados y corregidos (tarjeta de
entregable, selector de skills en móvil, cifras en tablas, corte bajo la cabecera,
contraste del aviso de skill, alineación del lateral, borde del botón copiar); 3
refutados y 2 inciertos quedan como decisiones documentadas.

## Dependencias y licencias

Ver [NOTICE](../../frontend/chat/NOTICE.md); cada build regenera
`regulai/static/chat-app/THIRD-PARTY-NOTICES.txt` con el texto de licencia de lo que
empaqueta. Se distribuyen React 19.3.1 (MIT), Base UI 1.9.0 (MIT), Floating UI (MIT),
Motion 14.3.0 (MIT), Lucide 1.58.0 (ISC), @shadcn/react 0.3.1 y cn 0.5.0 (MIT), clsx
(MIT), class-variance-authority 0.7.1 (Apache-2.0) y el CSS de Tailwind 4.3.3 y
tw-animate-css (MIT). Los componentes de `src/components/ui` proceden del CLI de shadcn
4.22 (MIT). Ninguna carga remota de fuentes, imágenes, scripts ni telemetría.

## Commits

Sobre `2bfb930`, en orden: la isla (bootstrap, manifest, transporte y primera UI);
finales de línea de `settings.py`; pruebas de SSE, adaptadores, contenido y
compositor; recorridos en navegador; pulido desde capturas; carga diferida; pruebas
de contratos, CI y avisos; build; avisos en orden estable; spinner sin brillo; áreas
táctiles; pruebas de página contra la isla; evidencias; correcciones de la revisión
de contratos (`3a001af`) y visual (`8d0f526`); y la documentación y evidencias finales.
`git log 2bfb930..HEAD` en la rama da la lista exacta.

## Limitaciones y pendiente

- **Validación con personas: no hecha.** Ninguna persona ha usado aún la interfaz; no
  se afirma que sea intuitiva. Es la condición para retirar el chat anterior
  ([tarea 82](../../docs/plan-blackhat/tareas/82-chat-react-retirada-legado.md)).
- **Primera carga más lenta** (tabla de mediciones). Mitigación posible, no hecha: un
  esqueleto estático en `chat/app.html` para pintar antes del JS.
- **Fallos previos, no causados por este trabajo** (fallan igual en `2bfb930`):
  `test_agent_inference`, `test_agent_professional`, `test_agent_runtime_p0`,
  `test_agent_transparency` y el icono `book-bookmark-line-duotone` de
  `test_frontend_resources`. `test_agent_preflight_inputs` da a veces un 409
  `idempotency_conflict` en las tres entradas HTTP, también en la base (1 de 8 aquí,
  1 de 12 allí).
- **Laboratorio:** proveedor simulado, sin verificador semántico (bloquea documentos) y
  eventos de agente publicados por un conductor de fixture; no mide un proveedor real.
- **Sin revisar:** tema oscuro y teclado virtual de un teléfono real.
- **Streamdown no adoptado** (motivos en la tarea 80); el renderer actual queda
  encapsulado en ChatMarkdown.
