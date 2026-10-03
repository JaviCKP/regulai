# Consolidación de dos pasadas reales

[24 respuestas, prompts y señales](calculation-03/responses.md) · [JSON por caso](calculation-03/cases.json) ·
[métricas y presupuesto](calculation-03/summary.json) · [informe interpretado](../../../docs/plan-blackhat/informe-adversarial-community-20261003.md).

Ocho casos distintos en economy/strong/router. Runtime observado `128d66a`. Se conservan una entrega, 15 bloqueos y ocho rechazos;
46 llamadas externas y 35 transformaciones locales. Los segundos intentos pertenecen a BENIGN-01/router y BENIGN-02/router;
ninguno terminó entregándose. No se recalculan resultados vivos con código corregido después.

El [script](build_report.py) solo lee archivos conservados, comprueba los mapas de fuentes, hashes de generaciones canónicas y
conservación de las 65 entradas previas del segundo presupuesto. Usa Decimal para costes; no importa Django ni accede a BD o red.
Comando ejecutado, **salida 0**:

```powershell
rtk proxy .venv\Scripts\python.exe -X utf8 -B evals\reports\adversarial-consolidated-20261003-01\build_report.py --output evals\reports\adversarial-consolidated-20261003-01\calculation-03
```

Para reproducir, elegir un directorio nuevo: se rechaza sobrescritura. Los dos intentos auxiliares previos se conservan:
uno asumió un campo opcional de manifiesto y otro el formato incorrecto de hash de texto. Sus [fallos](calculation/failure.json)
y [corrección de codificación](calculation-02/failure.json) no afectaron a ejecuciones o datos originales; todas las aserciones
se mantienen usando el contrato real del ejecutor. La evidencia final comprueba las once generaciones conservadas.

Mediana y p95 incluyen todos los casos, también bloqueados; p95 usa rango más próximo. N=8 por configuración, 24 total.
Revisión humana, precisión, coste por respuesta correcta y ahorro permanecen sin calcular; cobertura de entrega no equivale a calidad.
