# Evidencia local de la tarea 54

La [tarea](../../../docs/plan-blackhat/tareas/54-agente-escrituras-y-piloto.md)
detalla implementación, versiones y límites. El
[runbook](../../../ops/agent_chat/EXPORT_RUNBOOK.md) describe arranque, parada,
recuperación y rollback. No hay piloto, cuenta externa ni modelo pagado activos.

- Regresiones: `agent-final.result.json` / `.log` (73 OK),
  `governance-final.result.json` / `.log` (196 OK),
  `export-receipt-final.result.json` / `.log` (13 OK tras corregir el recibo).
- SDK oficial: `sdk/proof.json`; modelo y sandbox simulados en este ensayo.
- E2B real + HTTP + Drive simulado: `final-live/task54-live/report.json`,
  `export-live-second.log`, `operational.log` y
  `final-live/task54-ops/live-cases.json`. Red real en `executor-network-build.log`.
- Corpus final: `final-live/task54-corpus2/report.json`, archivos y galerías.
  7 correctos, 8 no soportados, 1 fallo: gráfico XLSX ausente. Son helpers
  offline reales, sin modelo ni prueba generativa. `visual-review.json` vincula
  los 21 previews inspeccionados a sus hashes.
- Plan generativo preparado: `final-live/task54-corpus2/generative-plan.json`;
  autorización de proveedor/modelo/gasto pendiente.
- UI final: `ui-confirmed-final-desktop.jpg`, propuestas de escritorio/móvil;
  `ui-live/task54-ui-final/ui-proof.json` registra una sola nueva creación
  simulada, SHA y recibo verificados. Auditoría de prompts en los dos directorios
  `task54-ui-*`. Ningún token/ID de Drive/destino original va al modelo.
- Integridad: `evidence-integrity-final.log` verifica 257 hashes contra los bytes
  staged de las tres instantáneas. `live` conserva el corpus inicial;
  `final-live` la segunda ejecución; `ui-live` la captura posterior a revisar UI.
- Parada: `cleanup-second.log`; red/contenedores del laboratorio retirados,
  túneles y PostgreSQL aislado detenidos, VM apagada normalmente con volumen
  e imágenes conservados. Continúa el límite histórico NoNewPrivs=0 de E2B.

Los intentos fallidos se conservan y no cuentan como éxitos. Los logs son datos
diagnósticos crudos; sus espacios y finales de línea son evidencia, no código.
