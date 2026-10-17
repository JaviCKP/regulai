# Revisión independiente de la isla de chat (17-10-2026)

Cuatro subagentes de solo lectura (Claude Sonnet, esfuerzo alto), sin ediciones concurrentes
sobre los archivos revisados: un revisor de contratos y otro de acabado visual, y un
verificador escéptico para cada uno que intentó refutar cada hallazgo contra el código, las
capturas, el frontend anterior y las decisiones documentadas. Revisado: `git diff 2bfb930..d65206f`
sin el build, y las 65 capturas de laboratorio regeneradas sobre ese código.

Un primer intento (sesión anterior) se agotó por el límite de uso sin entregar resultados; este
se repitió con un presupuesto de lectura explícito.

## Contratos (6 hallazgos, 6 confirmados, todos corregidos en `3a001af`)

| # | Severidad | Hallazgo | Veredicto | Qué se hizo |
| --- | --- | --- | --- | --- |
| 1 | media | Un envío sin confirmar ofrecía «Recuperar mensaje»; reenviarlo crea otro `request_id` y el servidor podría ejecutarlo dos veces | Confirmado; regresión frente al legado, que sólo ofrecía «Reintentar» con la misma identidad | «Recuperar mensaje» sólo si el servidor no registró la petición (404 al reengancharse, o negativa previa); si no, sólo «Reintentar» |
| 2 | media | Una respuesta HTML (429 del limitador, CSRF, login, proxy) terminaba en un `validation_error` sin acciones y con el adjunto «Recibido» | Confirmado; regresión (el legado caía en «Reintentar»). El 429 JSON del agente sin acciones era igual en el legado | Una respuesta sin `status` no es un resultado: las negativas previas explican el motivo y ofrecen «Reintentar» y recuperar el borrador; el resto se reengancha antes de decidir; «Recibido» sólo con un resultado real |
| 3 | baja | Al volver de bfcache, el reenganche no ocupaba el compositor; una subida cortada se mostraba como «Petición no disponible» | Confirmado | El reenganche ocupa el compositor hasta terminar; la subida cortada vuelve como no registrada |
| 4 | baja | «Confirmar revisión visual» admitía dos POST seguidos | Confirmado; el servidor no duplica el evento, pero el segundo POST podía mostrar un error | Un solo envío en curso y botón desactivado mientras se confirma |
| 5 | baja | Una ejecución revocada seguía ofreciendo «Reanudar» y la petición interpretada | Confirmado; igual en el legado, no es regresión | Se retiran ambos con el resto de la proyección |
| 6 | baja | La intención de exportar a Drive se fijaba antes de enviar y viajaba en el siguiente mensaje si el envío se rechazaba | Confirmado | La intención sólo existe con un envío aceptado; el botón espera a que no haya otra petición |

Cada corrección tiene su prueba (`requests.test.ts`, `ChatApp.test.tsx`); la de la ejecución
revocada se comprobó también deshaciendo el arreglo: la prueba falla sin él.

## Acabado visual (12 hallazgos: 7 confirmados, 3 refutados, 2 inciertos)

| # | Severidad | Hallazgo | Veredicto | Qué se hizo (`8d0f526`) |
| --- | --- | --- | --- | --- |
| 1 | media | La actividad se abre sola mientras el agente trabaja | Refutado: decisión documentada («abierto mientras trabaja salvo espera de decisión») y mismo comportamiento que el legado | Sin cambio |
| 2 | media | Acciones de la tarjeta de entregable heterogéneas y partidas a 360 px | Confirmado | Nombre en una línea; acciones con nombre visible y el mismo tratamiento, al lado o debajo según el ancho de la tarjeta |
| 3 | media | En móvil el compositor pierde el estado del agente | Refutado: el estado se ve en la actividad y en «Detener», y se anuncia por `aria-live` | Sin cambio |
| 4 | media | El selector de skills a 360 px quedaba cortado y con doble scroll | Confirmado | Hoja inferior por debajo de 640 px; sólo la lista se desplaza, con sombras que indican más contenido |
| 5 | media | Las tablas a 360 px partían cifra y unidad | Confirmado | Las columnas alineadas a la derecha no parten; la tabla se desplaza dentro de su caja si hace falta |
| 6 | baja | El texto se cortaba en seco bajo la cabecera | Confirmado (pulido) | Desvanecimiento de 1 rem al salir por arriba |
| 7 | baja | Aviso de skill redundante y motivo con contraste ≈ 3,45:1 | Confirmado sólo el contraste (la repetición en la actividad es decisión documentada) | Motivo a 5,5:1 |
| 8 | baja | El icono de agente desplazaba los títulos del lateral | Confirmado | Todos los títulos empiezan en el mismo borde; la marca va detrás |
| 9 | baja | En táctil el icono de copiar quedaba 6 px metido | Confirmado | El glifo conserva el borde del texto |
| 10 | baja | «✓ Recibido» en un turno bloqueado | Refutado: es un hecho cierto y un estado documentado; el aviso contiguo dice que no se envió a ningún proveedor | Sin cambio |
| 11 | baja | El estado vacío queda bajo a ≥ 768 px | Incierto: preferencia sin criterio fijado | Sin cambio |
| 12 | baja | Escala de tipo y radios definida pero poco usada | Incierto: higiene sin fallo visible | Se igualan los radios de tabla y código y la salida de «Ir al final» baja de 400 a 150 ms; el resto queda pendiente |

## Límites

Los revisores no ejecutaron código ni vieron hover, foco con teclado, tema oscuro ni el teclado
virtual de un teléfono real. La revisión no sustituye a la validación con personas
([tarea 82](../../docs/plan-blackhat/tareas/82-chat-react-retirada-legado.md)).
