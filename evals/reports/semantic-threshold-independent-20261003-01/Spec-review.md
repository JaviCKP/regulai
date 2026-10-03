# Spec review

Base `9e1ae5e58981c6ce0d45c236032a17ad6dcd60db`; commit fijo revisado `1af809fd209c4260d5314ff55fa090147515b8d0`. Diff de tres archivos: `chat_service.py`, `classification.py` y el nuevo test de frontera.

**Cero hallazgos nuevos. Recomiendo aceptar la corrección del P2 numérico en este alcance.** El requisito era conservar el límite nominal inclusivo 0,20, rechazar el flotante inmediatamente superior, no introducir epsilon ni rebajar el umbral 0,8 y preservar las señales del segundo intento.

`chat_service.py:790` calcula el límite con `Decimal(str(...))`. La misma lista de señales estrictamente superiores determina tanto el fallo como las instrucciones de corrección. La sonda independiente comprueba igualdad, flotante anterior y posterior para umbrales 0,8, 0,7 y 0,9. Seis solicitudes a `/chat/send/`, `/api/chat/send/` y `/chat/` verifican entrega al límite y una escalada: omisión=0,20 no aparece como fallo; contradicción inmediatamente superior sí; el segundo intento al límite se entrega. No se inicia un tercer intento.

`classification.py:72` suma masas decimales y elimina la tolerancia previa `+1e-12`. Una cola de 0,1+0,1 conserva public; 0,1 más el flotante inmediatamente superior a 0,1 sube a internal. El suelo local confidential sigue prevaleciendo. Este endurecimiento justo por encima del límite es intencional; no altera el valor nominal ni las comparaciones directas de señales/confianza del diff.

Replay de evidencia viva retenida: **24 clasificaciones iguales** entre base y fix; **11 verificaciones** con una única diferencia, DOC-01/strong pasa el chequeo que antes fallaba por representación. Esto no convierte retrospectivamente su resultado histórico en entrega.

Verificación propia: `rtk proxy .venv\Scripts\python.exe -B evals\reports\semantic-threshold-independent-20261003-01\run.py`, salida **0**, **3 tests**. Fuente exportada del commit fijo, SQLite solo en memoria, local_settings vacío antes de Django, entorno construido con credenciales vacías y cero intentos de red. No se ejecutaron puentes ni proveedores vivos.

Límites: revisión focal, no nueva calibración ni evaluación humana. Se preservan las dos ejecuciones reales y su falta de estado exacto posmáscara del juez. Los modelos, manifiestos, umbrales configurados, presupuestos y ledger no forman parte del diff.
