# Adaptación del preflight a Vercel

Implementación integrada en `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`. Este paquete conserva sin cambiar bytes los cuatro informes originales de C; [inventario](files.json) y [script de copia](package.py).

Dos fallos reproducidos antes de corregir: rechazo de la combinación Vercel autorizada y descripción de respuestas vivas como fixtures. [Rojo/verde](tdd-results.json): cuatro pruebas nuevas correctas; [suite focal](focal-results.json): 45 pruebas, exit 0, 32,511 s. La captura del primer rojo conserva comando, código y aserción, no un log completo. Los demás resultados conservan la salida disponible; la suite completa posterior conserva su log íntegro.

Se admite una lista de dos combinaciones exactas endpoint/transporte/modelo; las mezclas y otros hosts se rechazan antes de cualquier salida. Los tests capturan los transportes HTTP reales sustituidos por dobles locales y prohíben sockets. Comprueban `only=[typesafe-ai]`, uso/coste comunicado por Gateway, reserva compartida y API local cero.

[Delta y fuentes oficiales](manifest-delta.json) conserva precios, endpoint, alias mutable y límites. Es una propuesta técnica del agente, no una autorización. La [autorización efectiva](../pilot-real-vercel-20261003-01/authorization.json) deriva exclusivamente de las respuestas del usuario y cubre ocho casos × tres configuraciones, hasta 1 USD. No se hicieron llamadas de producto en estas pruebas.
