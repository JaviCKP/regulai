# 54. Escritura externa aprobada y cierre del piloto

Estado: pendiente de implementación.
Blocked by: [53](53-agente-mcp-lectura.md).
Especificación: [guía de ejecución](../../implementacion-agente-regulay-prompts.md), recuperación/aprobación del [plan](../../plan-capacidades-agenticas-regulay-2026-10-07.md) y [corpus documental](../../investigacion-prompts-skills-documentales-2026-10-07.md).

## Prompt de ejecución

```text
Implementa exclusivamente la tarea 54. Lee AGENTS.md, la guía de ejecución y la
evidencia de 48–53. No confundas un test simulado con la activación de un piloto.

Añade una sola escritura al conector documental de la 53: guardar/exportar una
revisión verificada en una carpeta autorizada. No añadas correo, publicación
pública, borrados remotos ni varios tipos de acción para demostrar lo mismo.

Usa la interrupción/checkpoint oficial de Deep Agents para presentar una propuesta
concreta antes del efecto: cuenta, carpeta, nombre, revisión, contenido/hash y
si crea o sustituye un archivo. La aprobación durable pertenece a Regulay y se
vincula a esos argumentos, usuario, empresa, ejecución, permisos y caducidad.
Revalida al ejecutar. Cambiar el destino o los bytes invalida la aprobación.
Las lecturas y cálculos locales continúan sin aprobación adicional.

Registra intención antes del efecto y resultado después. Usa una clave idempotente
del destino o reconciliación. Si un timeout deja incierto si se escribió, no
repitas a ciegas. Reanudar dos veces una aprobación no puede duplicar el archivo.
Un checkpoint conserva estado, no permisos. No construyas un motor de workflows.

Completa los casos operativos sobre el backend real: caída/reinicio del ejecutor,
pérdida de concesión, cancelación, reconexión SSE, pool agotado, retención/borrado
y dos usuarios/empresas. Comprueba que un sandbox liberado no reaparece con datos
previos, que la revocación corta los pasos siguientes y que desactivar el modo
impide ejecuciones nuevas sin borrar el historial ni descargas aún autorizadas.

Ejecuta el corpus local de 16 tareas y registra fallos, reparaciones, tiempos,
integridad y previews de los cuatro formatos. Prepara la evaluación generativa
con entradas/configuración repetibles. Si no existe autorización específica para
modelos de pago, no la ejecutes y deja esa validación pendiente: fixtures y modelos
simulados no prueban que la calidad iguale a Claude.

Prueba la escritura remota mediante transporte simulado; no escribas en una
cuenta real ni publiques resultados sin autorización. Ejecuta las regresiones
finales de las tres entradas, autorización de red, migraciones y dinero. No
vuelvas a introducir topes de generación retirados por la tarea 44 para aprobar
un test de presupuesto.

Deja un procedimiento breve de arranque, parada, recuperación y reversión con las
configuraciones necesarias. Resume evidencia, limitaciones y condiciones aún
pendientes. Mantén desactivado lo no validado. No hagas push ni despliegues.
```

## Aceptación

- Una escritura concreta se revisa y aprueba antes del efecto; argumentos/versiones cambiados invalidan la aprobación.
- Reinicios, reintentos y doble reanudación no duplican efectos; resultados inciertos se reconcilian.
- Aislamiento, pool, cancelación, retención y revocación probados en el backend real.
- Evidencia por formato y métricas propias, distinguiendo validación de runtime y calidad del modelo.
- Reversión y operación documentadas; ninguna cuenta real activada con una prueba pendiente o autorización supuesta.

## Verificación observada

Pendiente. No hay escrituras externas, evaluación con modelos de pago ni piloto del agente activados.
