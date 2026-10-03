# 23: Preparar y autorizar un recorrido real acotado

**Status:** pending external validation — preparación técnica local implementada
**Blocked by:** URL/contrato/precio de máscara real, acceso TypeSafe directo, revisión vigente de tarifas/versiones y autorización nueva explícita
**Specification:** [05](../05-clasificacion-documental.md), [06](../06-enrutamiento-modelos.md), [07](../07-verificacion-y-escalado.md), [11](../11-evaluacion-reproducible.md), [12](../12-demo-y-salida.md).

- [x] Ocho casos sintéticos versionados; éxito, bloqueo, consentimiento, evidencia ausente, fallo de verificación y segundo intento cuando proceda.
- [x] Smoke y evaluación utilizan el servicio real, observer previo al transporte y ledger común persistente; offline por defecto.
- [x] Preservar llamadas fallidas/descartadas, costes estimados/comunicados/reservas inciertas y saldo después de reiniciar.
- [x] Autorización histórica sustituida por plantilla nueva **pendiente** ligada a datos/destinos/acciones/hashes/ventana/techo; ninguna aprobación creada.
- [x] Manifiesto con orden/semilla, configuraciones, rúbricas, fuentes y versiones; preflight de cambios sin red.
- [ ] Enmascarador real autorizado y probado con PII/secretos sintéticos; placeholder no es destino aprobado.
- [ ] Acceso y cota actualizados en los destinos exactos; el Gateway histórico no demuestra TypeSafe directo.
- [ ] Ejecutar el piloto vivo bajo autorización explícita y preservar resultados, incluso fracaso o parada.

[Propuesta exacta, dependencias y recuperación](../ejecucion-real-y-calibracion-piloto.md). [Evidencia local nueva](../../../evals/reports/pilot-evaluation-20261003-01/README.md). No se ha gastado en APIs, recargado crédito, tocado una base del usuario, publicado ni desplegado. Las expectativas de fallo/escalado se fuerzan solo en los fixtures offline; no se presentan como conducta viva del proveedor.
