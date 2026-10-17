# Entrega local: protección reversible

Fecha: 17 de octubre de 2026. Rama `codex/proteccion-reversible`, checkout aislado `regulai-privacy`; base fija `79fb1953006745cddf4bd397a5534cf57a24aec1`. Sin push, integración en main, despliegue, activación real ni llamadas de pago. [Operación y límites](operacion-privacidad-reversible.md).

## Entregas

| Entrega | Resultado |
| --- | --- |
| E1 · contrato | SDK real sobre HTTP simulado; parser incremental UTF-8 acotado, referencias contiguas, todos los cortes de dos fragmentos y entrega byte a byte. |
| E2 · servicio | Ámbito estricto, registro cifrado existente, revisión fijada, variantes cifradas, unicidad concurrente, llamadas y usos idempotentes. Migraciones aditivas 0044/0045. |
| E3 · política | Categorías, literales y YARA localizable; simulación firmada, revisión inmutable, conflictos irreversibles y D2/bloqueo/consentimiento conservados. |
| E4 · salidas | Tres entradas HTTP, generación/agente/resumen/clasificador/juez, búsqueda y herramientas. Comprobación de cuerpo, URL, metadatos y credenciales; JSON escapado y valores numéricos incluidos. Binarios bloqueados. |
| E5 · presentación | Vista natural autorizada por lote, replay, snapshots, cancelación y dos consumidores independientes. Originales opacos; copia/exportación con autorización fresca. El stream admite un alias al principio sin confundirlo con JSON. |
| E6 · interfaz | Configuración, inspector, previsualización y selección exacta. AI Elements y React Bits adaptados y atribuidos. Diseño reducido a filas, etiquetas breves y detalles cerrados; sin tarjetas explicativas permanentes. |
| E7 · validación | Pruebas focales, comparación con la base, migración/reversión, medidas, capturas, vídeo y dos revisiones independientes. |

## Resultados observados

- **60/60 pruebas backend de privacidad**, sin omisiones. Incluyen PostgreSQL concurrente, claves, permisos, YARA, HTTP, streaming, fronteras, vistas y migraciones. [Resultado](../../output/privacy-20261017/acceptance.json).
- **49/49 pruebas frontend**, typecheck y build con `npm run verify`. Vite mantiene un aviso de chunk principal mayor de 500 kB; el build termina correctamente.
- **Build reproducido idéntico:** los 22 archivos coinciden byte a byte tras reconstruir; `git diff --exit-code -- regulai/static/chat-app` vacío sobre el commit `119e1a0`. [SHA-256 por archivo](../../output/privacy-20261017/build-hashes.json). `makemigrations --check --dry-run`: sin cambios pendientes.
- **137 regresiones comparadas** en la base fija y en esta rama: ambos tienen **2 fallos y 13 errores**, con los mismos IDs; ningún fallo nuevo en esa selección. [Comparación](../../output/privacy-20261017/comparison.json), [base](../../output/privacy-20261017/baseline.json), [rama](../../output/privacy-20261017/regression-final.json).
- **11 pruebas de recursos** en cada checkout: 10 pasan y falla en ambos el registro de iconos (`book-bookmark-line-duotone`). [Base](../../output/privacy-20261017/baseline-assets.json), [rama](../../output/privacy-20261017/regression-assets.json).
- Las incidencias previas afectan a referencias de skills/checkpoints, salidas del agente profesional, estado del recibo JEV, dos conexiones cerradas en la prueba de UI y tres procesos SDK no disponibles con esas rutas en Windows. El 409 intermitente de preflight no se reprodujo en este pase. No se han corregido ni ocultado como parte de esta entrega.
- **24 capturas actuales** en 360, 768 y 1440 px: cero desbordamientos horizontales, errores JS y peticiones a destinos ajenos al laboratorio. La copia natural coincide con el texto visible (normalizando CRLF del portapapeles de Windows); la protegida conserva alias tras recargar. [Informe de navegador](../../output/playwright/privacy/report.json).
- **13 capturas HTTP sintéticas** acumuladas del laboratorio: ninguna contiene `Ana Fixture` ni `ana@example.invalid` en la petición serializada completa. [Frontera UI](../../output/privacy-20261017/ui-provider-http.jsonl), [prueba vertical E1](../../output/privacy-20261017/e1-http-fixture.json). Incluyen credenciales ficticias, nunca claves reales.

