# Spec review — Jev mediante Vercel

**Sin hallazgos abiertos ni cambios propuestos al producto.** Revisión independiente del delta `6668db4` → `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`, en export aislado; contrato: tarea 29, autorización de ocho casos × economy/strong/router y planes 07/11.

`evaluation.py:199–203` admite únicamente las tuplas exactas endpoint/transporte/modelo de TypeSafe directo y Vercel. Una matriz independiente de 12 combinaciones acepta las dos válidas y rechaza mezclas, HTTP, sufijos y host alternativo. El conector existente impone `only: [typesafe-ai]`; no se añadió transporte ni selección de proveedor alternativa.

`manifest-vercel.json` conserva dataset, rúbrica, semilla, configuraciones, umbrales, presupuesto total de 1 USD, cotas por llamada, máximo de intentos y límites. Ambos ejemplares tienen SHA256 `ff5a3056a6d13d7bc8a9c8baae559b002e201cc235be1a3aaa3cc4cd9e6e5b9d`, único hash de la autorización. El banco humano queda rechazado por hash, ámbito reservado y ausencia de revisión independiente. Se declara que el alias Gateway no fija los pesos subyacentes.

Las pruebas propias en las fronteras HTTP simuladas confirman: timeout de clasificación conserva 0,003 USD y para antes de generar; un coste estimado de 0,00001155 USD conserva la reserva de 0,003 USD; revocar la aprobación durante la máscara local impide Gateway y generador. Las transformaciones locales mantienen API cero. El nuevo texto del informe distingue ejecución real de fixtures sin atribuir calidad ni ahorro.

**Verificación fresca:** seis pruebas propias y cuatro nuevas del repositorio, 10/10 OK; regresiones de smoke/ledger, 21/21 OK. Ambos comandos terminan con código 0. Comandos y SHA256 de logs, fuentes, manifiestos y pruebas en `evidence.json`.

**Límites:** `run_authorized.py` y `prepare.py` solo se inspeccionaron estáticamente; no ejecuté el puente, no leí bases/credenciales del usuario ni hice llamadas vivas. Las pruebas usan SQLite aislado y respuestas prefijadas, con sockets/DNS bloqueados. No confirman disponibilidad del proveedor, factura ni calidad semántica real. Cambios realizados: únicamente pruebas e informe en `.claude/review-vercel-spec/`.
