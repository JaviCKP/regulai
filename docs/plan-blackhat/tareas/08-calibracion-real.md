# 08: Calibración y comparación real pendientes

**Status:** blocked (externo)
**Blocked by:** acceso Jev de la cuenta Gateway y autorización explícita de nuevas pruebas/compras
**Specification:** [05](../05-clasificacion-documental.md), [06](../06-enrutamiento-modelos.md), [07](../07-verificacion-y-escalado.md), [11](../11-evaluacion-reproducible.md).

- [x] Smoke sintético real DeepSeek: `2 + 2` → `4`, 25 tokens de entrada/1 salida, estimación superior 0,00000870 USD.
- [x] Presupuesto conjunto 1 USD con registro persistente; tres 403 Jev diagnosticados y 0,03 USD reservados como inciertos.
- [ ] Obtener acceso real autorizado sin recarga ni compra automática.
- [ ] Calibrar sensibilidad/juez con casos representativos y conjunto humano reservado independiente.
- [ ] Comparar economy/strong/router con todas las llamadas y citas verificadas en vivo; medir calidad y ahorro reales.

Resultado Gateway: «Free tier users do not have access to this model. Upgrade to paid credits…», `providerAttempts: 0`. No se planifican más llamadas Jev. Los dos informes smoke y el diagnóstico se describen en [estado observado](../estado-ejecucion.md); no documentar credenciales.

[Export final seguro](../../../evals/reports/real-budget-2026-10-02.json): límite 1 USD, estimación conocida 0,00000870 USD y reservas inciertas 0,03 USD. Simulador/smoke/presupuesto: 21 pruebas correctas (14+6+1); presupuesto concurrente y restauración segura de configuración probados sin red real.

El bloqueo no impide probar controles ni la demo offline; impide afirmar resultados de calidad/calibración/ahorro reales. No tratar el catálogo público como prueba de acceso de la cuenta.
