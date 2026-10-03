# Cinco puertas tras corregir la frontera numérica

Commit fijo **1af809fd209c4260d5314ff55fa090147515b8d0**. [Manifiesto, comandos, tiempos y hashes](manifest.json).

| Puerta | Resultado observado |
| --- | --- |
| Django check | Salida 0, sin incidencias |
| Suite front/api | **404 tests OK en 163,419 s**, salida 0; tiempo del comando 165,969 s |
| Migraciones | Salida 0, sin cambios pendientes |
| Evaluación offline | **150 simulaciones, 0 controles fallidos y 0 llamadas reales** |
| Auditoría de dependencias | Salida 0, sin vulnerabilidades conocidas; requisitos principal y operativo |

Comando:

```powershell
rtk proxy .venv\Scripts\python.exe -X utf8 -B scripts\verify_community.py --output evals\reports\adversarial-gates-20261003-02
```

Salida final 0; todos los hashes de código permanecieron estables durante las puertas.
La prueba corresponde al entorno local y no acredita ejecución de CI remoto ni un nuevo ensayo de proveedores reales.
Los resultados vivos anteriores siguen asociados a `128d66a`, incluida la respuesta rechazada en el límite 0,20.
