# 29 — Ensayo autorizado mediante Vercel

Status: en ejecución. Blocked by: revisión del commit fijo, preflight y puertas finales antes de las llamadas.

Propietario: orquestador; adaptación del ejecutor por C (Astra Max); revisión independiente por Security (Astra Max).

Especificación: [recorrido real](23-recorrido-real.md), [ejecución y calibración](../ejecucion-real-y-calibracion-piloto.md), [plan 07](../07-verificacion-y-escalado.md) y [plan 11](../11-evaluacion-reproducible.md). Se conserva el banco y las rúbricas existentes.

El usuario autorizó hasta 1 USD para ocho casos sintéticos en economy, strong y router y después indicó usar Jev por Vercel. El permiso cubre el destino `https://ai-gateway.vercel.sh/typesafe/v1/systemone`, con `typesafe-ai/jev` y `only: [typesafe-ai]`, además de DeepSeek. No comprende el banco humano ni un despliegue. La ventana se limita al 3 de octubre de 2026 hasta las 23:59:59 UTC, dentro de las 24 horas aprobadas. El alias de Gateway no permite fijar pesos inmutables.

## Aceptación

- [x] Reutilizar el conector existente y aceptar solamente las dos combinaciones exactas de endpoint, transporte y modelo documentadas; bloquear mezclas antes de red o DB.
- [x] Conservar la reserva antes de llamar, el ledger conjunto, el límite de 1 USD y las reservas inciertas.
- [x] Leer únicamente las credenciales existentes de una misma empresa mediante SQLite `mode=ro`, pasarlas al entorno del hijo aislado y excluirlas de argumentos e informes.
- [ ] Revisar independientemente el commit fijo, con pruebas sin red.
- [ ] Ejecutar preflight satisfactorio y las cinco puertas sobre el código integrado.
- [ ] Ejecutar una vez el ensayo aprobado; conservar cualquier parada y no repetir llamadas inciertas.
- [ ] Informar resultados, costes estimados/comunicados/inciertos y limitaciones; no atribuir calidad semántica sin revisión humana.

## Verificación observada

C reprodujo dos fallos antes de corregirlos: rechazo del destino Gateway autorizado y texto de informe real que lo describía como simulación. Cuatro pruebas nuevas y las 45 pruebas focalizadas pasan (32,511 s); cero llamadas de producto en esas pruebas. Evidencia original en `.claude/vercel-preflight/`, pendiente de incorporar al paquete final.

La preparación directa anterior no abrió el ledger ni realizó llamadas; queda sustituida por la indicación explícita de usar Vercel. [Autorización y puente](../../../evals/reports/pilot-real-vercel-20261003-01/) conservan la preparación vinculada al hash exacto del manifiesto.
