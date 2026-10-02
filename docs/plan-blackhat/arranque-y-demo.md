# Arranque local, configuración y demo de cinco minutos

Desde `C:\Users\javi\Documents\Codex\regulai-platform`. Python probado: 3.12.11. Conservar entornos, bases y configuración existentes. [Resultados observados](estado-ejecucion.md), [guion técnico de demo](../../evals/DEMO.md) y [evaluación offline](../../evals/README.md).

## Instalación y comprobación

Solo si no existe `.venv`, crearla. La lista raíz es la única fuente; no instalar la interior por separado:

```powershell
rtk proxy uv venv --python 3.12.11 .venv
rtk proxy uv pip sync --python .venv/Scripts/python.exe requirements.txt
rtk proxy .venv/Scripts/python.exe regulai/manage.py check --settings=regulai.test_settings
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front api --settings=regulai.test_settings
rtk proxy .venv/Scripts/python.exe regulai/manage.py makemigrations --check --dry-run --settings=regulai.test_settings
rtk proxy uv tool run pip-audit -r requirements.txt
```

Los tests usan una base aislada y proveedores simulados. El resultado de la auditoría y las versiones se registran por fecha; [dependencias comprobadas](dependencias-verificadas.md). La sincronización reemplaza paquetes del entorno virtual elegido, no datos de la aplicación.

## Demo recomendada, sin salida del servidor a proveedores ni claves reales

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py run_demo --settings=regulai.demo_settings
```

Abrir `http://127.0.0.1:8001/login/`, usuario **`community-demo`**, contraseña pública sintética **`community-demo-only`**. Si ese puerto está ocupado, añadir `--port 8002`. Para preparar sin servidor, añadir `--seed-only`.

Usa exclusivamente `regulai/community-demo.sqlite3` y `regulai/community-demo-media`, con cookies propias. Migra y siembra una vez. Reiniciar conserva conversaciones y contraseña. Si alguien cambia el fixture de configuración, perfiles, credenciales, catálogo o reglas, falla sin sobrescribirlo: revisar la diferencia, no borrar la base para esconderla. Durante este comando están simuladas generación y HTTP de Jev; el proceso servidor bloquea las demás conexiones HTTP y socket. El navegador aún puede pedir glifos a Iconify: este bloqueo no convierte la presentación en un entorno completamente sin red. El banner **DEMO OFFLINE — fallo simulado** distingue esos resultados de una llamada real. El arranque normal no instala estos parches.

### Guion de cinco minutos

| Tiempo | Acción exacta | Qué enseñar |
| --- | --- | --- |
| 0:00–1:00 | Chat, motor **Synthetic economy**, enviar `Devuelve el saludo Hola.` | Respuesta prefijada, ruta autorizada, comprobaciones y coste **simulado**. No anunciar ahorro real. |
| 1:00–2:00 | Conversación nueva; enviar `SYNTHETIC_SECRET_DEMO` | Bloqueo YARA y ficha con cero llamadas; no sale al clasificador ni al generador simulado. |
| 2:00–4:00 | Conversación nueva, **Synthetic economy**, adjuntar `evals/documents/demo-contract.txt`; preguntar `¿Cuál es el precio del contrato?` | El primer fixture responde 900 euros y el juez prefijado lo rechaza; segundo intento fuerte devuelve 10 euros. Abrir los intentos y la evidencia del contrato. No presentar al juez prefijado como prueba de exactitud real. |
| 4:00–5:00 | Abrir la ficha/evidencia y explicar cobertura, llamadas y coste desconocido; si queda tiempo, **Policy simulator**, comparar localmente un borrador | Una regla que encuentra `public` puede bloquear el informe público sintético. Probar una corrección que encuentre `synthetic secret`, sin activarla durante la presentación. |

Otros documentos piden aclaración en esta demo; otros mensajes generales usan el saludo sintético. Se comprobaron las tres escenas en navegador: saludo `Hola` con ruta automática y tres llamadas simuladas; secreto bloqueado con cero llamadas; contrato de 10 euros con cita en línea 2, dos generaciones/cinco llamadas simuladas y persistencia tras recargar. Cancelar una advertencia termina en `cancelled` sin respuesta; confirmar con el archivo original mantiene una sola burbuja de usuario y devuelve `10 euros [1]`. El simulador comparó y activó una política local en otra empresa sin credenciales ni destinos, con cero llamadas reales. Se probó Enter para enviar y abrir la ficha y Espacio para alternar la ruta automática. La apertura de citas con teclado sigue sin comprobar: la herramienta rechazó reabrir la URL local. Capturas en [estado observado](estado-ejecucion.md). Los dos ensayos humanos completos permanecen pendientes hasta realizarse y registrarse.

## Servidor de desarrollo normal

Solo para una base de desarrollo identificada, tras conservar copia de la base y de la configuración. El bootstrap crea `local_settings.py` únicamente si falta y genera claves sin imprimirlas. Si ya existe, se conserva; comprobar que su base es la de desarrollo antes de migrar.

