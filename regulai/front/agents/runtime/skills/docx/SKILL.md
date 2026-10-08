---
name: docx
description: Informe Word desde la plantilla corporativa autorizada y datos locales.
---

Usa build_document con formato docx o pdf y una referencia autorizada. El procedimiento
local rellena la plantilla, conserva estilos, cabeceras, pies, numeración y secciones,
y construye la tabla a partir de los datos originales. No leas originales, perfiles,
DOCX, PDF, PNG ni logs para introducirlos en contexto. No instales ni descargues nada.

Para un cambio de título o del resumen utiliza edit_document con field=title o
field=section. Solo modifica el campo solicitado. export_pdf convierte la revisión
actual sin cambiar el contenido. Usa siempre la identidad/revisión del servidor.

El servidor reabre los bytes finales, contrasta los importes y conserva el render
privado de todas las páginas. visual_review_required significa que falta la revisión
visual cualitativa en el visor autenticado: termina el turno de modelo e indica que
el usuario puede revisar las páginas allí. No intentes autorizarte, fingir una revisión,
reenviar imágenes ni regenerar por ese estado. Un fallo automático permite otra
llamada reparada; los candidatos fallidos se conservan como borradores.
