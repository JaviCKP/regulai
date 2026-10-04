# Corpus de calibración adversarial del 4 de octubre de 2026

Este corpus contiene **4.000 solicitudes distintas**, además de conservar intactos los 44 casos históricos. Se generó localmente, sin llamadas de producto ni generación pagada de datos. Las expectativas, semilla, particiones y muestras se fijaron antes de medir el producto.

| Categoría principal | Casos |
| --- | ---: |
| Peticiones legítimas | 1.000 |
| Inyección y manipulación | 1.000 |
| PII y secretos sintéticos | 800 |
| Tareas documentales | 800 |
| Cálculo, razonamiento y formato | 400 |

Hay 500 negativos difíciles, 2.628 solicitudes en español (65,7 %), 1.332 en inglés y 40 multilingües. Las bandas de la solicitud textual completa serializada son 1.000 hasta 256 B, 1.400 hasta 2.048 B, 1.200 hasta 16.384 B y 400 hasta 65.536 B. El tamaño incluye prompt, instrucciones, historial y texto documental. No implica que una entrada quepa en el límite real del proveedor. Los doce archivos históricos binarios conservan `text_is_expected_excerpt`: su longitud textual es la de la expectativa heredada, no una reconstrucción observada del transporte; el arnés debe leer sus bytes con el lector real.

Los 1.179 documentos distintos incluyen TXT, Markdown, CSV, JSON, PDF, DOCX y XLSX. Los doce archivos del piloto anterior se copian sin cambios: incluyen PDF textual, tabla, imagen, escaneo simulado, páginas vacías, cláusula final, DOCX con revisiones/imagen/numeración y XLSX con/sin caché de fórmula. Fueron creados por bibliotecas Python y OOXML explícito; **no son exportaciones guardadas por Office**. No se ha añadido OCR. Las expectativas de cobertura parcial permanecen parciales.

## Acceso y custodia

`api.py` expone `load_partition('development'|'validation')`, que verifica el hash antes de devolver una lista de casos, y `verify_integrity()`, que lee únicamente bytes y devuelve hashes/recuentos sin mostrar contenido reservado. `provider_input(case)` usa una lista explícita de campos permitidos: prompt, instrucciones, roles y contenido del historial, y texto de documentos. Nunca transmite etiquetas, IDs del banco, respuestas de referencia ni marcadores de evaluación. Los archivos adjuntos se presentan como `source.ext`; sus referencias y hashes locales no son instrucciones de producto.

`reserved/` está bajo custodia de A. Durante el ajuste, los demás agentes no abren casos, originales, familias ni muestras de ese directorio. La API pública rechaza `load_partition('reserved')`. La comprobación pública del manifiesto no publica IDs reservados. La apertura final exige fijar primero el candidato y documentar el evento; una nueva calibración tras conocer sus resultados necesitará nuevas familias.

Particiones por grupos completos: desarrollo 2.397, validación 794 y reservado 809. Las diferencias respecto a 60/20/20 proceden del tamaño indivisible de las familias. Los documentos históricos conocidos pertenecen siempre a desarrollo. Las familias sintéticas de ataque directo se asignan una a cada partición para que las muestras contengan la categoría sin reutilizar la misma familia.

Los archivos `*/real_sample.json` congelan cuatro casos por categoría y una selección ampliada por dificultad y longitud. Los cuatro casos de cada lote inicial son exclusivamente sintéticos y revisados por el agente; PII tiene valores realmente anotados para ocultar, y validación/reservado incluyen un documental largo. No es revisión humana. Los ejemplos importados quedan con `provider_reviewed=false`, salvo dos preguntas públicas de ejemplo de PINT que tampoco entran en el lote de cuatro. La selección ampliada no implica autorización técnica para enviar entradas muy largas: el ejecutor conserva límites, presupuesto y preflight.

## Qué significa familia

Se registran **2.067 grupos operativos**. No equivale a acreditar 2.067 familias semánticamente independientes mediante adjudicación externa. Este requisito de independencia fuerte permanece pendiente; el número es un resultado reproducible de agrupación automatizada y procedencia, no una garantía.

- Las variantes locales de nombres, números, codificación, longitud y formato permanecen dentro de la misma plantilla. Los 998 casos legítimos locales sólo aportan 50 grupos. Las 200 variantes de PII sólo aportan diez. Los 788 casos documentales nuevos aportan veinte; sus 197 archivos y cuatro preguntas por archivo no inflan la independencia.
- Gretel aporta 600 documentos de distintos pares `document_type/expanded_type`. Esa condición se combina con exclusión de scaffolds cercanos mediante Jaccard de secuencias de cuatro palabras normalizadas, con límite 0,45. Un nombre de subtipo por sí solo no acredita independencia. Los descriptores de origen se conservan para revisión.
- LLMail aporta 930 construcciones seleccionadas de 21.007 textos etiquetados como ataque en la fase 2. Se excluyen repeticiones exactas normalizadas y vecinos con Jaccard de cuatro palabras de al menos 0,45. La normalización elimina números, destinos, marcadores, mayúsculas y puntuación; un cambio en ellos no crea por sí mismo un grupo. Los resultados del reto original no se convierten en resultados de regulAI.
- GSM8K aporta 400 problemas con anotaciones aritméticas comprobadas, descartando vecinos de al menos 0,40. BIPIA aporta 40 payloads; PINT sólo dos ejemplos de esquema. Las doce expectativas documentales históricas están señaladas como conocidas y no aportan evidencia no vista.

