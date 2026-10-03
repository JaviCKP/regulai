# Regresiones de alcance y presupuesto

`red.log`: ocho pruebas nuevas fallan antes de implementar la extensión explícita del ledger (salida 1).
La implementación se integró en `3756074`; preserva cap, ancla, llamadas, estimaciones y reservas inciertas,
rechaza otra cabeza y limita cada extensión a una pasada durable y su máximo de llamadas.

La revisión independiente de `df91ea1` encontró P2: el informe CLI podía usar el digest inicial aunque
durante la espera por el lock apareciera otra autorización válida y se registrara esa segunda.
`review-race-red.log` reproduce el fallo antes del arreglo, una aserción fallida, salida 1.
`128d66a` rechaza el cambio antes de insertar, dejando el ledger intacto.

Pruebas focales observadas: 41 en la integración inicial; 12 nuevas tras ampliar límites/concurrencia;
18 del módulo de extensión y ledger tras el arreglo P2. No se suman como pruebas distintas.
La [suite final conservada](../adversarial-gates-20261003-01/front-api.log) incluye las 13 regresiones finales
de extensión dentro de **400 tests correctos**, 169,896 segundos de suite, salida 0.

Todos los ledgers de estas pruebas son SQLite temporales sintéticas. No se abrió ni extendió el ledger real,
no se cerró su reserva incierta y no hubo llamadas pagadas. La aprobación humana del alcance nuevo continúa pendiente.
