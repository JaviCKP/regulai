# 51. Word desde plantillas y PDF comprobado

Estado: pendiente de implementación.
Blocked by: [50](50-agente-chat-excel.md).
Especificación: [guía de ejecución](../../implementacion-agente-regulay-prompts.md), [investigación documental](../../investigacion-prompts-skills-documentales-2026-10-07.md).

## Prompt de ejecución

```text
Implementa exclusivamente la tarea 51 sobre el recorrido verificado de la 50.
Lee AGENTS.md, docs/implementacion-agente-regulay-prompts.md, la investigación
documental y docs/agent-assets/sources.json.

Añade DOCX desde plantilla corporativa y PDF al mismo ejecutor, catálogo de
skills, registro de artefactos, progreso y preview. No crees otro flujo de chat.

Evalúa BrandDocs con una plantilla sintética representativa antes de integrarlo.
Si cumple conservación y verificación, fija el motor compartido y brand-docx,
con licencia y NOTICE. Deshabilita aprendizaje global y descargas en tiempo de
ejecución. Si falla un requisito crítico, documenta el caso y usa un procedimiento
acotado con python-docx/plantilla; no construyas un framework alternativo de marca.

Adapta la copia Apache 2.0 de la skill PDF pública de OpenAI. Conserva atribución
y señala cambios. Usa las rutas, herramientas y política de datos de Regulay;
no ejecutes sus instrucciones genéricas de instalación durante una conversación.
Preinstala conversores, bibliotecas y fuentes con tildes, ñ y símbolos monetarios.

Valida el recorrido Excel → informe DOCX → PDF usando resultados locales.
Conserva estilos, tablas, cabeceras, pies y numeración. Reabre los archivos y
renderiza las revisiones finales. Comprueba páginas, texto esperado, tablas
cortadas, fuentes y restos de la plantilla. No aceptes que una revisión visual
degrade silenciosamente a comprobaciones estructurales. El hash del archivo
verificado debe coincidir con el entregado.

Los perfiles de plantilla y renders también pueden contener datos. Sus originales
se quedan locales; únicamente vistas protegidas autorizadas llegan al modelo.
La preview autenticada para el usuario no se reutiliza como entrada de visión.
Continúa ante errores reparables, sin preguntar por cada conversión o cálculo.

Un segundo turno debe poder cambiar el título o una sección y publicar una nueva
revisión del mismo artefacto, conservando el resto. Prueba entradas malformadas,
plantilla multipágina, tabla larga, caracteres españoles y fallo del conversor.
Comprueba visualmente archivo y UI. No incorpores aún otro motor de presentaciones
ni un editor Office embebido. Actualiza la evidencia y detente antes de la 52.
```

## Aceptación

- XLSX → DOCX → PDF comprobado y previsualizable en el chat; una edición conserva identidad y diseño.
- Plantilla, conversores y fuentes pasan casos reales locales con datos sintéticos.
- Reapertura/render obligatorios, reparación y comprobación de la revisión final.
- Procedencia conservada; ninguna skill instala dependencias ni elude el gobierno del modelo.
- No salen originales ni renders reales al contexto del modelo.

## Verificación observada

Pendiente. La copia PDF existente es material de referencia, no una skill activa validada en este runtime.
