**Comparación formal completa: 21 ejecuciones por variante.**

Tres procesos por variante: 3 primeras peticiones y 18 calientes. Mismos mensajes sintéticos, catálogo y tres entradas HTTP. Imágenes inmutables verificadas; la versión medida coincide con la compilación final.

| Medida | n por variante | Antes | Después |
| --- | ---: | ---: | ---: |
| Preparación p95, simple | 12 | 22,862 s | 2,740 s |
| Preparación p95, sensible | 9 | 23,152 s | 1,423 s |
| Preparación p95, caliente | 18 | 23,152 s | 1,423 s |
| Preparación p95, frío de proceso | 3 | 20,147 s | 2,740 s |
| Cola p95 | 21 | 0,521 s | 0,203 s |
| Hasta primera inferencia p95, desde creación | 21 | 23,146 s | 2,638 s |
| Hasta primera inferencia p95, desde POST | 21 | 23,227 s | 2,722 s |
| SELECT de preparación, mediana | 21 | 15922  | 525  |
| Sentencias SQL de preparación, mediana | 21 | 19626  | 589  |

Objetivos para esta muestra: preparación simple p95 < 3 s cumplido; cola p95 < 500 ms cumplido.

p95 usa rango más próximo: posición ceil(0,95 × n). Con 3 muestras frías o 18 calientes coincide con el máximo. El frío corresponde al primer mensaje del proceso, con Django ya inicializado. El desglose por frío/caliente, simple/sensible y entrada HTTP figura en summary.json.

SQL incluye todas las sentencias capturadas antes del proveedor en las rutas internas de preparación; excluye admisión, claim y sondeo del banco. El tiempo hasta primera inferencia no incluye la respuesta del modelo. Proveedor simulado y sockets externos bloqueados.

Cola aislada PostgreSQL, conexión caliente y capacidad libre (sin transporte HTTP del claim):

| Trabajos concurrentes | p95 anterior | p95 notificación |
| --- | ---: | ---: |
| 1 | 454,6 ms | 158,1 ms |
| 2 | 471,6 ms | 177,6 ms |

Catálogo, lectura directa con rollback (5 repeticiones): mediana 2,004 → 0,018 s; SELECT 1990 → 12.
