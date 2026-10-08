# 53. Un conector documental mediante MCP

Estado: pendiente de implementación.
Blocked by: [52](52-agente-powerpoint.md).
Especificación: [guía de ejecución](../../implementacion-agente-regulay-prompts.md), sección de conectores del [plan](../../plan-capacidades-agenticas-regulay-2026-10-07.md).

## Prompt de ejecución

```text
Implementa exclusivamente la tarea 53. Lee AGENTS.md y
docs/implementacion-agente-regulay-prompts.md. Reutiliza el ejecutor, gobierno,
puerta de resultados y artefactos ya verificados.

Integra un cliente MCP mantenido y un único servidor documental de lectura.
Comprueba primero qué conexión autorizada existe en el entorno del piloto.
Prioriza Google Drive si ya está disponible; si el piloto usa Microsoft 365,
usa ese destino. No construyas ambos conectores ni supongas que las conexiones
del asistente de desarrollo son credenciales de los usuarios de Regulay.

El recorrido es buscar un documento autorizado, obtenerlo, conservarlo como
entrada privada y producir un informe. Las credenciales viven en el módulo de
herramientas de confianza; el modelo y el terminal reciben referencias opacas.
Los documentos descargados pasan por las mismas vistas y alias que los adjuntos.

La configuración administrada define servidor, operaciones y alcance. Expón solo
búsqueda/lectura/descarga autorizadas. Revalida identidad y permisos en cada paso;
no confíes en el indicador read-only del servidor. Un cambio de catálogo o schema
no amplía permisos. No habilites sampling/inferencia de MCP por defecto ni una
salida de red alternativa. Los procesos stdio no heredan secretos del servidor.

Usa una configuración versionada sencilla; no marketplace, instalación autónoma,
descubrimiento ilimitado de servidores ni sincronización completa de cuentas.
Fija una versión del adaptador MCP compatible con Deep Agents y traduce errores
a mensajes útiles sin volcar respuestas crudas o credenciales.

Prueba el contrato con un servidor MCP real de fixtures y transportes externos
simulados: revocación entre búsqueda y descarga, documento ajeno, cambio de
esquema, instrucciones maliciosas y error con datos sensibles. Este banco no
acredita que la conexión externa del piloto esté habilitada: deja esa comprobación
pendiente si no hay cuenta autorizada. No solicites aprobar cada lectura permitida.

Si la integración elegida exige un alta o autorización humana que falta, prepara
la configuración concreta y completa las pruebas independientes; no inventes
credenciales ni actives otra integración por tu cuenta. Registra resultados y
detente antes de la 54. No implementes aún escrituras externas.
```

## Aceptación

- Un único conector/servidor seleccionado; buscar/obtener/procesar usa el recorrido existente.
- Revocación, alcance y datos cruzados se comprueban por operación, no solo al conectar.
- Sin credenciales en prompts, resultados, logs o sandbox; sin inferencia MCP fuera de Regulay.
- Lecturas autorizadas sin confirmaciones; configuración administrada y permisos explícitos.
- Se distingue claramente evidencia del servidor de fixtures y prueba de la cuenta externa.

## Verificación observada

Pendiente. No se ha seleccionado una cuenta del piloto ni conectado un servidor MCP al producto.
