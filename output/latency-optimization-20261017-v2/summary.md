**Comparación formal completa: 140 ejecuciones por variante.**

20 procesos nuevos por variante; 20 primeras ejecuciones y 120 calientes. Mismo backup, banco e inputs, tres entradas HTTP y catálogo automático. Los timestamps verifican las parejas alternadas y la ausencia de solapamiento entre rondas. Cada ejecución completó exactamente una inferencia y un checkpoint.

| Medida | n por variante | Antes mediana / p95 | Después mediana / p95 |
| --- | ---: | ---: | ---: |
| Preparación simple caliente | 60 | 1,116 / 1,411 s | 0,816 / 0,992 s |
| Preparación sensible caliente | 60 | 1,147 / 1,445 s | 0,859 / 1,049 s |
| Preparación fría de proceso | 20 | 1,752 / 2,198 s | 1,438 / 1,758 s |
| Cola con capacidad libre | 140 | 0,153 / 0,213 s | 0,106 / 0,152 s |
| Cola: admisión hasta commit | 140 | 0,094 / 0,141 s | 0,059 / 0,095 s |
| Cola: despacho tras commit | 140 | 0,056 / 0,080 s | 0,046 / 0,063 s |
| Hasta primera inferencia, caliente | 120 | 1,297 / 1,581 s | 0,953 / 1,136 s |
| SELECT preparación simple caliente | 60 | 525 / 525 | 308 / 308 |

Metas comprobadas:

- Preparación simple caliente p95 < 700 ms: **no alcanzada**.
- Preparación fría p95 < 1,5 s: **no alcanzada**.
- Cola con capacidad libre p95 < 100 ms: **no alcanzada**.

p95 usa rango más próximo. El frío es la primera ejecución tras inicialización de Django/SDK; la base se restaura desde el mismo backup y no se vacían las cachés de PostgreSQL/SO. El timestamp de commit corresponde al callback de aplicación. SQL excluye admisión, claim y conductor.

El worker y servidor usan HTTP real por loopback; las tres admisiones usan Django TestClient. El proveedor está simulado y la red exterior bloqueada. Estos tiempos no predicen la latencia del modelo real.

Fuera de la comparación formal: 5 parejas piloto, 5 perfiles y 8 escenarios auxiliares. Los pilotos con distintos hashes no permiten atribuir sus diferencias al producto. El desglose completo, historiales y concurrencia están en summary.json.

[Instalación y ensayos auxiliares](DELIVERY.md) · [Cambios, caché e invariantes](CHANGES-AND-SAFETY.md) · [Perfil CPU/SQL/HTTP](PROFILE-ANALYSIS.md) · [Cola](QUEUE-ANALYSIS.md) · [Verificar, reproducir y revertir](REPRODUCE.md).
