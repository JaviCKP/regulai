# 25: Operación y recuperación en laboratorio aislado

**Status:** done (laboratorio local sintético)
**Blocked by:** ninguno para este alcance; entorno público y CI remoto no ejecutados.
**Specification:** [12](../12-demo-y-salida.md), [rotación](../rotacion-claves.md).

## Aceptación

- [x] Instalación reproducible, check --deploy, Gunicorn/HTTPS/cookies/hosts/estáticos/archivos privados y logs.
- [x] Dos empresas aisladas; concurrencia, interrupción y recuperación de incertidumbre.
- [x] Pruebas relevantes PostgreSQL, migraciones históricas, recifrado/conflicto real y restauración de base/medios/claves.
- [x] Evidencia de ejecución y límites respecto a CI remoto o infraestructura publicada.

## Verificación observada

Ejecuciones06 y07 con código0. [Resultado07](../../../evals/reports/pilot-operations-20261003-07/result.json): 82 pruebas PostgreSQL en12,464 s, una omisión específica de SQLite; escritor concurrente PostgreSQL comprobado aparte. Restauración exacta de todas las tablas, dos archivos y claves; recifrado/reversión correctos. Reinicio real durante llamada deja incertidumbre sin reenvío ni coste0. Arranque opcional supervisado probado un segundo, sin participantes.

[Verificación de logs](../../../evals/reports/pilot-operations-20261003-summary/verification.json): siete ejecuciones preservadas, hashes de comandos correctos y cero coincidencias de claves sintéticas o marcador sensible en logs. Contenedores propios retirados; comprobación posterior de Docker vacía. Los intentos01–05 conservan sus fallos y resultados parciales. [Procedimiento y límites](../operacion-y-recuperacion-piloto.md).
