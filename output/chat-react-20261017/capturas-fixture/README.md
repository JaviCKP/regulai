# Capturas y grabación de la isla de chat — FIXTURE

Todo lo de esta carpeta procede del **laboratorio** (`ops/chat_ui/lab.py`):
base de datos PostgreSQL desechable con datos sintéticos, proveedor simulado
(`httpx.MockTransport` sobre el SDK oficial, ritmo fijo de 6 caracteres cada
30 ms) y eventos de agente publicados por un conductor de fixture (sin worker
ni sandbox). No muestra datos reales, ni la latencia, la calidad o el coste de
un proveedor real.

- Generado con `frontend/chat/e2e/captures.mjs` sobre el código de `8d0f526`,
  con el build servido por Django (`ASGIStaticFilesHandler`, sin servidor de
  desarrollo), Chromium de Playwright 1.62.1 y `deviceScaleFactor` 1. A 360 px se
  emula un teléfono (táctil, `isMobile`); a 768 px, pantalla táctil.
- `capturas.json`: lista de capturas, desbordes horizontales, errores de
  consola/red y peticiones a otros orígenes (ninguno en las 65 capturas). A 768 y
  360 px registra además los controles visibles de menos de 40 px; los enlaces y
  citas dentro del texto quedan exentos (WCAG 2.5.8). Esta tanda no tiene ninguno.
- `video/recorrido-1440.webm`: respuesta progresiva, lectura hacia arriba sin
  arrastre, vuelta al final, agente con skill, entrega, visor y detalle final.

| Archivo | Estado |
| --- | --- |
| 01-vacio | Conversación nueva (modo Agente disponible) |
| 02-historial-respuesta | Respuesta completada con tabla, marcador protegido, enlace, código y archivo |
| 03-historial-bloqueado | Bloqueo por regla local |
| 04-historial-consentimiento | Requiere confirmación |
| 05-historial-fallo | Error del proveedor con reenviar |
| 06-cajon-conversaciones | Cajón en 768/360 |
| 07-menu-cuenta / 08-menu-modelo | Menús |
| 09-respuesta-progresiva | Texto llegando |
| 10-leyendo-arriba | La persona sube durante el streaming: no se arrastra; botón «Ir al final» |
| 11-respuesta-larga | Respuesta completa |
| 12-adjunto-rechazado / 13-adjunto-elegido | Comprobación local del archivo |
| 14-adjunto-recibido-bloqueado | El servidor recibió el archivo; la política lo bloquea (el laboratorio no tiene verificador semántico) |
| 15-selector-skills | `/` en mensaje vacío |
| 16-agente-trabajando / 17-skill-activada | Actividad abierta mientras trabaja; aviso de skill |
| 18-actividad-cerrada | Plegada por la persona |
| 19-entregable-pendiente | Archivo listado antes de la entrega: sin acciones que el servidor rechazaría |
| 20-entregable | Entrega verificada: vista previa, descarga, editar |
| 21-visor | Lateral (1440) o modal (768/360), iframe sin permisos |
| 22-actividad-final-abierta | Pasos registrados al terminar |
