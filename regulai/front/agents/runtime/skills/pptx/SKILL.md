---
name: regulay-pptx
description: Crear y editar una presentación editable de tres diapositivas con datos locales autorizados.
---

# PowerPoint en Regulay

OfficeCLI 1.0.155 es el motor principal. La imagen incluye el binario verificado,
Impress, Poppler y Liberation. No instales, descargues, invoques plugins ni abras
servicios de vista previa. No uses imágenes remotas ni un segundo motor.

Usa `build_presentation` con la referencia de entrada y `template=new` o
`template=corporate`. La entrada acotada admite hasta seis conceptos, etiquetas
de hasta treinta caracteres sin comas y céntimos enteros. Título hasta setenta
caracteres; texto explicativo hasta trescientos cuarenta. Nunca inventes cifras
ni afirmes que existen gráficos en informes que solo contienen tablas.

La composición revisada usa portada, detalle tabular y comparación con gráfico
nativo y libro XLSX incrustado. Preserva los maestros y diseños de la plantilla.
Fuente serif para títulos, sans para datos, paleta verde oscuro y neutros,
espacios consistentes, moneda con coma decimal, importes alineados a la derecha.
El procedimiento aplica estas reglas; no dependen del gusto del modelo.

`edit_presentation` modifica `title` o `body` de una diapositiva 1–3 de la revisión
vigente. Usa identidad lógica y revisión exactas. Cuerpo máximo: 140 caracteres
en la primera, 65 en la segunda y 340 en la tercera. Nunca reconstruyas las otras
diapositivas para un cambio localizado. Versiones antiguas se rechazan.

Los procesos CLI se cierran antes de reabrir, renderizar y sellar. El servidor
contrasta contenido, libro incrustado, tabla, límites del lienzo, fuentes, texto
del PDF y hashes de todos los PNG con los bytes finales. La revisión cualitativa
de todas las diapositivas sucede en el visor privado. Generar PNG no acredita
revisión visual. Un borrador no se entrega hasta completar ambas puertas.

Originales, valores, salidas crudas y renders privados permanecen fuera del
modelo. Solo recibes referencias y el resultado de la puerta del servidor.
Repara localmente un fallo mediante otra llamada autorizada; no solicites
aprobación para cada cálculo/conversión ni afirmes éxito por el código cero del
CLI. No hay animaciones, editor Office general ni compatibilidad demostrada con
todas las versiones de PowerPoint.

Adaptación de la skill OfficeCLI PPTX, commit
8d079c777ed6bea35b922c3d893758d3c2081137, Apache-2.0. Licencia y avisos adjuntos.
Se retiran instalación automática, procesos residentes, plugins, imágenes
externas y gráficos sin libro editable. Las rutas y operaciones son de Regulay.
