# 18: Privacidad y pipeline integrado

**Status:** in-review
**Blocked by:** none

## Entrega y aceptación

B1/B3/B4/B5/B6/B9; preflight, masking, presupuesto, consentimiento, reintento, historial, tiempo y cancelación.

Especificación y propiedad: [contratos de correcciones](../correcciones-community.md) y encargo humano allí referenciado. Decisiones D1–D7 aprobadas el 3 de octubre de 2026. Sin operaciones irreversibles ni llamadas pagadas.

## Verificación observada

Integrado mediante merge `eb8fde7`, conservando los commits pequeños de P (`e49cc6e`–`3e5e89e`). Enmascarado conjunto, verificación sobre fuentes enviadas, decisiones conservadoras, consentimiento renovable, límite previo del juez, reintento con controles concretos, motor manual acotado, historial por pares/bytes y plazos efectivos. La expansión del historial por el enmascarador también se rechaza si supera su cota.

ASTRA volvió a ejecutar las doce regresiones finales B1–B10/C1–C2 contra el producto `4400f0b`: doce AssertionError, cero errores y cero omitidas. Siete pruebas adicionales de P reprodujeron siete fallos de aserción en la base (cancelación, plazo, roles y feedback, motor manual, 503 incierto, logging y rúbricas). El falso positivo por transformar una cita inventada durante el enmascarado se reprodujo y corrigió antes de integrar.

Puertas `13-pipeline`: check sin incidencias; 275 tests OK en 43.918 s, sin expected failures; migraciones sin cambios; 150 controles offline correctos, cero salidas indebidas y cero llamadas reales; pip-audit sin vulnerabilidades conocidas. La prueba negativa del evaluador produce deliberadamente seis controles fallidos sobre expectativas falsas en un banco temporal; no son fallos del banco final.

Solo tres etiquetas development cambiaron por D3, con [justificación previa por caso](../cambios-banco-correcciones.md). El servicio de enmascarado debe preservar la estructura del array JSON recibido como texto; una respuesta incompatible falla cerrada. La cota de salida es un límite de aceptación local, no una equivalencia formal entre tokens y bytes. La sobrecarga interna no documentada del proveedor sigue siendo una hipótesis del estimador. Pendiente revisión adversarial final.
