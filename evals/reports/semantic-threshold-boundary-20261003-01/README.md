# Frontera inclusiva de verificación semántica

El caso vivo DOC-01/strong rechazó la respuesta tras superar las comprobaciones locales. Los cuatro
valores del juez fueron `claim_1=0.03`, `claim_2=0.03`, `failure_contradiction=0.13` y
`failure_omission=0.20`, con umbral configurado `0.8`. El límite inclusivo pretendido era `0.20`,
pero la resta binaria `1 - 0.8` dio `0.19999999999999996`. Esa diferencia fue suficiente para
marcar la omisión como fallida.

La evidencia viva original sigue intacta en
`evals/reports/adversarial-real-20261003-02/live-run-01/results.jsonl`, SHA256
`50c0cc9b092e79bb93326434ff8bcf222061e00993b4178328c70cd53a2f0d4e`.
No se cambiaron resultados, corpus, rúbricas, etiquetas, modelos ni umbrales para conseguir un resultado distinto.

## Cambio y contrato

`chat_service.py` calcula el complemento con `Decimal` a partir de la representación decimal de los
valores validados. Una única lista de señales que superan el límite determina tanto el estado como
la corrección enviada a un posible segundo intento. No se añade tolerancia.

`classification.py` tenía el mismo complemento y una compensación `+1e-12`. La regresión demuestra
que esa compensación aceptaba una masa de `0.20000000000000004` como si fuera `0.20`.
Ahora suma las masas decimales, incluida la masa desconocida asignada al nivel conservador, y compara
con el complemento decimal inclusivo. Las comparaciones directas de señales y confianza no cambian.
`verification.py` permanece intacto: el fallo estaba en la decisión semántica del pipeline.

| Masa/señal de fallo | Verificación, umbral 0.8 | Cola ordinal, umbral 0.8 y suelo public |
| --- | --- | --- |
| 0.19999999999999998 | Aceptada | public |
| 0.20 | Aceptada | public |
| 0.20000000000000004 | Rechazada | confidential |

## Pruebas conservadas

Los tests nuevos ejecutan el pipeline real de las tres entradas `/chat/send/`, `/api/chat/send/`
y `/chat/`, con dos citas válidas, parser real, validación real del juez y transportes sintéticos.
El generador y el enmascarador son fixtures explícitas. La prueba de reintento verifica que la
corrección solo nombra la señal situada por encima del límite. Clasificación usa su función real
`decide`; no se prueba una copia de la fórmula del producto.

| Fase | Comando desde la raíz | Resultado |
| --- | --- | --- |
| Rojo, antes del cambio | `rtk proxy .venv/Scripts/python.exe evals/reports/semantic-threshold-boundary-20261003-01/run_checks.py red` | Exit 1; 4 tests, 8 fallos esperados, 5.095 s |
| Verde, mismo test sin editar | `rtk proxy .venv/Scripts/python.exe evals/reports/semantic-threshold-boundary-20261003-01/run_checks.py green` | Exit 0; 4 tests OK, 4.539 s |
| Regresión focal | `rtk proxy .venv/Scripts/python.exe evals/reports/semantic-threshold-boundary-20261003-01/run_checks.py focused` | Exit 0; 94 tests OK, 37.248 s |

Los ocho fallos rojos fueron seis rechazos indebidos —valor exacto y anterior en las tres entradas—,
la inclusión indebida de `failure_omission` en la corrección del segundo intento y la aceptación
ordinal del valor inmediatamente superior. Las comparaciones directas ya pasaban antes del cambio.
Los 94 tests incluyen clasificación, comprobación de citas, flujo HTTP, contratos del juez,
pipeline y privacidad. Los mensajes de error en los logs corresponden a rechazos esperados de esos tests.

Los ficheros `red.json`, `green.json` y `focused.json` guardan comandos, códigos de salida,
hashes de fuentes y logs, y hashes del corpus, los dos packs y ambos resultados vivos protegidos.
Los contenidos protegidos coinciden antes y después de cada corrida y entre rojo y verde.
Entre verde y focal apareció el documento de estado `community-additional-20261003/STATUS.md`
del coordinador; todos los archivos protegidos que ya existían conservan su hash en las tres fases.
El test nuevo tiene el mismo hash en rojo y verde. El preparador de evidencia rechaza sobrescribir
una fase ya existente; para repetir las corridas hay que conservar esta evidencia y usar una nueva carpeta.

En todas las corridas se interceptó `regulai.local_settings` antes de iniciar Django, se utilizó
`regulai.test_settings`, almacenamiento temporal para ficheros y una única conexión SQLite sintética
`file:memorydb_default?mode=memory&cache=shared`. Las barreras de sockets/DNS, requests y httpx
registraron **cero intentos reales**. No se abrieron credenciales, base de datos de usuario ni ledger vivo.
Coste y llamadas API nuevos: **cero**.

Base de trabajo observada antes de integrar: `9e1ae5e58981c6ce0d45c236032a17ad6dcd60db`, con el
runtime previo `128d66a4f7b0cb8d4edc6fe2c36cdf94c458afe2`. La integración y las cinco puertas completas
corresponden al coordinador, sobre su nuevo commit fijo.

La regresión comprueba la frontera numérica y los controles locales. No recalibra Jev, no convierte
el resultado vivo fallido en una entrega retrospectiva y no mide de nuevo la calidad semántica del modelo.
