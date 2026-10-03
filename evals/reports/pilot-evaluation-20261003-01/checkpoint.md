# Checkpoint C — 3 octubre 2026

Trabajo autorizado local; cero llamadas de producto. No autorización real nueva, no compra, no base del usuario, no push. Histórico del 2 de octubre conservado. Preparación C cerrada con snapshot de fuentes al 3 octubre; ver README/audit/gates y owned-files.json.

Implementados `evaluation.py`, ampliación de `EvaluationBudget`, `smoke_ai` compartido con `evaluate_ai`, fixtures de máscara para banco y demo, ensayo 8 casos y banco humano propuesto 24 casos (12 desarrollo / 12 reservados), rúbrica y etiquetas pendientes. Scripts preparan manifiesto nuevo y agregan revisiones humanas sin modelos.

Contrato con A: observer antes de cada transporte y después de cada estado; coste por procedencia; `not_started/not_incurred` permite liberar solo una llamada probada no iniciada. Raíz lleva documentación principal/operación. B usa helpers de demo en base nueva.

Evidencia final: 29 tests ampliados OK antes del último ajuste de contadores; 20 focalizados OK después, 12,811 s. Ensayos finales 24+72 runs offline, cero controles fallidos/cero llamadas reales/cero revisiones humanas. Fuente de ambos informes coincide con snapshot; check y diff-check exit0. No add/commit por C; raíz coordina índice y revisión independiente.

Dependencias reales: aprobación nueva ligada a hashes, destino de máscara HTTPS y contrato/precio comprobados, credenciales aisladas; TypeSafe directo `jev-1.13.0` sin acceso real comprobado. DeepSeek usa alias móviles con versiones publicadas, no fijación inmutable demostrada. Preflight bloquea todos esos supuestos. Fuentes oficiales consultadas 2026-10-03.
