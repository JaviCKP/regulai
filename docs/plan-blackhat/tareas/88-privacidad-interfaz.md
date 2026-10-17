# 88 — E6 — Configuración e inspector

Status: completada; validación visual local cerrada.
Blocked by: [87](87-privacidad-proyeccion-replay.md).

Especificación: [protección reversible](../plan-tokenizacion-reversible-20261017.md), entrega E6 y criterios de la sección 11.

Aceptación: Configuración, inspector, previsualización, selección y copia protegida en la isla; teclado, móvil y accesibilidad verificados.

Verificación observada: configuración firmada, inspector con originales bajo demanda, recuentos por turno, previsualización, selección y copia/exportación. AI Elements y React Bits adaptados con licencias. Diseño corregido a petición del usuario: etiquetas breves, filas discretas y detalles cerrados. 24 capturas finales a 360/768/1440, copia natural/protegida y recarga; revisión independiente de teclado, foco, Escape, temas y movimiento reducido sin hallazgos abiertos. [Evidencias](../entrega-privacidad-20261017.md). Datos sintéticos; sin activación real.

Seguimiento 17/10: opciones «DNI / NIE» y «Cuentas / IBAN» explícitas; ejemplo ficticio de las cinco categorías habituales. Nueva prueba HTTP de simulación → activación firmada → lectura persistida → preview de correo, DNI, NIE, teléfono, IBAN y tarjeta, sin modelos. Desactivar la recuperación de DNI conserva D2. 16 pruebas focales y 49 frontend, typecheck/build pasan. Build `main-BfZaF43Y.js`. Este cambio de etiquetas no se verificó de nuevo visualmente: el control del navegador rechazó localhost por su política de URL. Se deja arrancada la demo sintética 8893 para el usuario.
