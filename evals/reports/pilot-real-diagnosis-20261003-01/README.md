# Diagnóstico posterior al ensayo real

[Informe de C](diagnosis.md), [auditoría del resultado vivo](audit.json), [replay tras el corrector](audit-after-diagnostic-fix.json), [rojo/verde](red-green.json) y [focal final](focal-final.json). Copias exactas: [inventario](files.json), [script](package.py). Código corregido en `972edb88c82a5220a43ffcc89316a9f9033e82f7`.

Defecto local reproducido antes de corregir: clasificación descartaba el código seguro de Jev y lo sustituía por `security_check_failed`; el texto afirmaba que no hubo envío. Timeout, HTTP503 y JSON inválido colapsaban en el mismo diagnóstico. Ahora la ficha, logs y ledger conservan `provider_error_code`, limitado a una lista cerrada. Los códigos libres, objetos y cuerpos sensibles no se exponen. La ficha describe correctamente la posible incertidumbre.

Cinco métodos nuevos verdes tras el rojo; **73 pruebas focales correctas en 33,582 s**, incluidas las tres entradas HTTP, ausencia de reenvío, sanitización del verificador y reserva incierta intacta. No se cambiaron estados públicos, destinos, modelos, umbrales, presupuestos o máximo de intentos. No se modificó la evidencia ni el ledger de la ejecución real, y no hubo nuevas llamadas o gasto.

El análisis también reproduce falsos positivos del detector en palabras comunes de desarrollo: «Cuál», «Cita» y «Contrato» reciben marcadores. Las respuestas documentales conservadas y sus citas pasan la validación local al repetirla. Estas observaciones no demuestran la causa de las puntuaciones del juez ni del último error externo. No se ajustó el detector ni se cambiaron casos o etiquetas para hacer pasar el ensayo.

**La causa concreta del fallo externo anterior sigue indeterminada.** El corrector mejora futuras evidencias y no puede recuperar un dato descartado. Se mantiene la parada y la reserva de0,003 USD. Siguiente acción: contrastar el evento Gateway de2026-10-03 15:43:21 UTC y revisar rechazos/falsos positivos antes de preparar cualquier continuación autorizada.
