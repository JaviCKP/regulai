Ejecutar desde `C:\Users\javi\Documents\Codex\regulai-privacy`. `latency_local.py` y `latency_sweep.py` operan sobre la VM de la instalación local; los comandos `unittest` y `latency_report_v2.py` se ejecutan en Windows sobre código y artefactos locales.

La serie `second` conserva como referencia las imágenes de la primera optimización y la copia privada `baseline.dump` de `latency-20261017-a2`. No necesita claves nuevas ni llama a un proveedor de pago. Los bancos usan datos clonados, credenciales sintéticas de proveedor, transporte simulado y bloqueo de conexiones externas. No ejecutar bancos simultáneamente si se quieren comparar sus tiempos.

Verificar los servicios y las fuentes instaladas:

```powershell
rtk proxy python ops/agent_chat/latency_local.py verify --series second
```

La instalación es accesible en `http://127.0.0.1:8800`. Se dejó activo en segundo
plano el túnel existente de `p1_activate_local.py`, limitado a localhost. Si tras
cerrar sesión o reiniciar ya no existe un listener en ese puerto, se puede volver
a abrir con `rtk proxy python ops/agent_chat/p1_activate_local.py tunnel --port 8800`.
Ese túnel también sirve las imágenes anteriores después de una reversión.

Repetir las pruebas de invariantes en una base aislada y el SDK sin red:

```powershell
rtk proxy python ops/agent_chat/latency_local.py tests --series second --round 70
rtk proxy python ops/agent_chat/latency_local.py sdk-tests --series second --round 70
rtk proxy python -m unittest ops.agent_chat.test_latency_recovery ops.agent_chat.test_latency_profile ops.agent_chat.test_latency_report_v2
```

Comparación adicional con siete mensajes por proceso, alternando el orden de las variantes. Usar números libres entre 0 y 199; el banco rechaza una base o carpeta de resultados existente para impedir sobrescrituras. Las rondas 20–39 pertenecen a la muestra formal publicada. Las rondas 70–89 quedan propuestas para otra muestra independiente; no volver a ejecutar `init` ni `build` para medir las imágenes ya probadas.

```powershell
rtk proxy python ops/agent_chat/latency_sweep.py --start 70 --rounds 20 --count 7
rtk proxy python ops/agent_chat/latency_local.py bench-after --series second --round 90 --count 3 --profile
rtk proxy python ops/agent_chat/latency_sweep.py --start 91 --rounds 1 --count 30 --scenario history
rtk proxy python ops/agent_chat/latency_sweep.py --start 92 --rounds 2 --count 5 --scenario concurrency
```

El escenario de concurrencia fija exclusivamente en sus procesos aislados dos plazas globales, de empresa y de proveedor. Publica la configuración instalada y la del ensayo. No modifica la configuración de los servicios existentes. Cada lote contiene dos trabajos con capacidad y tres que saturan esas dos plazas.

Usar cinco lotes por proceso: son 25 mensajes y respetan el límite existente de 30 mensajes por minuto. El intento de diez lotes alcanzó ese control de frecuencia; no se modificó ni se desactivó. Dos procesos por variante aportan 50 trabajos comparables.

Regenerar el resumen de la muestra formal original y comprobar identidad de imágenes, banco, backup, orden y ausencia de solapamiento:

```powershell
rtk proxy python ops/agent_chat/latency_report_v2.py --build 5
```

El generador formal está fijado a las rondas 20–39: ese comando no calcula el resumen de las nuevas rondas 70–89. Estas quedan como artefactos independientes y requieren un generador con ese intervalo explícito para su propia comparación. Los perfiles, pilotos, historiales y lotes concurrentes se enumeran aparte. No se mezclan con el p95 formal. El primer mensaje de proceso no incluye arranque de VM ni cachés frías de PostgreSQL/SO. Las entradas públicas pasan por Django TestClient; worker/servidor usan HTTP real local. El final medido es la primera llamada al proveedor simulado, no el primer token de un modelo real.

Revertir únicamente esta segunda optimización, conservando los datos y claves actuales y la primera optimización:

```powershell
rtk proxy python ops/agent_chat/latency_local.py rollback --series second
```

La reversión exige que no haya trabajo en curso, recupera los contenedores originales por identidad y no restaura la base de datos. Conserva una copia previa de checkpoints y comprueba huellas de datos/configuración. La copia de seguridad privada y los manifiestos se guardan dentro de la VM en `/opt/regulai/updates/latency-20261017-a2`. No copiar esos archivos privados al repositorio.

Tras una verificación correcta, retirar únicamente bases y contenedores temporales reconocidos por esta serie:

```powershell
rtk proxy python ops/agent_chat/latency_local.py cleanup-benchmarks --series second
```

Los artefactos locales y las carpetas de resultados se conservan como evidencia; usar un número nuevo para otra ejecución.
