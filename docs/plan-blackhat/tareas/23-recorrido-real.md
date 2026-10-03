# 23: Preparar y autorizar un recorrido real acotado

**Status:** pending external validation — preparación técnica local implementada
**Blocked by:** revisión humana de límites del detector local, acceso TypeSafe directo, revisión vigente de tarifas/versiones y autorización nueva explícita
**Specification:** [05](../05-clasificacion-documental.md), [06](../06-enrutamiento-modelos.md), [07](../07-verificacion-y-escalado.md), [11](../11-evaluacion-reproducible.md), [12](../12-demo-y-salida.md).

- [x] Ocho casos sintéticos versionados; éxito, bloqueo, consentimiento, evidencia ausente, fallo de verificación y segundo intento cuando proceda.
- [x] Smoke y evaluación utilizan el servicio real, observer previo al transporte y ledger común persistente; offline por defecto.
- [x] Preservar llamadas fallidas/descartadas, costes estimados/comunicados/reservas inciertas y saldo después de reiniciar.
- [x] Autorización histórica sustituida por plantilla nueva **pendiente** ligada a datos/destinos/acciones/hashes/ventana/techo; ninguna aprobación creada.
- [x] Manifiesto con orden/semilla, configuraciones, rúbricas, fuentes y versiones; preflight de cambios sin red.
- [x] Propuesta con detector local real en CPU, backend/modelo/versiones/hash fijados, sin endpoint ni coste de API; HTTP previo conservado como compatibilidad.
- [x] Gate focal final 40 tests OK y ensayo local 24 recorridos/24 controles; 38 transformaciones locales y 54 llamadas simuladas, cero llamadas reales. SEC-1 y costes externos inciertos conservados.
- [ ] Revisar los errores/omisiones del detector en datos representativos; las pruebas sintéticas no establecen anonimización completa.
- [ ] Acceso y cota actualizados en los destinos exactos; el Gateway histórico no demuestra TypeSafe directo.
- [ ] Ejecutar el piloto vivo bajo autorización explícita y preservar resultados, incluso fracaso o parada.

[Propuesta exacta, dependencias y recuperación](../ejecucion-real-y-calibracion-piloto.md). [Evidencia del detector local](../../../evals/reports/pilot-evaluation-local-20261003-01/README.md), [histórico con máscara simulada](../../../evals/reports/pilot-evaluation-20261003-01/README.md). No se ha gastado en APIs, recargado crédito, tocado una base del usuario, publicado ni desplegado. Las expectativas de fallo/escalado se fuerzan solo en los fixtures offline; no se presentan como conducta viva del proveedor. Las transformaciones locales se trazan aparte y no inflan llamadas externas; techo compartido 1 USD sin ampliación.
