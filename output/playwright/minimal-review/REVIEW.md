# Revisión independiente del acabado sutil

**Build definitivo: `main-Db3AF04w.js`.** Pase focal adicional del inspector a 360 y 1440, cerrado y con detalles abiertos: seis capturas en `inspector-final/`. Totales discretos, token y fechas legibles; el desglose por entrada/historial/otros/respuesta cabe sin solaparse. El panel conserva desplazamiento vertical con doce registros y no tiene overflow horizontal (`scrollWidth == clientWidth`: 359/447px). Copiar identificador devuelve exactamente el token y mantiene foco en el botón. Ocho Tabs por ancho permanecen en el panel; Escape devuelve foco a Más opciones. Sin errores JS ni activaciones. La fixture tiene llamadas confirmadas; este pase no acredita el render de la variante «sin confirmar». No hay hallazgos visuales abiertos.

**Cierre de revisión:** el pase focal posterior de `main-DMr4HQ69.js` resuelve el hallazgo de foco. `Ver` mantiene foco durante la petición (incluido retraso artificial de 600ms), `Ocultar` lo conserva y elimina el original de la vista. Verificado en 360 y 1440. `Ver mensaje` cierra el inspector, desplaza al mensaje, resalta el fragmento exacto «Ana Fixture» y enfoca su `span` de offsets 0–45. Las etiquetas abreviadas de settings caben en una fila móvil; el preview usa «Nombre 1» y «Correo 1». Diez capturas finales, sin overflow ni errores: `final/report.json` y `final/{360,1440}/`. No hubo activaciones, selecciones guardadas ni borradores nuevos en este pase focal. No quedan hallazgos abiertos de esta revisión visual.

## Pase completo anterior

Build servido por Django: `main-BFgsWawN.js`, laboratorio sintético `127.0.0.1:8893`.

Se capturaron 44 estados a 360×780, 768×1024 y 1440×900, con paletas clara y oscura: inspector, original revelado, preview con chips, selección ya protegida, configuración y diferencias de un borrador sintético sin activar. Los temas se establecieron mediante `data-bs-theme`; no se probó persistencia de preferencias.

El acabado actual reduce claramente el texto y el peso visual: ajustes por filas, inspector compacto, identificadores/advertencias bajo detalles cerrados y previews con etiquetas cortas. Las capturas inspeccionadas muestran jerarquía legible y espacio suficiente. No hay desbordamiento horizontal ni errores JS o solicitudes externas en el recorrido.

## Verificaciones

- Las 18 combinaciones de modal/ancho/tema mantuvieron el foco dentro durante ocho pulsaciones Tab, esperando 150ms entre pulsaciones. Escape devolvió foco al disparador correspondiente.
- Los detalles permanecen cerrados al cargar cada vista.
- Seleccionar «Ana Fixture» existente devuelve una propuesta y habilita «Proteger en este chat» en las seis combinaciones. No se guardó ninguna selección.
- Las previsualizaciones de 10.000 W ya muestran contenido: `opacity:1`, cajas de 296px y contenido desplazable, tanto con movimiento normal como reducido. Queda resuelto el fallo anterior de FadeContent.
- Se generaron seis borradores sintéticos de configuración para inspeccionar sus diferencias. No se activó ninguno; no se enviaron mensajes ni se modificó código fuente.
- Sin controles nuevos menores de 40px en móvil/tablet. El cierre de selección mide 28×28px en escritorio; supera 24px y no se considera bloqueo.

## Hallazgo de este build, resuelto en el pase final

Al pulsar «Ver», el botón se deshabilita durante la petición y el foco termina en BODY aunque el elemento no se desmonte. Reproducido en las seis combinaciones. Ocultar conserva correctamente el foco. Comunicado a la raíz: mantener el botón enfocable durante carga (`aria-disabled` con guard) o restaurar foco al terminar.

Evidencia estructurada: `report.json`. Las capturas anteriores del directorio `visual-review` son diagnósticos del diseño reemplazado y no representan este acabado.
