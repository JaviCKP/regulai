# Operación de la protección reversible

La función se entrega desactivada. Aplicar las migraciones no activa empresas, no reprocesa históricos ni concede permisos. Véase la [especificación](plan-tokenizacion-reversible-20261017.md) y la [evidencia de entrega](entrega-privacidad-20261017.md).

Activación local posterior solicitada por el usuario: la cuenta «Pruebas de Javi»
queda preparada en [la tarea 90](tareas/90-demo-privacidad-cuenta-local.md).
[Guía para probarla](demo-privacidad-local.md). Los límites de cobertura de esta guía se mantienen.

## Activación y cambios

1. Desplegar una versión que incluya las migraciones 0044 y 0045, el lector de proyección y su build React. Primero comprobarlo en una copia aislada.
2. Con un administrador autorizado de la política, abrir Configuración → Datos protegidos. Elegir categorías, textos exactos o cadenas YARA compatibles.
3. Probar con texto ficticio y revisar «Ahora» y «Con el cambio». La prueba es local: no consulta modelos ni activa el borrador.
4. Activar mediante la revisión firmada. La firma caduca a los 15 minutos y queda invalidada por cambios de política o reglas. Repetir la prueba si caduca.

La interfaz de esta entrega fue comprobada solo con fixtures. No se ha realizado ninguna activación real. Una categoría sin protección opcional sigue sometida a D2. Cambiar el tratamiento no cambia `Rule.action`, ni los requisitos de consentimiento o autorización de destino/modelo.

Una ejecución fija su revisión y las selecciones del chat. Si cambian mientras está en curso, sus siguientes salidas se detienen; un envío nuevo prepara el historial con la revisión vigente. Una política relajada no deshace los alias que ya se habían enviado. Retirar la configuración de una conversación protegida impide nuevos envíos hasta disponer de una política compatible.

## Cobertura

- Texto UTF-8 y campos estructurados: patrones locales de correo, teléfono, documento, cuenta y tarjeta; nombres etiquetados, campos explícitos, diccionarios y selecciones exactas.
- Los nombres libres no marcados no tienen detección general. No se usa una API para localizar datos personales.
- YARA solo permite cadenas localizables del subconjunto validado. Fallos de compilación, timeout, cambios de hash o rangos ambiguos detienen el envío. Las reglas incompatibles no se pueden activar como sustitución.
- Secretos y solapamientos irreversibles nunca crean una correspondencia recuperable. Las reglas irreversibles contextuales pueden ocultar también originales históricos por precaución.
- PDF, imágenes, OCR y otros binarios se bloquean en los canales afectados: no se presenta el texto extraído como saneamiento del documento completo.
- Los valores se ocultan, pero el contexto puede permitir inferencias. Recuperar una referencia no demuestra que la afirmación de la IA sea correcta.

## Almacenamiento, claves y retención

`ConversationAlias` mantiene el original cifrado y su ámbito empresa/usuario/conversación. `PrivacyMessage` almacena canónico, digest HMAC y variantes cifradas; `PrivacyOccurrence`, `PrivacyUse` y `PrivacyCall` contienen trazabilidad sin párrafos originales. Los eventos y checkpoints conservan la representación protegida. La proyección natural se deriva al entregar cada lote al propietario actualmente autorizado.

El valor canónico del alias es la primera grafía registrada. La burbuja del usuario conserva su variante exacta por aparición. Una respuesta que solo contiene el alias usa el original canónico: no se reconstruye texto que el modelo no devolvió.

Rotación de cifrado: instalar la nueva `ENCRYPTION_KEY` y mantener las anteriores en `ENCRYPTION_KEY_FALLBACKS` mientras existan registros y copias que las necesiten. Las escrituras usan la primaria. La prueba verifica lectura con fallback y fallo cerrado sin él; no se incluye una recifración masiva automática.

Rotación de búsqueda: `PRIVACY_LOOKUP_KEYS` es un mapa de versiones enteras a claves. La versión 1 predeterminada utiliza `SECRET_KEY`; conservarla explícitamente al rotarla y añadir una versión mayor. Se buscan primero las versiones anteriores y solo los valores nuevos usan la mayor, manteniendo identificadores existentes. No retirar claves antiguas para forzar compatibilidad.

Eliminar una conversación elimina sus correspondencias y usos por cascada. Purgar un original hace que aparezca como no disponible; no reconstruirlo desde otros ámbitos. La purga de correspondencias no borra originales que otras funciones retengan, ni copias de seguridad: ambas siguen la política de retención de la instalación. No se añade un plazo automático de borrado.

## Recuentos y estados

- **Valor:** un alias distinto dentro del ámbito, no una persona identificada.
- **Aparición:** sustitución en una revisión de mensaje. Reenviar referencias existentes no crea otra aparición del original.
- **Uso:** inclusión en una salida registrada. Una misma petición/llamada idempotente no lo incrementa de nuevo.
- **Entrada / historial / otros:** referencias incluidas en las llamadas externas registradas; los reenvíos cuentan en cada llamada. El desglose se fija al construir el payload, sin guardar sus originales.
- **Respuesta guardada:** referencias en el mensaje canónico final; no fragmentos SSE.
- **Sin confirmar:** una llamada registrada que no consta completada. Registrar una intención no demuestra que el proveedor recibiera o facturara la petición. Los recibos existentes siguen siendo la fuente de coste/estado.

El inspector pagina valores y revela originales mediante POST, bajo permisos vigentes y CSRF. Ser administrador no permite leer chats ajenos. Copiar/exportar solicita otra proyección autorizada: no reutiliza un original mostrado con permisos antiguos.

## Fallos y recuperación

La interfaz muestra un error breve; el servidor conserva códigos sin valores sensibles. `privacy_policy_changed` o una revisión caducada requieren preparar de nuevo la operación; `privacy_reference_unavailable` no autoriza buscar en otros chats; `privacy_binary_channel_blocked` exige un flujo de saneamiento específico. Ante una clave ausente, restaurar la configuración de claves correcta; nunca enviar el original como alternativa.

Una interrupción retira la salida natural provisional y mantiene el estado incierto del recibo. Reconectar reconstruye la proyección desde eventos canónicos, con offsets UTF-8 protegidos, un parser independiente por consumidor y deduplicación de secuencias. YARA contextual puede exigir esperar el resultado completo.

## Reversión

La prueba de migración realiza 0043 → 0045 → 0043 → 0045 en PostgreSQL desechable y verifica que los alias preexistentes conservan exactamente su ciphertext y que la política sigue ausente por defecto.

Revertir 0044/0045 elimina las tablas nuevas de trazabilidad; **no es un procedimiento seguro de rollback con conversaciones nuevas en uso**. En una instalación activa, conservar las tablas y claves, mantener un lector compatible o dejar indisponibles los chats afectados antes de volver a código anterior. Cambiar a `REGULAI_CHAT_FRONTEND=legacy` mantiene el motor servidor y la proyección; allí no se ofrecen inspector ni previsualización. La reversión de aplicación debe prepararse aparte de la reversión de esquema.
