# Spec review

Base `21bdd9f444024e2da76c826c0d0432090e555010`; revisión `df91ea1dacbe1662d392bfd91417d32a0e46abe6`; corrección comprobada `128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2`.

**Sin hallazgos abiertos en el delta final. Un P2 reproducido y corregido.** En `extend_pilot_authorization.py:25–30,35–46`, df91ea1 registraba una aprobación nueva aparecida durante la espera del lock, pero informaba del digest anterior. Contradecía la extensión explícita y auditable solicitada. `independent_cases.py` reprodujo el fallo; 128d66a rechaza la sustitución antes de mutar. La misma prueba exige excepción y ledger byte-idéntico; no se relajó el criterio.

Preservación comprobada: ancla y llamadas anteriores, cap conjunto, exposición `0.013858062`, reserva incierta `0.003`, rechazo de cabeza/predecesor incorrectos, caller antiguo, renovación implícita y bifurcación; pasada única y límite de llamadas. La expiración posterior a reservar deja `not_started/not_incurred`, cero transporte y pasada consumida. Revocar durante el lock no registra nada.

Pruebas frescas: 12 tests del cambio y 3 probes independientes en df91ea1: **14 verdes, un rojo P2**. Los 3 probes pasan en 128d66a. Detector real: **37/44** casos, **27/32** anotaciones sensibles eliminadas y **61/66** preservadas. Cinco casos × dos fixtures × tres HTTP: **27/30** controles; los tres fallos INJ-05 neutral son `quote_not_found`, con abstención segura. PII-03 conserva el DNI separado en seis transportes simulados. Se retienen pérdidas PII-12/DOC-08; control operativo y privacidad no se confunden. No repetí los 264 recorridos completos del implementador.

Corpus íntegro; fixtures estáticos y ausencia de medición semántica explícitos. Los dos ejemplos literales corresponden a [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html); las adaptaciones no se presentan como bypasses vivos.

Pack `80d336bd…`: cuatro casos exactos, oráculos separados, función `credentials_readonly` idéntica al original; guardia pendiente anterior a su llamada, hashes/constantes coherentes, `approved=false`, aprobado inexistente. Máximo 44 llamadas, `0.884` adicional y `0.897858062` conjunto. Inspección estática solamente.

Recomiendo presentar ese paquete exacto para aprobación humana. No autorizo ejecución ni cierro calidad/calibración. Solo SQLite sintética propia/memoria, `local_settings` vacío antes de Django y entorno construido sin copiar el del usuario; cero red de producto, claves, BD del usuario, puente o ledger real. Causa histórica incierta intacta. Comandos, resultados, hashes y límites: `evidence.json`.
