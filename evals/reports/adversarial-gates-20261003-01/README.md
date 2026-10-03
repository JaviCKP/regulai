# Cinco puertas sobre 128d66a

[Manifiesto de comandos, resultados, fuentes y hashes](manifest.json). Todas las órdenes empiezan por `rtk`.

| Puerta | Resultado |
| --- | --- |
| Django check | Sin incidencias, salida 0 |
| front/api | 400 tests correctos; 169,896 segundos de suite, 172,813 del comando; salida 0 |
| Migraciones | Sin cambios pendientes, salida 0 |
| Evaluación offline | 150 recorridos, cero controles fallidos y cero llamadas reales; salida 0 |
| Dependencias | Auditoría raíz y requisitos operativos: sin vulnerabilidades conocidas, ambas salida 0 |

Fuentes registradas estables durante la ejecución. Esto es verificación local; no se ejecutó CI remoto.
Las pruebas negativas internas de la suite generan informes de fallos deliberados y verifican su detección;
no corresponden al resultado de la evaluación offline normal.

Comando utilizado:

```powershell
rtk proxy .venv/Scripts/python.exe -B scripts/verify_community.py --output evals/reports/adversarial-gates-20261003-01
```

La evaluación adversarial separada conserva omisiones y falsos positivos aunque estas puertas pasen.
Las 400 pruebas no acreditan detección perfecta ni resistencia semántica de modelos reales.
