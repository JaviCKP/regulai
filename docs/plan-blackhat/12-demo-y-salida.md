# 12. Una demo breve, verificable y preparada para fallos

**Estado:** pendiente. **Prioridad:** P1. **Depende de:** 01–09 y [11](11-evaluacion-reproducible.md); simulador opcional. **Resultado:** presentar tres mejoras comprensibles, con evidencias reales y una recuperación ensayada.

## Guion propuesto: unos cinco minutos

| Escena | Qué hacer | Qué debe quedar claro |
| --- | --- | --- |
| 1. Elegir bien | Enviar una tarea sencilla y abrir la ficha de decisión | Se eligió un modelo autorizado que cumple la tarea; el coste mostrado procede de la ejecución |
| 2. Proteger datos | Adjuntar un documento sintético con una credencial reconocible por una regla local | Se bloqueó antes de salir a Jev y al generador; mostrar el motivo y el registro de llamadas |
| 3. Comprobar la respuesta | Preguntar sobre un documento con una condición importante y abrir sus citas | Si el primer resultado falla, se registra y se verifica el segundo; las fuentes se pueden abrir |

La escena 3 no puede depender de que un proveedor cometa exactamente el error esperado en directo. Preparar un modo de demostración con respuesta prefijada exclusivamente en una instalación aislada, rotulado **“fallo simulado para demostrar el control”**. Complementarlo con una captura de evaluación real identificada por fecha y configuración. No presentar un resultado prefijado como una llamada recién hecha.

Si sobra tiempo, enseñar el simulador del plan 10 con un falso positivo y su corrección. La narración cabe en una frase: “regulAI decide qué puede salir, elige un modelo adecuado y muestra qué ha comprobado de la respuesta”.

## Preparación y ensayo

1. **Congelar una revisión candidata.** Anotar commit, dependencias, modelos, políticas, rúbricas y dataset. Crear una empresa y usuarios de demo, credenciales de prueba y presupuesto acotado. Documentos completamente sintéticos.
2. **Comprobar las tres entradas.** Suite de seguridad y compatibilidad verde; prueba visual del chat, confirmación y evidencias; exportación de ficha sin información privada. Verificar descargas y mensajes de error que pueda ver el público.
3. **Ensayar fallos reales de operación.** Caída de Jev, 429 del generador, OCR ausente, documento demasiado grande, doble clic y pérdida de respuesta HTTP. La aplicación muestra el estado conocido y no se salta controles para continuar la demo.
4. **Preparar reproducción offline.** Capturas/resultados de ejecuciones anteriores con fecha, modelos y etiqueta de reproducción. Mostrar claramente cuándo se usa esa alternativa. No construir un sistema de caché productiva para resolver un fallo de wifi de la presentación.
5. **Cronometrar y simplificar.** Hacer dos ensayos completos con otra persona. Si la explicación exige abrir código o cinco pantallas, reducirla: pregunta, decisión, evidencia. Conservar siempre el detalle accesible para quien quiera profundizar.

## Comprobación de publicación

La aplicación revisada fija Django 4.2.28. El calendario oficial sitúa el fin del soporte extendido de la rama 4.2 en abril de 2026; la revisión de este plan es posterior. Antes de una publicación o despliegue público, abrir una entrega acotada para migrar a una rama soportada y comprobar compatibilidad de Django, DRF, middleware y dependencias. No mezclar esa actualización a ciegas con la construcción del router. [Calendario oficial de Django](https://www.djangoproject.com/download/#supported-versions).

Comprobar también que la instalación documentada corresponde al repo actual: sus dos listas de dependencias difieren. El candidato de demo debe instalarse desde una fuente de dependencias definida y probarse en el entorno que se llevará a la presentación. Registrar el resultado, no solo que se ejecutó `pip install`.

Esta comprobación de publicación no sustituye a la revisión de seguridad de los cambios, ni convierte el benchmark de 50 casos en una auditoría completa del producto.

## Artefactos que acompañan la demo

- Guion breve con entradas exactas y resultado esperado de cada escena.
- Configuración de ejemplo sin secretos y pasos de arranque probados.
- Informe del plan 11 con calidad, cobertura, coste, latencia y casos fallidos.
- Una ficha real de decisión permitida para compartir y un ejemplo de bloqueo.
- Tabla clara de capacidades Community y propuesta de evolución a Vigía13, sin atribuirle funciones no verificadas.

No prometer ahorro porcentual sin medición ni “respuestas siempre correctas”. La parte convincente es enseñar una decisión, su consecuencia y la evidencia que la respalda.

## Aceptación y recuperación

- [ ] Las tres escenas funcionan desde una instalación reproducida siguiendo la guía.
- [ ] El público puede distinguir directo, simulación y reproducción anterior.
- [ ] Un fallo externo termina con explicación y sin envío prohibido.
- [ ] La cuenta de demo no accede a datos, claves ni historial de producción.
- [ ] Se conocen el coste máximo del ensayo y el gasto observado.
- [ ] La revisión desplegada cumple los criterios de seguridad, pruebas y soporte acordados.

Recuperación: volver a la última revisión segura ensayada o usar la reproducción identificada. Mantener cerrada la salida de datos si no se puede validar. Después, revocar las credenciales temporales y retirar el entorno de demo que ya no se use, conservando únicamente los artefactos aprobados para compartir.
