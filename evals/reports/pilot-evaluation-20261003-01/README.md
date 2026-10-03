# Evidencia local del evaluador — 3 octubre 2026

**Preparación técnica comprobada; proveedores vivos y revisión humana pendientes.** No hubo llamadas nuevas de producto, gasto de APIs, compra de créditos, cambios en bases del usuario, despliegue ni publicación.

## Resultado final

| Comprobación | Resultado observado |
| --- | --- |
| Tests focalizados tras el último cambio | **20 OK**, 12,811 s, exit 0. Incluyen ledger concurrente/reinicio/cotas, autorización, transporte HTTP/SDK simulado y métricas humanas. |
| Suite ampliada inmediatamente anterior | **29 OK**, 44,192 s, exit 0. Incluye banco anterior de 150 recorridos offline, reproducibilidad y demo D2. El ajuste posterior separó reservas `not_started` de llamadas iniciadas y tiene regresión en los 20 tests finales. |
| Smoke final | **8 casos × 3 = 24 recorridos**, 0 controles fallidos, 0 llamadas reales, 0 revisiones humanas. |
| Preparación humana final | **24 casos × 3 = 72 recorridos**, 0 controles fallidos, 0 llamadas reales, 0 revisiones humanas. No mide precisión de proveedores. |
| Django check | Sin incidencias, exit 0. |
| git diff --check | Exit 0. |
| Preflight real | `ready_for_real=false`, sin red ni efectos en la base. Faltan aprobación, ventana, aceptación del alias, revisión operativa de tarifas, máscara/contrato y credenciales aisladas. |

Los [resultados finales del smoke](smoke-offline-final/report.md) y de la [preparación humana](human-offline-final/report.md) incluyen datos y rúbrica congelados, orden de ejecución, fuentes/runtime, respuestas de los intentos, recibos, dinero por procedencia, p50/p95 con n y plantillas humanas vacías. [Auditoría](audit.json): todos los hashes de fuentes de ambos informes finales coinciden con el árbol al cerrar esta evidencia. [Preflight](preflight.json) y [comandos/resultados](gates.json).

Los subdirectorios `smoke-offline` y `human-offline` conservan la ejecución previa al último ajuste de métricas. No se sustituyeron por la repetición final. Los logs `test-output-tail.log` y `test-final-output-tail.log` son fragmentos finales de la salida de herramientas; no pretenden ser el log completo de inicio. Los errores de proveedor y controles fallidos dentro de tests negativos son fallos inducidos y esperados, no llamadas reales.

## Invariantes ejercitadas

Los tests del modo real utilizan el servicio, conectores y cliente Jev reales, sustituyendo únicamente HTTP/SDK y bloqueando socket. Cada transporte comprobó que su llamada estaba reservada y persistida como `started` antes de responder. Smoke y evaluate comparten ledger; errores de máscara, JSON inválido del juez, timeout, cambio de modelo y revocación paran llamadas posteriores. El lock ajeno se conserva. Reservas inciertas sobreviven a reinicio; las estimaciones no liberan cota; un exceso se conserva y bloquea gasto nuevo. Una reserva probada no iniciada puede liquidarse a cero y no cuenta como ejecución del proveedor.

Las métricas no convierten `passed`, un juez prefijado o una coincidencia textual en aprobación humana. El coste por respuesta correcta queda null sin revisión completa o con costes desconocidos. Las referencias de desarrollo/reservado son borradores separados; nadie ha completado ni validado las etiquetas.

## Aprobación todavía pendiente

[Propuesta exacta y recuperación](../../../docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md). Techo propuesto conjunto: **1,00 USD** para ambos comandos y manifiestos; ninguna nueva autorización concedida. El enmascarador real sigue sin URL/contrato/precio verificados; se rechaza el marcador `.invalid`. Jev directo `jev-1.13.0` aún requiere acceso comprobado. Los alias DeepSeek no garantizan fijación de pesos y se declaran como limitación.

Las primeras sesiones humanas propuestas son locales, con dos personas y coste de API **0 USD**, para referencias/rúbrica/controles y comprensión. Precisión, calibración, ahorro y comparación viva permanecen pendientes.

Hashes finales de manifiestos:

- `pilot-real/manifest.json`: `70086f93362e76e2110b8c67db2f703d6d53b43c53b7cb23c91da8963bcd0200`.
- `pilot-human/manifest.json`: `4879ab40d339ccd3905d306ce93cb4b8ac635e95274eddcba6751b834538ef7c`.

Un cambio posterior de fuentes, dependencias, datos, etiquetas, rúbrica, tarifas o manifiesto exige nueva preparación/revisión. No se reescriben estos resultados ni se renueva automáticamente la autorización del ledger.
