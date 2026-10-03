# Cierre de integridad y contabilidad

[Comprobación completa](run-03/checks.json): **salida 0**, 664 hashes comprobados sin diferencias y 168 enlaces locales válidos.
Código final `1af809f`, cinco puertas correctas y revisión independiente sellada. El [verificador](verify_delivery.py) es reproducible
y rechaza sobrescribir el directorio de salida:

```powershell
rtk proxy .venv\Scripts\python.exe -X utf8 -B evals\reports\adversarial-closure-20261003-02\verify_delivery.py evals\reports\adversarial-closure-20261003-02\run-03
```

Comprueba corpus y resultados congelados, paquetes de revisión, logs de puertas, fuentes actuales, manifiestos y aprobaciones reales,
logs de los puentes, agregados y enlaces. Las únicas diferencias de código de producto entre ambos ensayos y el cierre son
`chat_service.py` y `classification.py`, correspondientes al arreglo numérico.

El ledger se abre exclusivamente con `mode=ro`: 110 entradas, dos extensiones explícitas bajo el mismo cap de 1 USD.
Las primeras 29 y 65 entradas conservan sus hashes; todo el ledger coincide con el último snapshot público.
La única reserva incierta histórica sigue siendo 0,003 USD. Cero llamadas nuevas y ninguna apertura de la BD del usuario por este verificador.

La [primera comprobación](run-01/checks.json), salida 1, señaló solo un error del helper: interpretó las rutas de un índice
relativo al repositorio como relativas a su carpeta. Se corrigió la base de resolución, manteniendo cada hash exigido.
No cambiaron artefactos ni resultados para resolverlo. El cierre anterior a la segunda pasada permanece en
[otra carpeta histórica](../adversarial-closure-20261003-01/checks.json).

La [comprobación del índice Git](index-check-03.json), salida 0, contrasta 184 archivos conservados con sus bytes en disco.
Detectó antes normalización CRLF en diez archivos de la revisión final: se añadió `.gitattributes` con `-text` y se volvió
a aplicar el filtro al índice mediante `git add --renormalize`, sin modificar los archivos sellados. Los intentos previos
se conservan en `index-check.json` y `index-check-02.json`. El salto de línea final de un log histórico también se mantiene;
no se altera evidencia para satisfacer una comprobación estética de whitespace.
