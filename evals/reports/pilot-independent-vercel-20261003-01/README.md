# Revisiones independientes del ensayo con Vercel

Commit fijo `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`, anterior a la ejecución viva. Security y Spec son agentes Astra Max distintos del implementador C. Ninguno realizó llamadas de producto ni accedió a claves o bases del usuario.

- [Security](security/security-vercel-698e8f0.md): 51 pruebas correctas (45 suministradas y seis propias), cero sockets/DNS. [Sello](security/final-seal.json).
- [Spec](spec/Spec-review.md): 31 pruebas correctas, seis propias; doce tuplas probadas, solo dos combinaciones exactas admitidas. [Evidencia](spec/evidence.json).

Sin nuevos hallazgos bloqueantes en esos alcances. Se preservan los fallos iniciales de dos arneses: finales de línea del export y fixture que marcaba manipulación durante clasificación. Los verdes corresponden a una copia de bytes aprobados verificados y al fixture corregido, sin cambiar aserciones ni fuentes productivas. No son una garantía de calidad o disponibilidad del proveedor vivo.

[Inventario de copias y hashes](files.json); [script](package.py). Los informes originales se copian sin cambiar bytes, incluidas sus referencias a los directorios privados de pruebas. Se excluyen snapshots completos, ZIP y cachés; los scripts, capturas sintéticas, inventarios, comandos, códigos y logs permanecen conservados.

Seguimiento del sellado: una [errata separada](../pilot-independent-diagnostics-20261003-01/security/log-hash-errata.md) identifica tres hashes parciales de la tabla de Security y los metadatos de su wrapper. Los sellos finales originales contienen los hashes completos correctos. Se mantienen intactos informe y evidencias originales; no cambia el resultado de las pruebas.
