# Activación real local — 14 de octubre de 2026

Servicio local: `http://127.0.0.1:8800`. Cuenta existente convertida en `admin`.
Credenciales y claves quedan fuera del repositorio. Web ASGI normal, PostgreSQL,
DeepSeek real, worker separado y plantilla E2B privada construida y ejecutada.

## Evidencia

- `tests-postgresql.log`: 65 pruebas pasan en PostgreSQL de pruebas separado;
  incluyen tres entradas HTTP, política, dinero, cierre de presupuesto y catálogo
  de herramientas tras el cierre de red privada. Proveedores simulados en estas pruebas.
- `health.log`: admin/staff/superuser, PostgreSQL, DEBUG=False, simulador=False,
  agente profesional habilitado, páginas protegidas HTTP 200.
- `renderer.log`: conversión real DOCX → PDF/PNG dentro de la microVM aislada.
- `startup.log`: arranque único probado con recuperación de memoria y firewall.
- `restart-downloads.log`: nuevo login tras reiniciar la web, descargas HTTP con
  hashes idénticos, estado completed y contenido distinto en las dos tareas.
- Además, 12 pruebas de interfaz pasan con el selector profesional por defecto.

## Resultados reales

1. Mendizábal: ejecución `7b99bb31-8fda-4f1e-9347-fac437412dad`, conversación 13.
   Recuperación del documento creado con DeepSeek en la conversación 10.
   Tres páginas, tres diagramas, Word/PDF descargables. Hash del Word:
   `8d85547639a3ff06e2e4f433de7a2fde011f66b35b9445c7507af11398fcf6c2`.
   Las tres imágenes descargadas coinciden con las revisadas visualmente.
2. Creación nueva sin adjunto: ejecución `4017ae7a-13ad-4f74-bea7-7cd09a920e87`,
   conversación 14. «Entrada, procesamiento y salida», una página, un diagrama,
   11 llamadas reales, coste de modelo estimado 0,05785950 USD.
   Hash: `e334f1410ef697be351fb55bab8a8ed3ec1d2a0cead39513515a8f621a9f969a`.
   Contenido y página revisados; no contiene el tema del documento anterior.

Archivos, páginas y recibos completos en
[`output/real-agent-20261014`](../../../output/real-agent-20261014/).

## Límites y trazabilidad

Los ensayos fallidos no se borraron ni se marcaron como completados. Su historia
se describe en [la tarea 57](../../../docs/plan-blackhat/tareas/57-activacion-real-local.md).
La búsqueda Tavily no está configurada y el navegador JavaScript está desactivado
por un fallo observado del puente. La lectura web directa está disponible.
La revisión visual aquí es la realizada durante esta sesión sobre los PNG reales;
no se ha registrado una revisión humana ficticia ni una llamada de visión inexistente.
La validación de estructura y páginas no garantiza todas las afirmaciones históricas.
No es un despliegue público ni una validación de toda la matriz funcional de la tarea 56.