La suite global no está verde: los resultados anteriores separan explícitamente los fallos presentes en la base de las pruebas nuevas que pasan.

## Matriz de aceptación

| Área de §11 | Evidencia automatizada |
| --- | --- |
| Experiencia completa | `test_privacy_http`: tres entradas, mismo alias al reintentar/reenviar historial y aliases separados por conversación; `privacy-captures.mjs`: stream, recarga y copias. |
| Cobertura | `test_privacy_policy`: literales, nombres etiquetados/campos, D2 efectivo, variantes y solapamientos. Límites visibles dentro de Detalles. |
| YARA | `test_privacy_policy`: instancias múltiples, condición falsa, reglas sin posiciones, UTF-8, wide/binarios, truncado, timeout, revisión y bloqueo intacto. |
| Frontera externa | `test_privacy_http`, `test_privacy_agent`, `test_privacy_boundaries`: SDK/HTTP simulado y rutas privadas del ejecutor; generación, clasificación, verificación, compacción, búsqueda, lectura pública y resultados de herramientas; canales binarios rechazados antes de red. |
| HTTP | `test_privacy_http`: tres entradas, campos manipulados y referencia de otra conversación; cero salidas en fallo de política. |
| Streaming | `test_privacy_vertical`, `test_privacy_presentation`, `test_privacy_agent`, `test_privacy_http`; tests de `requests`, `runs` y `sse`: particiones, Unicode, referencias contiguas/malformadas/incompletas, replay, duplicados, snapshots, dos consumidores, cancelación y retracción. |
| Autorización | `test_privacy_service`, `test_privacy_views`, `test_privacy_presentation`: propietario/empresa actuales, CSRF, token fuera de allowlist, revocación, cambio de empresa y purga durante el stream. |
| Renderizado | `ChatMarkdown.test.tsx` y parser: HTML, Markdown, URL remota, referencia anidada y control como texto opaco; sin nodos ejecutables ni enlaces. Navegador: cero solicitudes remotas. |
| Estado | `test_privacy_service`, `test_privacy_policy`, `test_privacy_http`, `test_privacy_boundaries`: cuatro escritores PostgreSQL, firma del payload completo, retry idempotente, fallo después de registrar y antes de construir el conector, aceptación/bootstrap sin duplicar apariciones. |
| Persistencia | `test_privacy_migrations`: 0043→0045→0043→0045 conserva ciphertext previo y defaults; pruebas de cifrado, rotación HMAC/Fernet, purga y política vigente. |
| Coste/rendimiento | `test_money_and_provider_usage_are_unchanged_when_protection_is_enabled`; `test_privacy_performance`; solo transportes simulados. |
| UI | Capturas actuales y revisión independiente: teclado, foco, Escape, áreas táctiles, temas, movimiento reducido, copia y navegación al fragmento. |

## Rendimiento

Windows 11 build 26200; Intel64 Family 6 Model 151 Stepping 2; Python 3.12.11. Corpus sintético de **3.872 bytes/lote**, dos correspondencias y 64 referencias, 100 iteraciones. `Presentation.feed` con correspondencias previamente autorizadas/cargadas, incluida la comprobación local de política: mediana **3,42 ms**, p95 **3,94 ms**, pico medido **115.356 bytes**. Una consulta SQL tanto para un carácter como para todo el lote; ninguna por carácter. [Medición completa](../../output/privacy-20261017/performance.json).

Es una medida de proyección local, no de latencia extremo a extremo ni de un corpus documental real. El umbral p95 < 50 ms se cumple en esta máquina y muestra.

## Interfaz y revisiones

