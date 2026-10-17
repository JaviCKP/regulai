# Worker y cola: verificación local

35 pruebas distintas pasan (36 ejecuciones porque ASGI se ejecutó además por separado), sin proveedores reales. La suite PostgreSQL incluye notificaciones transaccionales, carrera entre comprobación y espera, claim único con dos workers, replay, revocación, capacidad y dinero. El ASGI real atiende una inferencia HTTP mientras dos peticiones de claim permanecen en espera.

El banco registra 20 muestras calientes y una conexión fría por modo/concurrencia (126 trabajos). p95 caliente: 454,563 → 158,099 ms con una ejecución; 471,560 → 177,599 ms con dos ejecuciones. La mediana de SELECT por claim es 33 → 33 y 33 → 35,5 respectivamente: con dos workers el primer aviso puede despertar ambos. La espera vacía no sondea continuamente; en la prueba de notificación perdida se hacen dos consultas de estado durante el plazo, una al principio y otra al final.

Estas cifras incluyen la admisión HTTP del fixture y el claim real en proceso; excluyen transporte HTTP del claim y arranque del SDK. “Frío” significa conexión nueva, no proceso nuevo. El baseline reproduce el sleep previo de 500 ms con el mismo claim. El archivo JSON conserva todas las muestras y límites.

- Resultado y comandos exactos: [worker-verification.json](worker-verification.json).
- Muestras: [queue-comparison.json](queue-comparison.json).
- Banco reproducible: [latency_queue_benchmark.py](../../ops/agent_chat/latency_queue_benchmark.py).

Ejecutar los comandos del JSON desde `C:/Users/javi/Documents/Codex/regulai-privacy`. Crear primero el PostgreSQL efímero con imagen cacheada, ejecutar `postgresql` y `benchmark`, y terminar con `cleanup`. Las pruebas SDK no necesitan PostgreSQL. Los intérpretes reutilizan los entornos locales existentes de regulai-platform, pero importan este checkout regulai-privacy. No hay cambio de dependencias.

El contenedor de laboratorio se detuvo y eliminó después del banco y de las pruebas de privacidad. No conserva volumen ni base de datos. Los cambios de producción de este bloque no añaden migraciones ni configuración; iniciar el servidor actualizado antes del worker actualizado. Los workers anteriores siguen usando el claim inmediato.
