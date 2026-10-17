# 90 — Privacidad y reglas útiles en la cuenta local existente

Status: completada localmente el 17 de octubre de 2026; generación real reservada al usuario.
Blocked by: ninguno. Continúa la petición explícita posterior a [89](89-privacidad-aceptacion.md).

Aceptación: localizar la cuenta con claves sin exponerlas, conservar datos y
permisos, nombres coherentes, reglas YARA verificadas, categorías de privacidad
activables desde opciones, modelos y agente preparados, servicio local arrancado
y guía de prueba. Sin publicación, push ni llamadas nuevas de generación pagada.

Se localizó `admin`, empresa 3 «Pruebas de Javi», dentro de `regulai-v2-vm`.
La VM histórica de tarea 57 no se arrancó. DeepSeek devolvió HTTP 200 al catálogo:
`deepseek-flash` y `deepseek-v4-pro` disponibles. No se cambiaron claves,
contraseñas, modelos, precios, grants ni límites.

Se construyó una imagen COPY sobre la web instalada, manteniendo sus montajes
privados, runtime y worker. La base de comparación del código es `2bfb930`,
anterior a la isla React; incluye React y privacidad sin reemplazar cambios
instalados ajenos. La preparación inicial falló por usar un ID SHA como nombre
FROM; se corrigió con una etiqueta local fijada a ese ID. El segundo fallo fue
del harness de test (`TEST.MIRROR`), antes de ejecutar pruebas; se preservaron
los defaults de Django. Ambos diagnósticos quedaron en el directorio privado.

Backups privados antes de preparar y aplicar, clon PostgreSQL aislado y pruebas
sobre base separada. Las migraciones 0044/0045 conservaron todas las huellas de
columnas anteriores. Pasaron **61 pruebas**: reglas, tres entradas HTTP, frontera
de proveedor simulado, privacidad, replay, proyección, permisos y agente.
El tratamiento se activó mediante simulación y revisión firmada existentes,
con cinco categorías y cinco coincidencias en texto ficticio.

Reglas nuevas 9–12: claves privadas, credenciales, documentación interna y
consentimiento de datos salariales. Las reglas anteriores 4–8 quedaron inactivas
con sus valores anteriores en auditoría. El agente se renombró «Asistente de
trabajo»; se crearon únicamente dos conversaciones vacías, sin respuestas
fabricadas: «Contacto de ejemplo» (7) y «Plan de trabajo» (8).

Comprobación final: 36 tablas ajenas a las modificaciones autorizadas conservan
sus huellas, incluidas credenciales, usuarios, permisos, conversaciones previas
en sus tablas de mensajes/solicitudes, modelos y registros económicos. Web,
worker y PostgreSQL activos con cero reinicios; sin trabajos pendientes ni
reservas ocupadas. El clon se eliminó tras comprobar su identidad. Backups e
imagen anterior se conservan en la VM. El entorno E2B real produjo DOCX/PDF y
superó la comprobación de aislamiento sin inferencia.

La instancia escucha por túneles loopback en 8800 y 8893. El proceso simulado
anterior de 8893, propiedad de esta tarea, se detuvo sin borrar su base.
No se volvió a automatizar el navegador tras el rechazo de su política de URL;
no se afirma una nueva verificación visual ni una generación real de proveedor.

Evidencia sin secretos: [preparación](../../../output/privacy-20261017/real-prepare.json),
[aplicación](../../../output/privacy-20261017/real-apply.json),
[modelos](../../../output/privacy-20261017/real-models.json),
[sandbox](../../../output/privacy-20261017/real-sandbox.json),
[invariantes y servicios](../../../output/privacy-20261017/real-finish.json).
[Guía breve](../demo-privacidad-local.md).

Reversión: directorio privado `/opt/regulai/updates/privacy-20261017-a1`, dumps
`before-prepare.dump` y `before-apply.dump`, web anterior
`regulai-v2-web-before-privacy-20261017-a1`. No volver directamente a la imagen
anterior después de crear chats protegidos: conservar lector, esquema y claves
compatibles. Para retirar la configuración, preparar primero una revisión
compatible con los datos ya creados; no eliminar las tablas de privacidad ni
reintroducir originales en el proveedor. Las reglas anteriores se recuperan
desde la auditoría mediante una nueva revisión explícita.
