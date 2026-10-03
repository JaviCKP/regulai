# Checkpoint de preparación y validación del piloto

Encargo del 3 de octubre de 2026. Base fija: `6c78cd396eb72713e85b72d8592970e4b6b66585`.
Las 302 pruebas y 150 ejecuciones anteriores son evidencia histórica.

## Aceptación y límites

Cerrar D2 mediante controles de servidor y transporte, preservar D1–D7 y probar la integración.
Preparar corpus, ensayo real con ledger, evaluación humana, operación y piloto reproducibles.
Los resultados humanos, APIs pagadas, despliegue y CI remoto solo se cierran con ejecución observada y autorización vigente.
No hay permiso para nuevos gastos de producto, push, publicación, bases de usuario ni contacto con participantes.

## Propietarios y dependencias

| Trabajo | Propietario | Depende de | Archivos o contrato |
| --- | --- | --- | --- |
| D2 y privacidad | A, Astra max | Base | chat_service, policy, simulator, masking; bloque mask_texts/import de views; fixtures generales |
| Documentos y navegador | B, Astra max | Contrato D2 | documents/file_security, corpus, UI y pruebas documentales; runner nuevo aislado |
| Ejecutores y calibración | C, Astra max | Contrato D2 y hook ledger acordado con A | evaluate_ai, smoke_ai, evaluation_budget, run_demo, bancos y pruebas propias |
| Operación y recuperación | Orquestador | Docker disponible; D2 para recorrido completo | settings de laboratorio, scripts operativos, tests propios, dos empresas |
| Piloto e integración | Orquestador | A–C y operación | documentación principal, tareas 20/25/26/27, cinco puertas |
| Revisión independiente | Nuevos Astra max | Commit integrado fijo | Solo revisión; seguridad y requisitos separados |

Máximo cuatro agentes simultáneos. Lanzamientos A/B/C aceptaron explícitamente `gpt-6-astra`, `reasoning_effort=max`, `fork_turns=none`. El modelo del orquestador no se puede cambiar ni certificar con las herramientas disponibles.
Índice Git compartido: los agentes no hacen add/commit hasta coordinación. Rama `codex/community-pilot-20261003`.

## Secuencia

1. [x] Inspección Git, instrucciones, planes y contratos existentes; reparto sin propietarios solapados.
2. [x] Cerrar D2 y probar regresiones/fixtures; preparar corpus y ejecutor en paralelo.
3. [ ] Validar instalación Linux/PostgreSQL/HTTPS, estados y recuperación con datos sintéticos.
4. [ ] Integrar commits pequeños, fijar revisión y encargar revisiones independientes.
5. [ ] Reproducir/corregir hallazgos y ejecutar cinco puertas sobre integración final.
6. [ ] Publicar informe local por fase y propuestas concretas para autorizaciones externas.

## Evidencia y estado observado

- Git inicial sin cambios tracked; cinco untracked ajenos preservados: tres PDF raíz, brainstorming Vigía13 y prompt del piloto.
- A confirmó brecha de ausencia de máscara en código; prepara obligación sin toggle desactivable y sin migración prevista.
- Docker Desktop 4.88.1, motor Linux 29.7.2 disponible. WSL tiene Ubuntu y otras distribuciones; no se modifican.
- No existe directorio estándar `C:\Program Files\PostgreSQL`; se usará PostgreSQL efímero Docker para la validación.
- Directorios reservados: `evals/reports/pilot-privacy-20261003-01`, `pilot-documents-20261003-01`, `pilot-evaluation-20261003-01`; operación y gates crearán directorios nuevos.

## Actualización de integración local

- A: finalizado. D2 obligatoria implementada; rojo inicial 3 pruebas/5 fallos. Nuevo fallo de revocación de rol durante máscara en simulador reproducido (1/1 rojo) y corregido; 13 pruebas D2 verdes y gate final de área134 pruebas correcto. Sin migración; políticas sin máscara `both` autorizada fallan cerradas. Commits `d56eca4` (implementación) y `208d9ef` (regresiones/evidencia).
- B: 12 documentos con expectativas congeladas, 12/12 extracción pública y suite documental/UI de65 pruebas verde. No Word/Excel/LibreOffice disponibles (PATH, COM, directorios e inventario). Navegador comprobó caducidad real >300s, renovación409, cancelación sin llamadas, cita con teclado, recarga y móvil375px. Regresión/captura de recibo incierto reconstruido sin coste0; contraste de botones corregido. Cierra último recorrido sobre CSS final y documentación.
- C: ejecutor smoke/evaluación con8 casos×3 configuraciones, observer/ledger compartido. Banco humano24 casos (12desarrollo/12reservado) y preparación offline72 ejecuciones, sin valoraciones humanas. Suite ampliada29 pruebas correcta; repetir20 focalizadas tras último ajuste de reservas no iniciadas. Destino de máscara real y acceso Jev directo siguen pendientes. Propuesta de gasto máximo1USD compartido entre manifiestos, sin autorización reutilizada.
- Root: `scripts/pilot_lab.py`, `ops/pilot/` y settings aislados. Driver opcional psycopg[binary] 3.3.6, imágenes fijadas por digest, build excluye settings/bases/medios locales. Entorno interno PostgreSQL 17, Gunicorn, Nginx HTTPS loopback. Solo proxy en red de entrada; aplicación/DB/proveedor quedan en red Docker interna.
- Operación intentos 01–04 conservados. 01 falla al inspeccionar imagen base no retenida por BuildKit; 02 muestra que red `--internal` no publica el puerto; se separa proxy. 03 detecta estáticos 600 no legibles por Nginx; storage estático ahora644 y medios600. 04 valida HTTPS/cookies/hosts/static/privatefiles/tenants y transportes sintéticos D2; harness repetía login y alcanzó throttle, corregido reutilizando sesión sin bajar límites. Recursos propios retirados en cada intento.
- Operación05: concurrencia/desconexión/reinicio correctos; PostgreSQL82 pruebas con un error por test que asumía `csrftoken` y una omisión SQLite. Se corrigió el test para usar `settings.CSRF_COOKIE_NAME`, conservando comprobaciones de CSRF. Operación06 completa:82 pruebas PostgreSQL correctas (1omisión SQLite), backup/restauración de todas las tablas/medios/claves, recifrado con clave nueva sola, reversión y escritor concurrente real. Código de salida0, recursos propios retirados.
- Ejecución activa: operación07, sesión exec4597; valida el arranque opcional supervisado `--serve-seconds 1`, manifiesto de endpoint y ruta autenticada de avatares de Nginx. No hay participantes ni proveedores vivos. Runner de verificación de logs/hashes preparado en `evals/reports/pilot-operations-20261003-summary/`.
- Preparación del piloto en `piloto-controlado.md`: dos personas por designar, sesión inicial local/offline 0 USD. Tareas20/25/26 creadas; A21, B22, C23/24 reservadas. `scripts/verify_community.py` listo para cinco puertas finales más auditoría opcional PostgreSQL, todavía no ejecutado.

Próximo: cerrar07 y logs, recoger listas B/C, crear commits por propietario, fijar commit para nuevos revisores Astra Max (seguridad y requisitos/Standards). Ejecutar cinco puertas solo después de corregir hallazgos de código. Ningún push, proveedor vivo ni contacto humano.
