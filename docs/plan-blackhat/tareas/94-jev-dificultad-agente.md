# 94 — Jev: evaluación de dificultad en el agente

Status: corregido, aplicado y verificado localmente el 18 de octubre de 2026.
Blocked by: ninguno.

La instalación tiene Jev configurado y routing auto/difficulty, pero el agente
sólo lo consulta con classification=required. Con clasificación local omite
la consulta y registra not_consulted/classification_local, a diferencia del
chat normal. La petición es incorporar la evaluación de dificultad al agente.

## Alcance y aceptación

- Respetar classification=required; si es local y la ruta es auto/difficulty,
  consultar únicamente difficulty-v1. Las otras configuraciones siguen igual.
- Proteger el contexto antes de enviarlo y validar autorización, YARA, presupuesto
  y revocaciones con GovernedCalls. Dificultad no concede permisos ni reduce
  sensibilidad. No sustituye revisión final.
- Conservar el modelo explícito del perfil agente. Registrar la consulta real,
  dificultad, tiempo y coste; sin inventar motivos ni recomendaciones textuales.
- Mantener replay sin consultas/cargos duplicados y bloquear resultados inciertos.
  Sin caché de evaluaciones entre inferencias ni cambios de esquema o política.
- Probar las tres entradas HTTP, privacidad y errores con proveedores simulados.
  Conservar los cambios de latencia y de recuperación del chat 12.
- Activar localmente sólo tras pruebas, con reversión a la imagen actual y sin
  restaurar datos antiguos, modificar claves, hacer push ni llamadas de pago.

## Diagnóstico observado

Clave Jev presente, classification=local, routing=auto/difficulty,
verification=local. Los últimos tres recibos del agente muestran not_consulted,
classification_local y ninguna dificultad. El test de regresión confirma
cero llamadas antes del cambio; sin clave también continuaba sin evaluación.

La evaluación externa añade su propio tiempo de respuesta. No se afirma una
mejora de latencia ni se estima el tiempo del proveedor real usando simulaciones.

## Resultado observado

93 pruebas PostgreSQL pasan sin fallos, errores ni omisiones; 17 pruebas offline
del reinicio y reversión. Las 31 pruebas de dificultad/transparencia también
pasan en SQLite. Tres entradas HTTP y recibo visible verificados con proveedores
simulados. El selector instalado devuelve difficulty con la configuración real.

Imagen aplicada 82417497, derivada de la imagen actual 11d2287c, cambiando sólo
service.py. Worker reiniciado con el mismo ID/imagen/configuración. Huellas de
base idénticas desde la preparación; claves, montajes y checkpoints preservados.
Reversión preparada sin restaurar datos antiguos. Sin llamadas de pago ni push.

Se corrigió también el resumen Jev de llamadas liquidadas después de cancelar.
El informe registra el fixture ausente de la primera suite y el primer reinicio
revertido, ambos resueltos antes de la verificación final.

[Informe y cómo probar/revertir](../../../output/jev-difficulty-20261018/README.md).
