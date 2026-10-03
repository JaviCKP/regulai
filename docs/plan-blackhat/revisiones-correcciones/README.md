# Revisiones independientes de las correcciones

Los informes se conservan íntegros, sin fusionar ni reordenar los hallazgos entre ejes. Cada revisor Spec es un SOL GPT6.1 HIGH nuevo, distinto del implementador; Standards es otro revisor independiente. Aplicaron la skill `code-review` sobre la base fija `4400f0b` y el checkout inmutable `9549e74`. Las líneas y enlaces de esos informes corresponden a ese checkout, anterior a las correcciones posteriores. El [manifiesto](manifest.json) conserva sus hashes.

## Eje Standards

[Informe original](standards.md). Su hallazgo sobre pérdida de límites del historial se reprodujo en exportación y carga HTTP y quedó corregido en `f778336`. Las dos aserciones también fallan en `4400f0b`; la prueba se ajustó en `865e8cb` para que un campo ausente falle como aserción de comportamiento, no como error de preparación.

## Eje Spec

| Carril | Informe original | Seguimiento posterior a la reproducción |
| --- | --- | --- |
| P | [Pipeline](spec-P.md) | `a02f483`, `f8b5ba3`, `95dfb77`: destinos obligatorios e identidad de máscaras antes de generar; suelo unknown compartido con simulador. Cuatro regresiones, diez aserciones rojas y cero errores en la revisión anterior; integradas en verde. |
| D | [Documentos](spec-D.md) | `f92d5a1`, `520fa3a`, `5701a10`, `4cd129f`, `90000c6`: imágenes PDF inline, filas Word borradas, CSV irregular y reinicio decimal. Doce regresiones, veintidós aserciones rojas y cero errores; integradas en verde. |
| V | [Verificación y conectores](spec-V.md) | Sin defecto técnico nuevo. Corregir unidades de precio en documentación, carril R. |
| C | [Clasificación](spec-C.md) | `d4e1313`, `9840bd6`: calidad mínima también para una única tarea plausible e instrucción de aclaración para todos los avisos de ambigüedad. Tres probes independientes rojos, después verdes. |
| S | [Seguridad](spec-S.md) | `e7311bf`: alternar enmascarado exige POST/CSRF, probado con GET405, POST sin token403, POST válido302 y empresa ajena404. Procedimiento de rotación documental pendiente R. |
| F | [Interfaz](spec-F.md) | Pérdida de límites duplicada con Standards, resuelta en `f778336`. Identificación del motor real en la ficha en corrección. |
| O | [Onboarding y datos](spec-O.md) | Reproducida exposición del departamento de otra empresa en listados y filtros Prompt/Alert tras traslado del usuario; en corrección. Los controles adicionales de 2.005 filas y política inicial pasan. |
| Q | [Operación y CI](spec-Q.md) | Reproducido código de salida 0 con 52 controles fallidos de una copia development del banco, cero casos reserved; en corrección. |

Las pruebas usaron bases aisladas y transportes sintéticos. No hubo llamadas reales a proveedores/Jev, publicación ni ejecución de CI remoto. La revisión R se añadirá después de actualizar la documentación.
