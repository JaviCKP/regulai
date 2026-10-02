# Jev mediante Vercel AI Gateway

Contrato comprobado el 2 de octubre de 2026. Vercel ofrece una [ruta compatible con TypeSafe](https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe): `POST https://ai-gateway.vercel.sh/typesafe/v1/systemone`, autenticada con la clave de **AI Gateway**. Conserva `noul`, `choice`, `score` y los contadores `input_tokens`/`output_tokens`.

Invocación del cliente existente:

```python
result = evaluate(company.jev_api_key, 'typesafe-ai/jev', state, questions, transport='vercel')
```

El transporte directo sigue usando una clave TypeSafe y una versión `jev-X.Y.Z`. La credencial de Vercel nunca debe enviarse al endpoint directo. La autorización local debe cubrir Vercel y TypeSafe antes de cualquier envío. El cliente fija ambos endpoints y limita el proveedor a `typesafe-ai`; no solicita fallbacks.

El [catálogo público](https://ai-gateway.vercel.sh/v1/models) devuelve `typesafe-ai/jev`, tarifa de entrada USD 0,000000042/token, salida USD 0/token, `zdr: none` y `no_training: all`. Estos valores se gestionan separadamente de la clave.

Gateway devuelve el identificador `typesafe-ai/jev`; el contrato no fija ni comunica la versión interna de Jev. Registrar ese identificador y repetir la calibración cuando cambie el servicio. Los metadatos monetarios comunicados se conservan en `JevResult.provider_metadata` tras validación.

El parser acepta los campos de envoltura `provider_metadata` y `providerMetadata`, valida ambos con las mismas reglas y rechaza conflictos si aparecen juntos. La regresión falló primero y pasó tras corregirla; el informe offline final 04 registra hashes del código probado. No se infiere coste cero de metadatos ausentes.

Las pruebas locales simulan HTTP. Un catálogo público o un contrato válido no prueban que esta cuenta tenga acceso ni demuestran calidad semántica. La prueba real requiere el presupuesto compartido configurado por la orquestación.

## Resultado de acceso real — 2 de octubre de 2026

Tres intentos sintéticos reales recibieron HTTP 403. El diagnóstico explícito fue «Free tier users do not have access to this model. Upgrade to paid credits…», con `providerAttempts: 0`. No se obtuvo una evaluación semántica real. No se harán nuevos intentos ni compras/recargas automáticas.

El presupuesto conjunto autorizado era 1 USD, registrado persistentemente en `.claude/real-provider-budget.sqlite3`. Se conservan 0,03 USD de reservas inciertas por esos intentos: no son coste confirmado ni cero. El [export final seguro](../../evals/reports/real-budget-2026-10-02.json) incluye las tres reservas, el diagnóstico y la estimación DeepSeek de 0,00000870 USD. Los informes reales 01/02 registran los dos primeros; el tercero diagnosticó el acceso de cuenta. [Resultados y pendientes](estado-ejecucion.md), incluida calibración y respuesta documental con citas de extremo a extremo en vivo.