Build revisado: `main-Db3AF04w.js`, servido por Django en `127.0.0.1:8893`. [Configuración móvil](../../output/playwright/privacy/360-configuracion.png), [inspector móvil](../../output/playwright/privacy/360-inspector.png), [previsualización escritorio](../../output/playwright/privacy/1440-previsualizacion.png), [restauración durante streaming](../../output/playwright/privacy/1440-stream-natural.png), [copia protegida](../../output/playwright/privacy/1440-copia-protegida.png).

[Grabación de la restauración](../../output/playwright/privacy/recording/page@5839b1aa1c67a7f42afa8a7929cbec81.webm). Los artefactos visuales permanecen locales; no se publican.

- **Seguridad/contratos — `/root/seguridad_contratos`, solo lectura.** Se corrigieron y verificaron: revelación parcial de literal irreversible contextual, valores numéricos JSON, fecha de bootstrap variable, doble registro interno/HTTP y doble aparición aceptación/bootstrap. El pase final no encontró nuevos bloqueantes. También comprobó 14 prefijos y 1.302 emisiones del stream frente al enmascarado completo.
- **Visual/accesibilidad — `/root/acabado_visual`, solo lectura.** 44 estados iniciales del diseño reducido, 18 combinaciones de foco, previews de 10.000 caracteres con y sin movimiento; pases finales en 360/1440 sobre revelación y desglose del inspector. Se corrigieron opacidad de previews largos y pérdida de foco al revelar. Sin hallazgos abiertos. [Informe independiente](../../output/playwright/minimal-review/REVIEW.md). La variante «sin confirmar» no apareció en su fixture visual; su estado se prueba en backend.

## Reproducción

Todas las órdenes de la sesión llevan prefijo `rtk`. Se usaron PostgreSQL 18 desechable en WSL, puerto 55483, y bases separadas `test_regulai_privacy_*`, un proceso Django por base. Ninguna SQLite de la aplicación.

Desde la raíz, con el Python del entorno configurado:

```powershell
rtk proxy python ops/privacy_suite.py C:\Users\javi\Documents\Codex\regulai-privacy output/privacy-20261017/acceptance.json test_regulai_privacy_acceptance front.test_privacy_vertical front.test_privacy_service front.test_privacy_policy front.test_privacy_http front.test_privacy_agent front.test_privacy_presentation front.test_privacy_views front.test_privacy_boundaries front.test_privacy_migrations front.test_privacy_performance.PrivacyPerformanceTests.test_loaded_projection_budget_and_constant_query_count
rtk proxy python ops/privacy_suite.py C:\Users\javi\Documents\Codex\regulai-privacy output/privacy-20261017/regression-final.json test_regulai_privacy_regression_final
```

Desde `frontend/chat`: `rtk npm run verify` y `rtk proxy node e2e/privacy-captures.mjs`, tras preparar/servir el laboratorio sintético de `ops/chat_ui` con `REGULAI_PRIVACY_LAB=1`. El runner y el laboratorio se limitan a la base de pruebas; no son configuración de producción.

## Límites y pendientes externos

No se han validado personas reales, exactitud sobre documentos reales, un detector general de nombres, saneamiento universal de binarios ni un despliegue de producción. La activación por empresa y la integración en main quedan fuera de la autorización actual. El contexto puede permitir reidentificación. Los resultados acreditan los casos sintéticos cubiertos, no una garantía universal de ausencia de filtraciones para cualquier documento o configuración futura.

## Commits locales

`93dcd44` tareas/especificación; `f0b585e` contrato vertical; `1a4c3db` offsets del parser; `cb2a092` servicio y registro; `3ac0551` detectores/simulador; `5308b99` fronteras; `82787bf` proyección; `4c2ffef` endpoints y cierre de hallazgos; `119e1a0` interfaz discreta y build. La evidencia y guía se añaden en el commit final de aceptación de esta rama.

Se inspeccionó de nuevo el checkout compartido antes del cierre: conserva sus artefactos ajenos sin tocar. No se ha integrado la rama.
