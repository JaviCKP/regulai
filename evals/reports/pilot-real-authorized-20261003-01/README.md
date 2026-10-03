# Primera autorización nueva: diagnóstico sin llamadas

El usuario aprobó expresamente «Autorizar hasta1USDparaesos8casos» en la conversación, después de recibir destinos, datos, modelos, límites, parada y ventana. `authorization.json` registra esa primera propuesta TypeSafe directo, sin incluir el banco humano. La ventana operativa se recortó al día UTC de revisión de tarifas, dentro del máximo24h autorizado.

El preflight pasó todas las comprobaciones de autorización/fuentes/versión/precios y solo señaló `isolated_credentials_required`: ninguna conexión de producto ni ledger abierto; gasto0USD. Una consulta local separada en SQLite `mode=ro` encontró una credencial DeepSeek y una Gateway, ninguna TypeSafe directa; no mostró valores ni modificó la base.

**Propuesta sustituida después:** el usuario indicó que no dispone de TypeSafe directo y ordenó ejecutar Jev a través de Vercel. Esa autorización expresa conserva ocho casos y1USD total; su manifiesto y ejecución se documentan en [el ensayo Vercel](../pilot-real-vercel-20261003-01/README.md). Esta carpeta es evidencia histórica del diagnóstico, no la configuración activa de ejecución. No se vuelve a pedir aprobación del mismo gasto.
