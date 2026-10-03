# Cinco puertas finales — 3 de octubre de 2026

Revisión de arranque `4c7695eacb3467e28ff02c75c384075b034ccbc6`; runtime corregido en `0957df4`. `scripts/verify_community.py` terminó con exit0. [Manifiesto](manifest.json): `source_unchanged=true`, `passed=true`. Cada orden conserva argumentos, duración, código y SHA256 del log. El código no cambió durante la ejecución.

| Puerta | Resultado observado |
| --- | --- |
| Django check | Exit0, sin incidencias |
| Suite front/api | **378 tests OK, 169,117 s**; exit0 |
| Migraciones | Sin cambios por generar; exit0 |
| Evaluación offline | 150 recorridos de controles, cero fallos, cero proveedores reales; exit0 |
| Dependencias | Aplicación y extensión PostgreSQL: exit0, sin vulnerabilidades conocidas en los paquetes auditables |

El paquete de modelo `xx-ent-wiki-sm` no está en PyPI y pip-audit declara que no puede auditarlo. Su versión, wheel y archivos instalados se comprueban por separado; no se afirma cobertura SCA del modelo. Los mensajes ERROR del log de pruebas pertenecen a fallos inyectados deliberadamente y no sustituyen el resultado del runner.

El banco histórico de 50 casos×3 usa su fixture HTTP sintético explícito; no mide calidad de modelos ni eficacia del detector. Los bancos nuevos con detector CPU real se conservan en [lote final local](../pilot-local-final-20261003-01/README.md). No se suman suites parciales solapadas.

Los cambios posteriores `4494e85`/`d63731a` afectan atributos Git y bytes congelados de JSON, sin cambiar runtime ni expectativas. Se verificaron con export limpio y prueba focal del [corpus](../pilot-corpus-export-20261003-01/README.md). No se repitió toda la suite por empaquetado/documentación. No hubo CI remoto, gasto de producto, publicación ni migración de base de usuario.
