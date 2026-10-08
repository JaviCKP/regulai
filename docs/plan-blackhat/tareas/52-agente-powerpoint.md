# 52. PowerPoint editable con revisión visual

Estado: pendiente de implementación.
Blocked by: [51](51-agente-word-pdf.md).
Especificación: [guía de ejecución](../../implementacion-agente-regulay-prompts.md), candidatos y corpus del [informe documental](../../investigacion-prompts-skills-documentales-2026-10-07.md).

## Prompt de ejecución

```text
Implementa exclusivamente la tarea 52. Lee AGENTS.md, la guía de ejecución y la
investigación documental. Parte del mismo recorrido de archivos de 50/51.

Añade PPTX como cuarta skill, sin un segundo agente ni otra UI. Empieza por
OfficeCLI, fijando versión y licencia. Prueba antes de adoptarlo: crear una
presentación breve, modificar una plantilla y cambiar solo una diapositiva.
La comprobación debe inspeccionar el PPTX final y renderizarlo, no solo mirar el
HTML previo a la exportación.

Conserva maestros/diseños cuando haya plantilla. Texto, tablas y gráficos deben
seguir siendo editables donde lo requiera la tarea. No rasterices toda la
presentación para ocultar problemas. Verifica contenido, número de diapositivas,
objetos fuera del lienzo, solapamientos y legibilidad. Vacía los procesos
residentes antes de que el verificador lea y calcule el hash del archivo.

Si OfficeCLI falla un requisito de esos tres casos, compara solo ese caso con
BrandDocs ya disponible o dom-to-pptx, según sea conservación de plantilla o
creación desde HTML. Elige una implementación principal; no dejes tres motores
activos, un selector genérico y una batería combinatoria. Documenta la limitación
real si ninguno cumple, sin prometer compatibilidad completa con PowerPoint.

Adapta la skill al catálogo, fuentes, imagen y rutas de Regulay. Retira instalación
automática y uso no autorizado de imágenes externas. Elige los recursos del
usuario o locales; no hagas nuevas llamadas de pago de imagen o inferencia.

Integra preview de diapositivas, descarga y edición sobre la misma identidad de
artefacto. Prueba que cambiar el título no altere el resto del deck y que una
reparación vuelva a validar la revisión final. Mantén renders reales fuera del
modelo y comprueba la UI. Ejecuta los cuatro casos PPTX del corpus; la variante
con modelo simulado no cuenta como medida de calidad generativa.

Registra motor elegido, resultado de las comprobaciones y limitaciones. No
añadas animación avanzada, colaboración en diapositivas o editor visual salvo
que sean imprescindibles para un caso ya solicitado. Detente antes de la 53.
```

## Aceptación

- Crear, editar y renderizar PPTX dentro del mismo flujo del chat.
- Una implementación elegida, dependencias fijadas y licencia registrada.
- Contenido editable y preservación de la plantilla comprobados para los casos admitidos.
- Cambio localizado sin regresiones en otras diapositivas; reparación seguida de nueva verificación.
- Los cuatro formatos conviven sin ampliar permisos o exponer datos a la vista del modelo.

## Verificación observada

Pendiente. OfficeCLI y las alternativas están investigadas, pero no instaladas ni evaluadas en Regulay.
