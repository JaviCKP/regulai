# Verificación final de operación local, 3 de octubre de 2026

Esta revisión vuelve a comprobar las ocho ejecuciones conservadas; no ejecuta
otro laboratorio, no despliega y no repite la suite. La evidencia 01–07 y su
[resumen anterior](../pilot-operations-20261003-summary/README.md) permanecen intactos.

## Ejecución 08

[Resultado](../pilot-operations-20261003-08/result.json),
[comandos](../pilot-operations-20261003-08/commands.json) y
[fuentes exactas](../pilot-operations-20261003-08/source-manifest.json).
HEAD registrado: `87311294631d9ffdf6b76ccf3fcb9140018a0977`; el manifiesto identifica
los bytes efectivos. El ejecutor de la ejecución terminó con exit 0.

- **84 tests PostgreSQL**, 12,128 s, `OK (skipped=1)`. El comando del contenedor
  tardó 15,453 s y terminó con exit 0. La omisión corresponde a
  `test_skipped_compare_and_swap_update_aborts_and_rolls_back`, cuyo trigger es
  exclusivo de SQLite; se ensayó además un escritor PostgreSQL real y el aborto
  atómico del recifrado.
- Restauración exacta del inventario y hashes de **27 tablas y dos archivos**;
  credenciales sintéticas legibles. La reversión del dump y claves volvió a
  coincidir. La lectura tras rotación con la nueva clave sola también pasó.
- Reinicio durante una llamada: `outcome_unknown`, `success=false`, generación
  `started`, coste `null` y total ausente. La comprobación de no reenvío y las
  demás ocho puertas constan como verdaderas en `result.json`.
- Los 67 comandos están conservados. El primer sondeo de disponibilidad de la
  base (`db-ready-0.log`) devolvió 2 antes de estar lista; el siguiente y todos
  los comandos posteriores terminaron con 0. No se oculta ese sondeo inicial
  ni se presenta como fallo de la suite.

Las ejecuciones 06/07 ya habían completado 82 tests cada una, con una omisión
SQLite. El endpoint supervisado de un segundo pertenece a 07. Los intentos 01–05
conservan sus fallos y resultados parciales; no se convierten en pases por el
resultado posterior de 08.

## Verificación independiente de los archivos

Se copió sin cambios el verificador anterior al directorio nuevo. SHA256 del
script: `ac62d02396c25c86a6221269b2338433d0974edbf8c4fc283a187d926dab9d2f`.

```powershell
rtk proxy .venv/Scripts/python.exe -X utf8 evals/reports/pilot-operations-20261003-summary-final/verify_evidence.py
```

Exit 0: **8 ejecuciones**, todos los hashes de logs coinciden y **0 coincidencias**
de claves sintéticas o marcadores sensibles en los logs. [verification.json](verification.json)
conserva las comprobaciones y hashes por ejecución. El verificador rechaza
sobrescribir su salida; repetir en otro directorio nuevo si se necesita otra
ejecución. [verification-run.json](verification-run.json) registra este comando.

La [revisión adicional](secret-review.json) comparó 24 claves sintéticas conocidas
en memoria contra 440 archivos de texto de operaciones y seguimiento UI,
incluidos manifiestos de comandos y JSON: cero coincidencias. Tampoco encontró
bloques PEM de clave privada. No se emitieron claves; no se afirma detección
general de secretos ni OCR automático de capturas.

## Recursos y límites

Las órdenes `verify-owned-*` y `remove-owned-*` de 08 terminaron con exit 0.
Las consultas Docker posteriores por etiqueta `regulai.synthetic-lab` y por
identidad exacta `regulai-lab-43a3f7dd8eed` devolvieron salida vacía y exit 0
para contenedores, redes, volúmenes e imagen temporal. Las carpetas privadas y
backups sintéticos se conservaron; no se borró ni inspeccionó contenido de bases
de usuario. [inspection.json](inspection.json) resume recuperación y limpieza.

La revisión es local: cero llamadas a proveedores reales, sin CI remoto,
despliegue público, nuevos ensayos humanos ni caída de la máquina completa.
El enmascarador sintético sustituye un marcador exacto; no acredita capacidad
general de detección. [Procedimiento y límites](../../../docs/plan-blackhat/operacion-y-recuperacion-piloto.md).

`evidence-sha256.json` registra todos los archivos de este resumen salvo el
propio índice. Los informes fuente se verifican mediante `verification.json`.
