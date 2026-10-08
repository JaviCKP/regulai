# Evidencia de la tarea 49 — 7 de octubre de 2026

Implementación y límites en [la tarea 49](../../../docs/plan-blackhat/tareas/49-agente-inferencia-y-datos.md).
Todo el contenido de las pruebas es sintético. No hubo inferencias de pago.

Resultados de referencia:

- `verified-governance.log` y `.result.json`: 176 regresiones, OK; tres entradas HTTP,
  estado, presupuesto, privacidad y compatibilidad del chat.
- `verified-postgres.log` y `.result.json`: 19 pruebas de agente/estado, OK, sin omisiones;
  SDK aislado contra HTTP Django y SDK OpenAI real con transporte de proveedor simulado;
  concurrencia e idempotencia en PostgreSQL, alias y migración reversible.
- `final-sdk.log` y `.result.json`: cinco pruebas del SDK Deep Agents real contra HTTP
  interno simulado, incluidos compactación, resultados, errores y metadatos.
- `task48-recheck/`: las 15 pruebas originales de 48 repetidas con su lock intacto.
- `real-e2b-recheck/report.json`: repetición original sobre dos microVM Firecracker;
  filesystem, identidad, red IPv4/IPv6, cálculo y destrucción.
- `final-adapter-network.log`: adaptador nuevo en el host real preparado en 48.
  Destino interno permitido, receptores externos controlados inaccesibles y controles
  positivos. Su servidor HTTP es sintético: es evidencia de red, no de gobierno Django.
- `real-lab-final-checks.log`: comprobaciones de cierre de E2B.

Los logs anteriores registran iteraciones y errores ya corregidos. No sustituyen los
resultados de referencia. `final-agent-sqlite.log` incluye una omisión intencionada de
la prueba concurrente de PostgreSQL; la prueba real correspondiente pasa en
`verified-postgres.log`. No se acredita concurrencia mediante SQLite ni mocks de red.

Los comandos registrados en `.result.json` llevan el prefijo `rtk`. `run_checks.py`
captura stdout/stderr sin la recodificación de PowerShell. Los IDs de modelos,
claves de fixtures y direcciones son sintéticos o pertenecen al laboratorio local.
