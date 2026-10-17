# Probar la protección en la cuenta local

Abre [RegulAI](http://127.0.0.1:8800/). La dirección que estaba abierta,
[localhost:8893](http://127.0.0.1:8893/), también apunta ahora a esta instalación.
Usuario **admin**, empresa **Pruebas de Javi**. La contraseña se conserva.

La conexión existente ofrece **DeepSeek Flash** y **DeepSeek Pro**. El agente
**Asistente de trabajo** utiliza Flash. No se han trasladado claves a otra cuenta.

## Cinco pruebas

| Dónde | Texto para pegar | Resultado esperado |
| --- | --- | --- |
| Chat nuevo, modo Agente | `hola` | Respuesta breve en el chat; no solicita ni intenta entregar archivos. |
| «Contacto de ejemplo», modo Chat | `Prepara una ficha: Lucia Romero, lucia.romero@example.com, DNI 12345678Z, teléfono +34 612 345 678.` | El botón del escudo («Ver lo que recibirá la IA») muestra correo, DNI y teléfono protegidos; la vista del propietario conserva los valores recuperables. |
| Chat nuevo | `SOLO USO INTERNO` seguido de un salto de línea y `Plan comercial del próximo trimestre.` | Bloqueo por «Documentación interna», antes del proveedor. |
| Chat nuevo | `Listado de personal: Lucia Romero, salario de ejemplo 32000 EUR.` | Pide confirmación por «Datos de personal». Cancelar no consulta al modelo. |
| «Plan de trabajo», modo Agente | `Prepara un plan de cinco pasos para organizar una jornada de formación. No busques en Internet.` | Usa el agente configurado y muestra sus pasos y respuesta. |

Todo el contenido anterior es ficticio. Enviar un mensaje permitido o confirmar
un envío usa la conexión real y puede consumir saldo del proveedor.

En [Configuración → Datos protegidos](http://127.0.0.1:8800/settings/privacy/)
están activados correo, teléfono, DNI/NIE, cuenta/IBAN y tarjeta en modo recuperable.
Para cambiarlo: elegir tratamiento, probar con datos ficticios y activar el cambio.
Los secretos mantienen su tratamiento irreversible.

Las cuatro reglas activas son **Claves privadas**, **Credenciales de acceso**,
**Documentación interna** y **Datos de personal**. Las cinco reglas antiguas
identificadas se conservan desactivadas, con auditoría, incluidas las duplicadas
y la que buscaba `REGULAI_TEST_BLOCK`.

La protección opcional cubre texto; no ofrece saneamiento general de PDF,
imágenes ni binarios. El agente puede iniciar trabajos nuevos de texto; la
reutilización de archivos/historial binario protegido sigue sujeta al bloqueo
documentado. No hay búsqueda comercial ni navegador JavaScript configurados.

## Arranque y evidencia

El lanzador existente `%LOCALAPPDATA%/RegulAI-real/Iniciar RegulAI.cmd` conserva
su función de arrancar la instancia v2 en el puerto 8800; no reinstala la cuenta.
La dirección 8893 es un segundo túnel de esta sesión. El laboratorio simulado que
ocupaba ese puerto se ha detenido, conservando su base.

Verificados: catálogo real de modelos por GET (HTTP 200), 61 pruebas del servidor
preparado, migración en clon y conservación de datos, cinco coincidencias del
detector, build React completo y microVM real con DOCX/PDF y aislamiento de red.
Web, worker y PostgreSQL siguen activos sin reinicios. **Cero llamadas nuevas
de generación**; la respuesta de un modelo real queda para la prueba del usuario.
No se ha realizado una nueva revisión visual: el acceso del navegador automatizado
fue rechazado por su política de URL.

[Registro técnico y reversión](tareas/90-demo-privacidad-cuenta-local.md).
[Corrección del bloqueo de saludos y comprobaciones posteriores](tareas/91-saludo-agente-bloques-texto.md).
