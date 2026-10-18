# Chat 12: ejecución, recuperación y continuación corregidas

Aplicado y verificado localmente el 18 de octubre de 2026. Los informes de
activación y verificación identifican las imágenes y confirman conservación de
datos, claves, configuración privada y checkpoints, sin llamadas al proveedor.

## Corrección

- El lector de resultados acepta JSON puro y el envoltorio exacto del SDK fijado,
  comprobando concordancia del código de salida. No acepta texto añadido arbitrario
  ni convierte errores de ejecución o truncamientos en éxito. La paginación usa el
  mismo lector. Los prompts 17 y 19 ya tenían resultados completos con exit_code 0.
- Los checkpoints de workspace generado pueden almacenarse cifrados y recuperarse
  por el ejecutor privado. Requieren versión 2, sandbox vinculado y ausencia de
  adjuntos originales, revisiones base o referencias a archivos anteriores. El
  servidor emite el marcador private_executor; el cliente no puede declararlo.
  La estructura/tamaño/rutas del ZIP se validan al guardar y recuperar. No se añade
  ningún bloque binario al proveedor: mensajes y resultados mantienen protección,
  YARA y autorización actual. Las demás prohibiciones de canales binarios siguen.
- «sigue» o «continúa» puede seleccionar la última petición propia fallida con
  delivery_incomplete y resultados completos de execute registrados. No incluye
  respuestas fallidas como respuestas válidas, datos de otras cuentas, archivos
  originales, efectos externos ni operaciones/inferencias inciertas. Los resultados
  son contexto de datos no confiables, no autoridad para repetir comandos. Se fijan
  identidad/digest en el snapshot y se revalidan en cada frontera. Se conservan los
  límites de historial y capacidad. No se crea ninguna operación de ejecución al
  seleccionar ese contexto.

El probe de la imagen candidata sobre el chat existente fue sólo lectura: reconoce
ambos resultados y selecciona el prompt 19 para continuar. No cambia los intentos
fallidos, sus costes, ni reenvía la simulación. El usuario puede escribir «sigue»
en el chat 12; la respuesta real posterior sigue dependiendo del proveedor.

## Verificación

Suite final PostgreSQL aislado: 187 ejecuciones de pruebas,
cero fallos, errores u omisiones (`tests-3.json`). SDK: 28
pruebas, cero fallos, errores u omisiones (`sdk-tests-3.json`), en contenedor sin red.
Se prueban las tres entradas HTTP con continuación, inferencia simulada, contenido
sensible oculto en la petición real al conector y finalización. También se cubren
YARA, revocación, aislamiento, recuperación, replay, dinero y checkpoints. Los
totales incluyen métodos heredados de fixtures; no representan casos únicos.

La suite exploratoria ampliada (`tests-0.json`) tuvo seis errores de fixtures:
tres archivos de evidencia ausentes, dos expectativas del formato de herramientas
anterior y un checkpoint sin referencia de skills. Se reprodujeron los mismos seis
errores con la imagen anterior (`baseline-fixture-check.txt`); no se atribuye a esa
suite un resultado verde. La suite final selecciona controles vigentes y las nuevas
regresiones. Una carrera del fixture SDK permitía pedir un tercer trabajo mientras
terminaba el único trabajo simulado; se fijó su concurrencia en 1 para probar de
forma determinista el backoff. No cambia la concurrencia instalada.

No se usó un proveedor de pago ni un sandbox de pago para verificar. No se afirma
una nueva mejora de latencia o de calidad del modelo. Se conservan las dos
optimizaciones de latencia anteriores. No hay migraciones ni cambios de políticas,
modelos, máscaras, límites instalados o interfaz.

## Operación local

Desde `C:\Users\javi\Documents\Codex\regulai-privacy`:

```powershell
rtk proxy python ops/agent_chat/chat12_local.py verify
rtk proxy python ops/agent_chat/chat12_local.py tests --round 10
rtk proxy python ops/agent_chat/chat12_local.py sdk-tests --round 10
rtk proxy python ops/agent_chat/chat12_local.py rollback
```

`rollback` cambia efectivamente los servicios y exige ausencia de trabajos activos.
Vuelve a las imágenes de la segunda optimización de latencia, preservando los datos
y claves actuales; no restaura la base sobre datos nuevos. El stage privado con las
copias y originales es `/opt/regulai/updates/chat12-20261018-a1`. La preparación no
modifica datos vivos y los tests usan bases aisladas eliminadas al terminar. Los
contenedores temporales de prueba se ejecutan con --rm. Los informes y respaldos
se conservan. No hubo push ni despliegue remoto.
