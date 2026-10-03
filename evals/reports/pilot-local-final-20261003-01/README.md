# Ensayos offline finales con detector local v2

Código fijo `0957df45362bc7cbf41c154bb13514d58901763a`; manifiestos integrados en `4c7695e`. `run_snapshot.py` preserva las versiones anteriores, compara cambios permitidos y ejecuta los bancos offline. Solo cambiaron hashes de fuente e identidad `regulai-local-v2`; casos, rúbricas, precios, etiquetas y umbrales permanecen iguales. La autorización continúa **pending**.

| Banco | Recorridos / controles cumplidos | Transformaciones CPU | Llamadas externas simuladas |
| --- | --- | ---: | ---: |
| [Smoke](smoke/report.md) | 24 / 24 | 38 | 54 |
| [Banco humano preparado](human/report.md) | 72 / 72 | 120 | 180 |

Se usa el detector instalado real; clasificación, generación y juez son simulados. **APIs reales0, gasto de producto0USD, revisiones humanas0.** Controles cumplidos no significa respuestas correctas según personas. Coste por respuesta correcta permanece nulo. Los informes conservan p50/p95 y tamaño de muestra por configuración y split; no sumar filas `all` con sus subdivisiones.

Los dos preflight terminaron exit0 como consultas diagnósticas y `ready_for_real=false`: faltan aprobación, ventana, aceptación de alias móviles, revisión de tarifas vinculada a esa aprobación y credenciales aisladas; el banco humano además necesita autorización de reservados y validación independiente de referencias. No hay deriva de fuentes/runtime/detector. No se crearon directorios de ejecución real ni se abrió su ledger.

Los hashes para una futura propuesta son `12aecafee1351be7584791db4f4e0d22d9f522abb7552bdce7af804e2525c1ed` y `82e94e25bbf0ea512e82c925884e57ca85a8cd6b693be86907ecd9c31f349665`. Los destinos exactos y el techo conjunto de1USD están en la [propuesta](../../../docs/plan-blackhat/ejecucion-real-y-calibracion-piloto.md). Tarifas oficiales consultadas el3octubre siguen coincidiendo; ello no concede permiso de gasto. Cambiar día/configuración requiere revisar y congelar otra propuesta.

[Órdenes, tiempos, códigos y hashes](commands.json). La preparación precedente permanece en [el lote anterior](../pilot-evaluation-local-20261003-01/README.md), sin sobrescribir sus fallos ni sus resultados.
