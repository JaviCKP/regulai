# 91 — El saludo del agente no es un archivo

Status: completada y aplicada localmente el 17 de octubre de 2026.
Blocked by: ninguno. Corrección posterior a [90](90-demo-privacidad-cuenta-local.md).

Aceptación: «hola» recorre las tres entradas del chat con privacidad y catálogo
de skills; el texto se protege antes del proveedor, los binarios siguen bloqueados
y un fallo de respuesta no anuncia una entrega de archivo. Sin nuevas llamadas
de generación pagada ni cambios en cuenta, claves, esquema o datos existentes.

El intento `2290394c-4a68-4c8f-8efd-4ead9190027b`, conversación 9, no tenía archivo
ni entrega requerida. Falló antes del proveedor: el control de privacidad rechazaba
cualquier lista de contenido, incluidos los cuatro bloques `type: text` del SDK.
Se reprodujo antes de corregirlo: seis fallos en tres pruebas de regresión.

Ahora se admiten únicamente bloques con `type` y `text` válidos; los demás se
rechazan antes de resolver imágenes. La protección se conserva en generación,
compactación y replay. React y la interfaz heredada distinguen el fallo de una
respuesta del fallo de una entrega. Los nuevos fallos sin archivos muestran
«La respuesta se ha interrumpido». El intento histórico permanece fallido.

Verificación observada:

- SDK real de la imagen instalada, sin red, secretos ni sandbox nuevo: un saludo
  completado contra transporte simulado; cuatro bloques de texto confirmados.
- 29 pruebas locales de privacidad/frontera/inferencia; después se amplió el
  caso de las tres entradas con catálogo instalado y volvió a pasar.
- Imagen candidata: **37 pruebas, OK, 50,930 s**, en PostgreSQL de prueba separado.
  Incluyen catálogo automático, tres entradas HTTP, frontera HTTP del proveedor,
  protección del contenido, replay, skills y visión sin privacidad opcional.
- React: typecheck, **49 pruebas** y build correctos; advertencia de tamaño del
  bundle ya existente. No nueva comprobación visual por el rechazo previo de URL.
- La ampliación inicial a 68 pruebas produjo cinco errores: checkpoint de skills,
  dos resultados de herramientas y dos archivos PDF de evidencia ausentes.
  Los **mismos cinco errores** se reprodujeron en la imagen original, con las
  mismas trazas y ajustes. No se atribuyen al parche ni se presentan como superados.

Se aplicó la imagen `sha256:b36f6f4db48e24038dfbb9870bb6e3c10033c68029208226cee129681f3c0763`
a la web local, conservando worker, montajes privados y configuración. Huellas
de datos iguales antes/después; web y worker activos con cero reinicios automáticos.
Los hashes instalados coinciden con el código y manifest preparados. Los túneles
8800/8893 siguen escuchando en loopback. El PostgreSQL temporal de pruebas locales
se detuvo conservando su directorio.

Prueba del usuario: recargar [el chat](http://127.0.0.1:8893/chat/9/) y enviar de
nuevo «hola». No se reintentó automáticamente ni se fabricó una respuesta real.

Evidencia: [fallo original](../../../output/privacy-20261017/greeting-before.json),
[petición del SDK](../../../output/privacy-20261017/greeting-sdk.json),
[validación](../../../output/privacy-20261017/greeting-validate.json),
[aplicación](../../../output/privacy-20261017/greeting-apply.json),
[servicios y hashes](../../../output/privacy-20261017/greeting-finish.json).

Reversión compatible, sin migraciones: contenedor anterior
`regulai-v2-web-before-privacy-greeting-20261017-a1`. Configuración, huellas y logs
privados se conservan en `/opt/regulai/updates/privacy-greeting-20261017-a1`.
La imagen anterior recuperaría también este fallo; nunca reintentar ejecuciones
con efectos inciertos. No confundir esta reversión con retirar la privacidad de 90.
