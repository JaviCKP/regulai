# Preparación y verificación del piloto Community — 3 de octubre de 2026

**Cierre en curso:** código integrado hasta `febc8aa`; revisión de seguridad y cinco puertas definitivas pendientes. Este encabezado se sustituirá al terminar. Base de comparación fija `6c78cd396eb72713e85b72d8592970e4b6b66585`; original `6a0f667`. Las302 pruebas y150 ejecuciones conservadas antes de este encargo son históricas.

## Estado de las seis fases

| Fase | Estado y alcance observado | Pendiente concreto |
| --- | --- | --- |
| 1. Privacidad | D2 obligatoria implementada y probada en chat/simulador; revisión de cierre en curso | Validar eficacia semántica del enmascarador vivo cuando exista uno autorizado |
| 2. Documentos y uso | Corpus12/12 Python/OOXML, expectativas y navegador comprobados; preparada para participación | Abrir/guardar con Word, Excel y LibreOffice reales; realizar H1/H2 con personas |
| 3. Proveedores reales | Preparada, pendiente de acceso y autorización | Máscara HTTPS/contrato/tarifa reales, acceso Jev directo, tarifas/alias revisados y nueva aprobación vinculada al manifiesto |
| 4. Calibración | Preparada, pendiente de participación y ejecución viva | Dos revisores, referencias/rúbrica validadas, conjunto reservado intacto y comparación real |
| 5. Operación | Completada y verificada en laboratorio local Linux/PostgreSQL/HTTPS aislado | Infraestructura pública, CI remoto y recuperación en otro servidor no ejecutados |
| 6. Piloto | Preparado, pendiente de aprobación y participantes | Designar dos personas y operador; autorizar sesión local sintética0USD y registrar observaciones reales |

No hubo nuevas llamadas pagadas de producto, push, despliegue, publicación, contactos, migraciones ni recifrado de la base del usuario. Los agentes A/B/C y revisores nuevos se lanzaron como `gpt-6-astra`, esfuerzo `max`, contexto nuevo; la herramienta confirmó aceptación. Se respetó el límite de cuatro contando al orquestador. El modelo del orquestador no se puede cambiar ni certificar desde las herramientas de esta conversación.

## Implementación y compatibilidad

El servidor exige máscaras de la propia empresa, activas, autorizadas y con ambas categorías. Falta, desactivación, sustitución incompatible, timeout y contrato de lote inválido impiden continuar. YARA evalúa originales antes de red; restricted bloquea incluso motores privados. Se conserva D1–D7 y no se altera el histórico de Prompt/AuditLog ni el esquema. Las políticas antiguas sin máscara compatible deben completar configuración; no se les concede autorización automáticamente.

La regresión inicial demostró la brecha antes de corregirla. Las pruebas capturan HTTP/SDK y cubren entrada, instrucciones, historial elegible, fuentes, localizadores y respuesta. Solo el enmascarador autorizado recibe originales. Esto acredita el recorrido en los casos probados; una máscara que devuelva texto insuficientemente transformado sigue requiriendo validación semántica propia. No se afirma detección perfecta de secretos.

El ejecutor comparte servicio y ledger persistente para smoke/evaluación. Reserva antes de llamar, conserva importes inciertos, limita plazo/intentos/presupuesto y bloquea autorizaciones ausentes/caducadas o configuraciones cambiadas. Economy/strong/router comparten restricciones. La rúbrica humana tiene borradores separados de desarrollo/reservado; no se han usado valoraciones inventadas ni anunciado ahorro.

## Evidencia nueva

| Área | Evidencia conservada |
| --- | --- |
| Privacidad inicial | [Rojo y134 pruebas finales](../../evals/reports/pilot-privacy-20261003-01/README.md) |
| Revocación durante reserva | [Diez variantes rojas y19 pruebas verdes](../../evals/reports/pilot-privacy-followup-20261003-01/README.md); cierre independiente Standards posterior |
| Documentos y navegador | [65 pruebas,12 archivos y capturas](../../evals/reports/pilot-documents-20261003-01/README.md); renovación tras316,599s sin llamadas hasta reconfirmación |
| Ejecutor y banco humano | [24+72 recorridos offline](../../evals/reports/pilot-evaluation-20261003-01/README.md), cero revisiones humanas/cero llamadas reales |
| Operación | [Siete ejecuciones preservadas](../../evals/reports/pilot-operations-20261003-summary/README.md);06/07 completas,82 pruebas PostgreSQL (una omisión SQLite), restauración de27 tablas/2archivos/claves, recifrado/reversión/conflicto real |
| Integración01 | [Manifiesto](../../evals/reports/pilot-integrated-gates-20261003-01/manifest.json):332 pruebas con39 fallos y1 error de fixtures antiguos; otras puertas correctas. No se cuenta como integración aprobada. |
| Correcciones de integración |44 pruebas de clasificación/verificación y7 de UI correctas; temperatura documental reproducida roja y21 pruebas del evaluador verdes. Logs conservados por separado. |

Los resultados de suites parciales se solapan y no se suman. Los bancos offline usan respuestas prefijadas y comprueban controles, no precisión de modelos. Los informes antiguos y los intentos fallidos se conservan, sin sobrescribirlos ni presentarlos como éxitos.

## Revisiones independientes

Standards y Spec revisaron `c1e3a36` frente a `6c78cd3` en contextos nuevos; seguridad revisa `febc8aa`. Los informes permanecerán separados. Standards reprodujo la salida tras cambiar motor/modelo/credencial durante `before_call`: corregida en `a3bc67b`. Spec reprodujo temperatura declarada0,6 frente a0,1 documental: corregida en `febc8aa`, conservando las reglas del servicio; también señaló guías con máscara opcional, actualizadas. El navegador encontró un aviso histórico que pedía confirmar una ficha terminada: corregido en `5fa840c` con rojo/verde y seguimiento visual.

La aceptación final depende de verificar los correctores independientemente y cerrar los hallazgos de seguridad, no de la recomendación del implementador.

## Propuestas revisables y recuperación

- [Recorrido vivo y banco humano](ejecucion-real-y-calibracion-piloto.md): ocho casos iniciales, destinos/modelos publicados y límite conjunto propuesto1USD. Aún no se puede aprobar el destino de máscara porque falta concretarlo. La autorización del2octubre no se reutiliza. El preflight permanece cerrado.
- [Documentos y dos recorridos humanos](documentos-y-ensayos-piloto.md): corpus y formulario listos; aplicaciones Office y personas pendientes.
- [Operación y recuperación](operacion-y-recuperacion-piloto.md): instalación y comandos aislados, backup de base/medios/claves, restauración, recifrado, reversión, estados inciertos y limpieza de recursos propios.
- [Piloto local](piloto-controlado.md): dos personas más operador, documentos sintéticos y coste de API0USD. Incluye permisos, incidencias, condiciones de parada y criterio de decisión. No se ha realizado ni invitado a nadie.

Para continuar con la sesión humana faltan participantes y aprobación del entorno/revisión. Para llamadas vivas faltan servicio de máscara compatible, acceso aislado, revisión de tarifas/modelos y aprobación nueva con destinos, datos, ventana y techo exactos. Ningún silencio ni plazo transcurrido concede esos permisos.
