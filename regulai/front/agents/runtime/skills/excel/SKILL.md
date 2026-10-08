# Excel del laboratorio Regulay

Instrucciones originales de Regulay. No son un prompt de Claude/Cowork ni una copia
de las cuatro alternativas documentales investigadas. Las bibliotecas conservan
sus licencias en la imagen. Consulta ../../NOTICE.md.

Solo se admiten entradas sintéticas CSV UTF-8 o XLSX de una hoja de valores, con
columnas item y amount_cents, importes enteros en céntimos, de 3 a 1000 filas (el
perfil puede exigir un mínimo superior). Se conservan filas duplicadas: cada fila
cuenta. Nulos, fórmulas de entrada, enlaces externos, macros y esquemas distintos
se rechazan; no se adivinan conversiones de moneda ni reglas de imputación.

Para crear el libro llama a build_excel con la referencia opaca y un título. El
Python preinstalado usa pandas y openpyxl, escribe fórmulas y estilos y LibreOffice
recalcula una copia local. La aplicación reabre los bytes finales y contrasta
fórmulas, resultados almacenados y la suma entera contra la entrada inmutable.

Para cambiar el título usa rename_excel con logical_id y base_revision actuales.
Solo cambia la celda del título. No reconstruyas el análisis, los formatos ni las
fórmulas. Sus resultados almacenados se conservan y se comprueban otra vez. Una
versión vieja se rechaza y requiere volver a seleccionar la versión actual.

Si la vista devuelta dice withheld, el archivo no está publicado. Puedes reparar
un fallo local mediante una nueva llamada autorizada, hasta el límite del grafo;
no hace falta aprobación. No repitas una llamada cuyo resultado sea incierto.

No pidas originales, stdout, stderr, tabla de alias ni previews de usuario. La
puerta de 49 solo entrega referencias y agregados contrastados. Los errores crudos
y los borradores permanecen privados. Solo el servidor publica el enlace y la
preview autenticados después de la verificación; no inventes enlaces ni éxito.
