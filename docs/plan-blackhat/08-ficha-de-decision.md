# 08. Una ficha que explique cada decisión

**Estado:** pendiente. **Prioridad:** P1. **Depende de:** [03](03-flujo-unico-web-api.md); ampliar al terminar 04–07. **Resultado:** debajo de la conversación se puede entender qué se decidió, por qué y cuánto costó, sin abrir logs internos.

## Primera versión visible

Un bloque desplegable junto a cada turno: estado de seguridad, cobertura documental, proveedor/modelo elegido, motivo breve, estado de verificación, número de intentos, tiempo y coste. Ejemplo con datos de demostración: “Tarea sencilla; modelo económico autorizado. Documento completo. Comprobaciones superadas. Un intento. Coste estimado”. Los importes proceden de las llamadas reales o se etiquetan como ejemplo.

No mostrar una “nota de confianza global”. Cada señal tiene significado distinto. La explicación se forma a partir de códigos de decisión y plantillas breves, sin pedir otro texto explicativo a un LLM.

## Implementación

1. **Ampliar el registro ya creado.** `Prompt.decision` contiene `schema_version`, política/rúbrica/configuración efectivas, cobertura, resultado de seguridad, ruta, verificaciones, intentos y mediciones. Conservar empresa e identificador definidos en 02. No añadir una tabla de trazas paralela ni otro identificador independiente.
2. **Registrar todos los resultados.** Permisos denegados, falta de credencial, comprobación no disponible, bloqueo, respuesta correcta y escalado tienen ficha. Guardar antes de cada llamada el intento previsto y después su resultado. Si no se conoce el uso por timeout, se muestra desconocido, no cero.
3. **Contabilidad mínima correcta.** Por llamada: propósito, proveedor, modelo solicitado/efectivo, entrada/salida reportadas, tarifa y moneda capturadas, duración monotónica y resultado. Totalizar con `Decimal` clasificación, orientación, generación, verificación y reintentos. Un total con partidas desconocidas es incompleto. Distinguir datos medidos, estimados y no disponibles.
4. **Presentación en Bootstrap y API.** Añadir un desplegable accesible en [chat.html](../../regulai/front/templates/chat/chat.html) y un objeto `receipt` en la respuesta API. Verificar la ruta real de la plantilla al implementar. Usar texto escapado, teclado, foco y estados legibles sin depender del color. Mostrar detalle completo solo a quienes puedan leer esa petición.
5. **Exportación pequeña.** JSON de la ficha con el mismo filtro de permisos; inicialmente basta descargar una petición. No crear un dashboard analítico. Filtrar campos internos y evitar URLs firmadas, claves, documentos, coincidencias sensibles y respuestas descartadas en el export.

La ficha es un registro de lo que hizo la aplicación, no un registro legalmente inmutable. `AuditLog` puede recibir un resumen con `request_id`, pero no duplicar todos los datos ni anunciar inmutabilidad que el modelo actual no garantiza.

## Esquema orientativo de contenido

| Sección | Campos necesarios |
| --- | --- |
| Identidad | `schema_version`, `request_id`, estado y fechas |
| Seguridad | decisión, códigos de motivo, IDs/versiones de reglas, destinos permitidos |
| Documento | digest, formato, estado y unidades de cobertura; sin texto completo |
| Ruta | modo manual/auto/fallback, tarea, nivel, candidato elegido, motivo |
| Calidad | comprobaciones realizadas, resultados y versiones; alcance de verificación |
| Llamadas | propósito, resultado, duración, uso y tarifa por intento |
| Total | moneda, coste conocido/estimado/incompleto, duración y número de intentos |

Validar el JSON en servidor y tolerar versiones anteriores al leer. Los clientes no pueden escribir esta ficha. Los identificadores o hashes no convierten contenido personal en anónimo; siguen protegidos por permisos y retención.

## Aceptación y pruebas

- [ ] Una petición bloqueada tiene motivo comprensible y cero coste de generación; un coste previo solo aparece si realmente ocurrió.
- [ ] Una petición con escalado suma todos los intentos y juicios.
- [ ] Un timeout no presenta gasto desconocido como gratuito.
- [ ] Cambiar la tarifa actual no modifica fichas históricas.
- [ ] Otra empresa no puede obtener la ficha ni su exportación mediante un ID.
- [ ] Nombres de archivo y mensajes con HTML se muestran como texto.
- [ ] La ficha se puede recorrer con teclado y coincide con la API.

Verificar renderizando la interfaz; revisar solo el HTML no demuestra accesibilidad ni ausencia de problemas visuales. Comprobar el cálculo con tarifas sintéticas y resultados independientes.

## Entrega y recuperación

Sin otra entidad persistida; la migración del campo ya pertenece a 02. Añadir campos gradualmente en el esquema de decisión. No llamar “ahorro real” a una resta contra un modelo que no se ejecutó: cualquier comparación hipotética se etiqueta como estimación; el ahorro medido pertenece al plan 11.

Documentar campos, unidades, permisos y retención. Ocultar temporalmente el componente visual no detiene el registro mínimo necesario para explicar decisiones y costes.
