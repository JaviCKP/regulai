# Operación final con detector local real

Las ejecuciones09 y10 terminaron exit0. La10 incluye los correctores `be29b6f` y `0957df4`: [resultado](../pilot-operations-20261003-10/result.json), [fuentes](../pilot-operations-20261003-10/source-manifest.json) y [órdenes/hashes](../pilot-operations-20261003-10/commands.json). **117 tests PostgreSQL OK en17,185s, una omisión exclusiva de SQLite**. La09 conserva114 tests/19,251s, anteriores a los últimos correctores.

En ambas se instaló el modelo local real en Linux y se comprobó API0 antes del SDK con transporte sintético, sin llamar a ningún enmascarador HTTP. Pasaron check --deploy, HTTPS loopback, cookies/hosts, estáticos, permisos de archivos privados, aislamiento Alpha/Beta, doble envío, desconexión y terminación real de Gunicorn durante una llamada. La recuperación mantiene outcome_unknown y coste externo null, sin reenvío.

Backup/restauración y reversión compararon27 tablas, dos medios y claves, con descifrado observado. Recifrado nuevo, lectura sin fallback y conflicto con escritor PostgreSQL real pasaron. Se conservaron copias privadas sintéticas fuera de Git. La lectura inicial de disponibilidad de PostgreSQL devuelve2 antes de estar listo y después0; es sondeo esperado, no un test omitido.

El [verificador](verify_evidence.py) amplía la comprobación anterior con el nuevo email sintético: [10 ejecuciones conservadas](verification.json), hashes de cada log correctos y0 coincidencias de claves/marcadores en logs. Los recursos temporales identificados por `regulai.synthetic-lab` y las imágenes `regulai-lab-*` fueron retirados; se comprueba nuevamente durante el cierre global.

No hubo proveedores vivos, exposición pública, participantes ni CI remoto. El laboratorio de loopback no acredita una instalación pública ni recuperación en otra máquina. Los intentos01–08 se conservan y están descritos en los resúmenes previos.
