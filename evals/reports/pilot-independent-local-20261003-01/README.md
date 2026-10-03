# Revisiones independientes del backend local

Nuevos subagentes `gpt-6-astra`, esfuerzo `max`, contexto nuevo, distintos de los implementadores. Seguridad y Spec revisaron snapshots fijos; no se cuenta la autorrevisión como independencia. La [tanda previa](../pilot-independent-reviews-20261003-01/README.md) conserva Standards/Spec/Security del cierre D2 anterior.

| Revisión | Commit y resultado |
| --- | --- |
| [Seguridad inicial](../../../docs/plan-blackhat/revisiones-piloto/security-local-c85d019.md) | c85d019: reproduce P1 numéricos JSON y P2 rollback, con capturas SDK/MigrationExecutor |
| [Seguridad de cierre](../../../docs/plan-blackhat/revisiones-piloto/security-local-0957df4.md) | 0957df4: mismas PoCs sin cambios verdes; 68 métodos de regresión y14 propios, cero red viva; ambos hallazgos cerrados |
| [Spec](../../../docs/plan-blackhat/revisiones-piloto/spec-local-d63731a.md) | da836e3 y0957df4: requisitos/controles independientes correctos; P2 de export del corpus cerrado en d63731a; cero hallazgos abiertos |

`package-files.json` registra origen, bytes y SHA256 de cada copia. `original-reports/` conserva el dictamen exacto recibido. Las versiones de `docs/` solo sustituyen enlaces al scratch por enlaces a la evidencia conservada, sin cambiar hallazgos o conclusiones. No se empaquetan ZIP/checkouts completos, cachés ni bases.

Para repetir, reconstruir snapshots de los commits declarados y copiar los scripts del equipo a `.claude/review-local-security/` o `.claude/review-local-spec/`; seguir las órdenes de sus resultados. Los exportadores y manifiestos fijan fuentes/entorno. Usar un directorio de ejecución nuevo para no sobrescribir evidencia. Los tests bloquean la red de producto y utilizan únicamente datos sintéticos.

Se conservan también fallos del arnés, reproducciones rojas y ejecución parcial de be29b6f. El falso positivo observado sobre `card` y las limitaciones NER/plazo cooperativo están documentados. No son pruebas de calidad humana, Office, infraestructura pública o proveedores vivos. Seguridad no repitió PostgreSQL ni navegador: sus resultados están identificados por separado en operación y UI.
