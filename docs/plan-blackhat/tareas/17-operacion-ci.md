# 17: Operación y comprobaciones CI

**Status:** in-progress
**Blocked by:** none

## Entrega y aceptación

Logs sin contenido, timeout coherente, CI offline/auditoría; validar sintaxis sin afirmar ejecución remota.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

SOL trabaja desde `2cea782`: formatter con lista permitida, auditoría de excepciones sin contenido, Gunicorn y CI. Versiones observadas por ASTRA: uv 0.12.3 y pip-audit 2.10.1. No se ha ejecutado GitHub Actions. PostgreSQL requiere un driver y un servicio que no forman parte del entorno actual; no se añade infraestructura para simular esa validación.
