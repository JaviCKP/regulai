# 79 — Chat React: base de build, bootstrap y reversión

Status: en curso.
Blocked by: ninguno.

Continúa [78](78-investigacion-chat-ui.md). Especificación:
[prompt de renovación](../../../output/chat-ui-research-20261017/prompt.md);
[inventario de estados](../chat-react-estados.md).

Aceptación: isla React/TypeScript/Vite limitada al chat, sus menús y visor;
dependencias fijadas con lockfile y avisos de licencia; build reproducible a
`regulai/static/chat-app/` con `manifest.json` resuelto por Django (JS, CSS y
chunks importados); bootstrap JSON público con campos explícitos; un solo
frontend activo por página y vía local de reversión; Tailwind, reset, tokens y
portales aislados; la biblioteca de skills y las páginas de `base.html` intactas.

Decisión registrada: excepción autorizada a la exclusión histórica de React
([README, decisión 1](../README.md#decisiones-compartidas-para-evitar-soluciones-incompatibles)),
limitada a la experiencia del chat. Django conserva backend, sesiones, CSRF,
permisos, archivos, ejecución, estado autoritativo y dinero.
