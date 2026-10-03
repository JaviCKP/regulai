# Checkpoint de privacidad obligatoria

Base inicial: `6c78cd3`. Agente A, 3 de octubre de 2026.

Diagnóstico observado: `chat_service.run_pipeline` y `policy_simulator._semantic` continúan cuando su consulta de máscaras activas devuelve una lista vacía. La comprobación del chat valida una máscara cuando se llama, pero no valida el conjunto de máscaras antes de cada destino posterior.

Regresión inicial: `front.test_required_masking`, antes de cambios funcionales: 3 tests/5 fallos, exit 1. Segundo rojo real: permiso de administrador revocado durante máscara semántica no se revalidaba por caché OneToOne, 1 test/1 fallo, exit 1. Ambas corregidas.

Contrato previsto: D2 es requisito del servidor, sin toggle de desactivación. Los fixtures necesitan `ObfuscationConfig` activo propio, destino explícito `obfuscation:<id>` y `masking.max_call_cost='0'` si son sintéticos y tienen presupuesto. No se prevé migración.

Propiedad: servicio/política/simulador/máscara y fixtures de privacidad; documentos/UI pertenecen a B, evaluación a C, operación/docs generales al coordinador. No commits ni índice hasta coordinación.

Estado final: fuente funcional congelada; 13 tests nuevos OK y gate de 134 tests OK en 40,985 s después del último cambio. Check/migraciones/diff exit 0. README y manifest propios contienen alcance y SHA-256. Listo para integración/commit serializado del coordinador.
