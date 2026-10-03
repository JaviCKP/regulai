# Cierre documental y conservación de evidencias

[Verificador](verify.py) de solo lectura. Contrasta las fuentes con gates 05, hashes de revisiones, diagnóstico y perfiles, diario vivo y logs, enlaces locales, presencia de archivos ajenos sin incorporar y retirada de recursos del laboratorio. Compara secretos sintéticos del laboratorio sin emitir sus valores; no lee credenciales reales.

También registra el hash del ledger persistente sin abrirlo para escribir y comprueba que el puerto loopback 8781 del ensayo de teclado está cerrado. No hace llamadas de producto ni repite suites por documentación. La [primera auditoría](../pilot-closure-20261003-01/README.md) se conserva, incluido su enlace roto.

El resultado efectivo queda en `verification.json` al ejecutar el verificador; este documento por sí solo no acredita que las comprobaciones hayan pasado.