```powershell
rtk proxy .venv/Scripts/python.exe scripts/bootstrap_local.py
rtk proxy .venv/Scripts/python.exe regulai/manage.py migrate
rtk proxy .venv/Scripts/python.exe regulai/manage.py runserver 127.0.0.1:8765 --noreload
```

La base local preparada es `regulai/community-local.sqlite3`. La cuenta sintética existente `community-local-demo` / `Local-demo-only-2026!` se usa solo en loopback. Actualmente `ai_config={}`: el envío devuelve 503 con cero llamadas. No importar claves reales ni activar llamadas durante el ensayo offline.

Con `--noreload`, reiniciar el proceso después de editar plantillas para ver los cambios: Django puede mantenerlas en caché. La preparación de recursos locales mediante `scripts/vendor_assets.py` fue comprobada; no hace llamadas a modelos.

Un administrador de empresa trabaja sobre su empresa. El catálogo global y Django admin requieren un operador activo con `is_staff`, `is_superuser` e ID explícito en `PLATFORM_ADMIN_USER_IDS` de la configuración local. Usar únicamente IDs de operadores elegidos; no conceder el ámbito global a todos los administradores de empresa. No abrir `media/` como ruta pública; las descargas y avatares pasan por vistas autenticadas.

## Configuración IA de ejemplo, sin secretos

[ai-config-example.json](ai-config-example.json) valida con `AIConfig` y **mantiene cerrada la salida**: sin destinos, sin candidatos, presupuesto cero. Es una base segura para editar en el simulador, no una política que produzca respuestas.

Para una política autorizada, configurar destinos por sensibilidad (`engine:<CompanyEngine.id>`, `jev` y, si procede, `obfuscation:<id>`). La credencial de Jev va en el campo cifrado `Company.jev_api_key`; las de generación en `CompanyEngine.api_key`. Ninguna pertenece al JSON. Los modelos necesitan contexto, salida máxima, capacidades, moneda, fecha y tarifas vigentes. Un presupuesto acotado rechaza precios desconocidos.

Ejemplo de **un candidato**, con IDs de muestra que deben sustituirse por filas activas de la propia empresa:

```json
{"company_engine_id": 101, "model_id": 201, "level": "economy", "quality": {"general": 0.5}}
```

El ID 101 sería de `CompanyEngine`; 201 sería de `EngineModel` del mismo motor. El simulador revalida pertenencia y actividad. El valor de calidad anterior es ilustrativo, no calibrado. Para semántica requerida, también hacen falta permiso real hacia Jev, acceso de cuenta, tarifas y límite contractual por llamada. Esta cuenta Gateway devuelve 403: no usar esa ruta en vivo ni comprar créditos automáticamente.

La activación del simulador es un POST separado tras revisar la comparación. Revalida el borrador y comprueba versión/digests de política y reglas. Una edición concurrente o prueba expirada exige repetir la comparación.

## Evaluación repetible

Elegir un directorio **nuevo** para conservar informes anteriores:

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py evaluate_ai --settings=regulai.test_settings --output evals/reports/offline-repeticion-local
```

El comando acepta SQLite en memoria, ejecuta 50 casos en tres configuraciones y bloquea red externa. Rechaza una salida ya existente. Informe final: [offline-2026-10-02-04](../../evals/reports/offline-2026-10-02-04/report.md), con hashes SHA-256 de los bytes exactos de los archivos ejecutados, comprobados de nuevo contra los archivos actuales. `--real` está desactivado en este banco; las pruebas reales acotadas fueron otro comando con registro persistente y no deben repetirse como parte del arranque.

## Recuperación

1. Demo offline: terminar con Ctrl+C. Sus parches desaparecen con el proceso; iniciar el servidor normal con sus settings habituales conserva sus datos. No borrar la base normal ni sustituir claves para retirar la demo.
2. Cambio de política: copiar `previous_config` del AuditLog `policy_activate` correspondiente, compararlo como nuevo borrador y activarlo con una revisión nueva. Si las reglas cambiaron, reconstruir el borrador con `rule_before.yara_rule` y sus campos anteriores; `rule_after` registra la versión nueva. La auditoría está limitada a la empresa y no incluye la muestra ni credenciales. Si era una regla nueva y `rule_before` es nulo, desactivarla como cambio explícito revisado.
3. Error de proveedor o validación: mantener el estado explícito y la salida cerrada; usar la demo offline rotulada. No saltarse comprobaciones ni repetir automáticamente un resultado incierto.
4. Cambio de código/esquema: conservar una copia consistente de SQLite y settings antes de migrar. Volver a una revisión solo con su esquema y copia compatibles; no ejecutar una migración destructiva sobre la única base. Las claves de cifrado deben conservarse para leer credenciales existentes.

No hay despliegue autorizado. El presupuesto real de pruebas era 1 USD; una estimación DeepSeek de 0,00000870 USD y reservas Jev inciertas de 0,03 USD están documentadas en el [estado](estado-ejecucion.md). No confundir esas reservas con cobro confirmado o con llamadas gratuitas.