La normalización léxica no detecta toda paráfrasis semántica. No se anuncian significación estadística ni 4.000 observaciones independientes. Las comparaciones deben tratar el grupo como unidad y reflejar esta incertidumbre residual. Se comprueba además ausencia de duplicados de solicitud completa, documentos compartidos entre particiones y originales idénticos entre fuentes. La solicitud completa incluye el hash de los bytes adjuntos: un PDF vacío y uno escaneado tienen igual texto extraíble esperado pero diferentes entradas y cobertura.

Las ampliaciones de longitud añaden contexto inerte de inventario a una selección determinada por semilla. Sirven para comprobar interferencia y conservación de la tarea literal, no son nuevo contenido independiente. Se describen como adaptaciones y permanecen en su grupo original.

## Referencias y expectativas

Los originales seleccionados están en `*/originals.jsonl`, enlazados por hash desde cada caso, junto a las adaptaciones y su justificación. Los ficheros públicos completos necesarios para importar se descargan con revisión fija y hash en `sources/downloads.json`; los grandes originales y `.dependencies/` son caché local ignorada por Git. Nunca se ejecuta código descargado.

Los spans usan índices Unicode de Python sobre el campo original indicado por `scope`: `prompt`, `history:<índice>` o `document:<ref>`. La auditoría valida 2.412 spans sensibles y 2.239 spans a conservar, sus límites y ausencia de contradicción entre ambos. No se tratan todos los importes, fechas o empresas como PII. Las etiquetas de origen se adaptan a la política y las credenciales sintéticas se clasifican como restringidas. No se promete detectar cualquier cadena opaca.

Las 400 referencias numéricas se comprueban con una gramática AST limitada a constantes y operaciones `+ - * /`, usando `Decimal`; no se ejecuta `eval`. Todas las anotaciones de cálculo deben coincidir, y la última coincide con la respuesta final. Esto verifica la aritmética suministrada; la interpretación narrativa conserva la procedencia de GSM8K.

`oracle.kind` es `exact`, `numeric`, `contains`, `abstain` o `manual`. `contains.expected_answer` puede ser una cadena o una lista: en una lista se requieren **todos** los elementos. Los controles exactos/parciales no acreditan la verdad de afirmaciones adicionales. Las síntesis sin referencia exhaustiva quedan `manual`; no deben transformarse en correctas por el juicio del proveedor. Un ataque documental tiene tanto expectativa de control como tarea legítima respondible: detenerlo antes de generar no demuestra resistencia del generador ni utilidad entregada.

La revisión previa corrigió la referencia de un ejercicio de contar tres palabras antes de copiar una etiqueta, explicitó BUSL-1.1 para originales locales y excluyó preguntas sin referencia exacta del lote sintético inicial. Ocurrió antes de cualquier medida del producto; las construcciones de preparación permanecen ignoradas como evidencia temporal, no resultados.

## Reproducción y límites

1. `rtk proxy python scripts/download_calibration_sources.py` descarga únicamente archivos de datos/documentación fijados; el fichero LLMail fase 2 es la menor publicación deduplicada útil (68,6 MB). No descarga la fase 1 de 448 MB ni los envíos brutos de más de 1 GB.
2. El generador necesita el Python 3.12 incluido con Codex y `pyarrow==23.0.1` aislado en `corpus/.dependencies/`; no modifica dependencias del producto. Los documentos Office se reutilizan; no hay una nueva dependencia de autoría.
3. `rtk proxy <python-incluido> scripts/build_calibration_corpus.py --output <directorio-nuevo>` reproduce el banco. Sin `--output` se niega a sobrescribir un manifiesto congelado.
4. `rtk proxy <python-incluido> scripts/validate_calibration_corpus.py --public-only` valida desarrollo/validación. Sólo el custodio ejecuta la variante sin ese flag antes de medir, para esquema e integridad del reservado, sin evaluar sus componentes de producto.

No se ha ejecutado el corpus contra proveedores. El origen público de una referencia implica posible conocimiento previo por el modelo. Faltan adjudicación semántica independiente de las familias, revisión humana de respuestas y el conjunto real privado de PINT. El archivo PINT disponible dice expresamente que no es su benchmark: no se atribuye rendimiento PINT a estos dos ejemplos. Los ataques importados se neutralizan por patrones de destinos/credenciales y permanecen fuera de los lotes pagados; el saneamiento automático no se presenta como revisión perfecta de cualquier dato real residual.

