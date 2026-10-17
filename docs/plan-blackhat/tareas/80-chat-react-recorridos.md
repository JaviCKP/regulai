# 80 — Chat React: recorridos y sistema visual

Status: pendiente.
Blocked by: [79](79-chat-react-base.md).

Especificación: [prompt de renovación](../../../output/chat-ui-research-20261017/prompt.md),
apartados de dirección visual 1–8; [inventario de estados](../chat-react-estados.md).

Decisión ChatMarkdown (17-10-2026): se encapsula el renderer actual (port a
TypeScript de `chat-markdown.js`, mismo algoritmo) con un límite DOM propio.
Streamdown 2.7.0, configurado sin HTML crudo (sin rehype-raw), sin imágenes,
con saneado y enlaces http/https/mailto, superó 6 de 7 comprobaciones del
contrato; falla al retener una posible cabecera de tabla incompleta (mostraría
`| a | b |` en crudo) y añade 475 KB minificados / 142 KB gzip al JS inicial
(medido con el mismo build y React en ambos) sin aportar funciones exigidas.
No se adopta; evidencia y candidato en `output/chat-react-20261017/streamdown/`.

Aceptación: recorrido vertical compositor→envío→streaming→actividad/skill→archivo
y después menús, historial, visor y recuperación, con adaptador al protocolo
actual (transporte, estado y presentación separados). Un único ChatMarkdown con
la política de contenido (Streamdown sólo si supera equivalencia). Sin useChat ni
otro runtime; sin multiarchivo, edición, regeneración ni voz nuevos.
