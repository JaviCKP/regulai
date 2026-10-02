# Jev mediante Vercel AI Gateway

Contrato comprobado el 2 de octubre de 2026. Vercel ofrece una [ruta compatible con TypeSafe](https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe): `POST https://ai-gateway.vercel.sh/typesafe/v1/systemone`, autenticada con la clave de **AI Gateway**. Conserva `noul`, `choice`, `score` y los contadores `input_tokens`/`output_tokens`.

Invocación del cliente existente:

```python
result = evaluate(company.jev_api_key, 'typesafe-ai/jev', state, questions, transport='vercel')
```

El transporte directo sigue usando una clave TypeSafe y una versión `jev-X.Y.Z`. La credencial de Vercel nunca debe enviarse al endpoint directo. La autorización local debe cubrir Vercel y TypeSafe antes de cualquier envío. El cliente fija ambos endpoints y limita el proveedor a `typesafe-ai`; no solicita fallbacks.

El [catálogo público](https://ai-gateway.vercel.sh/v1/models) devuelve `typesafe-ai/jev`, tarifa de entrada USD 0,000000042/token, salida USD 0/token, `zdr: none` y `no_training: all`. Estos valores se gestionan separadamente de la clave.

Gateway devuelve el identificador `typesafe-ai/jev`; el contrato no fija ni comunica la versión interna de Jev. Registrar ese identificador y repetir la calibración cuando cambie el servicio. Los metadatos monetarios comunicados se conservan en `JevResult.provider_metadata` tras validación.

Las pruebas locales simulan HTTP. Un catálogo público o un contrato válido no prueban que esta cuenta tenga acceso ni demuestran calidad semántica. La prueba real requiere el presupuesto compartido configurado por la orquestación.
