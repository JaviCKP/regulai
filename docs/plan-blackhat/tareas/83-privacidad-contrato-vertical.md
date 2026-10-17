# 83 — E1 — Prueba vertical del contrato

Status: completada (prueba vertical aislada, no integración de producción).
Blocked by: ninguno.

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E1 y criterios de la sección 11.

Aceptación: Correo y nombre sintéticos ausentes en el transporte HTTP capturado; proyección equivalente para todos los cortes de bytes y caracteres. Sin cambiar políticas.

Verificación observada: 4 pruebas OK en `front.test_privacy_vertical`, Django 5.2.17/Python 3.12.11, SQLite únicamente en memoria. SDK OpenAI con `httpx.MockTransport`, cero red real: cuerpo, URL y cabeceras sin nombre/correo; 100 tokens entrada y 20 salida conservados. Cada corte UTF-8 y carácter, byte a byte, alias contiguos, Unicode, referencias inválidas/incompletas, no recursividad y consumidores independientes. Política de empresa vacía antes y después. Captura sintética: `output/privacy-20261017/e1-http-fixture.json`.

Contrato precisado: `privacy_projection.py` es sólo un codec interno de presentación; recibir un mapa no autoriza revelación. E2/E5 deben suministrar únicamente el conjunto de la inferencia autorizada y revalidar cada lote. Los segmentos llevan offsets UTF-8 canónicos y tipo `original` para que el renderer no los interprete como Markdown. No hay ruta de producción conectada todavía.
