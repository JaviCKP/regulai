# Recorrido visual local de las correcciones

3 de octubre de 2026. Demo offline real de Django, con proveedores y jueces sintéticos y red saliente del servidor bloqueada por `run_demo`. Worktree nuevo `ui-review`, base SQLite dedicada creada para este recorrido; no se modificó ninguna base del usuario. Inicio sobre `eb8fde7`; interfaz actualizada a `9549e74`; exportación y recarga verificadas después de `f778336`. No prueba calidad de proveedores reales.

- DOCX programático con dos párrafos y una imagen de 2×2: `complete_text_only`, aviso de una imagen no analizada/no enviada, confirmación y cero llamadas antes de aceptarla. [Captura](coverage-consent.jpg).
- Confirmación de la misma petición y archivo: «10 euros [1]», evidencia literal «cuesta 10 euros.» en `word/document.xml/paragraph:2`. Dos generaciones y cinco llamadas simuladas; ruta final `synthetic-strong-v1`, verificación pasada, coste simulado estimado 0,00102000 USD. Los desplegables de evidencia y cita se abrieron con Enter. [Captura](document-evidence.jpg).
- Tras recargar se conservan respuesta, evidencia y ficha. El recorrido descubrió que el filtro de exportación omitía los límites del historial; dos regresiones HTTP reprodujeron el problema y `f778336` lo corrige. Se verificaron después los valores 32768 bytes y 20 turnos. [Ficha recargada](receipt-after-reload.jpg).
- Vista estrecha solicitada al navegador de prueba: 390×844, ancho de documento observado 375 píxeles y scrollWidth 375, sin desbordamiento horizontal. La dimensión temporal se restauró. [Captura](mobile-receipt.jpg).
- Mensaje con marcador sintético `SYNTHETIC_SECRET_DEMO`: bloqueo local, cero llamadas y coste cero. [Captura](blocked.jpg).

El navegador no registró errores ni advertencias en el recorrido documental. Se cerró la pestaña creada para la prueba y se detuvieron ambos servidores propios (demo Django y maqueta de interfaz). No se cerraron servidores ni pestañas ajenos.

La maqueta previa comprobó etiqueta «No verificado» y renovación de consentimiento, pero no ejecutaba backend; sus capturas se conservan solo como evidencia auxiliar externa y no acreditan el flujo HTTP. Las regresiones automatizadas cubren advisory y caducidad real de tokens.

El DOCX de este recorrido fue generado con python-docx, no guardado por Word o LibreOffice. Siguen pendientes los ejemplos sintéticos creados con aplicaciones de escritorio reales y los ensayos con otras personas.
