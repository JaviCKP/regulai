# Formulario simulado P01 — separado del registro humano

**Contenido escrito por un modelo para un perfil ficticio. No son citas, decisiones, tiempos ni valoraciones de una persona.** El [formulario humano original](../../../evals/reports/pilot-documents-20261003-01/human-rehearsal-form.md) permanece sin completar. La simulación no cuenta como validación humana del banco.

- Perfil hipotético: P01, empleado poco técnico, empresa ficticia Alpha, español.
- Persona real: ninguna; operador humano: no asignado.
- Autor/observador técnico: agente P01; identidad de la única prueba nueva: community-demo / Community offline demo.
- Fecha del artefacto: 3 de octubre de 2026. Fecha de sesión humana: no existe.
- Inicio, fin, zona y duración humanos: **no medidos / null**.
- Comentarios literales humanos: **ninguno**.
- Revisión inicial: 535eb9d; navegador nuevo: 972edb8; hashes completos y límites en [informe](informe.md).
- Estado: revisión simulada completa; H1/H2 humanos pendientes.

## H1 con acompañamiento hipotético

| Paso | Resultado verificable usado para simular | Ayuda hipotética; no observada |
| --- | --- | --- |
| Login, saludo y simulación | Login nuevo y banner offline; saludo solo revisado en test, no enviado. | Explicar en castellano que respuestas y jueces son prefijados y el coste del recibo es un fixture. |
| Secreto bloqueado | Expectativa de test exacto y evidencia histórica de control; sin bloqueo nuevo. | Distinguir prohibición de confirmación permitida; no ofrecer un botón para anular el bloqueo. |
| Omisión y cancelación | Nuevo Word cancelado con Tab/Enter, mismo id/SHA, cero llamadas, ningún asistente. | Traducir pending_consent; señalar que párrafo 3 es un localizador interno de la imagen omitida. |
| Confirmación, segundo intento y cita | Recibo histórico: failed/passed, 10 euros, párrafo 2; no confirmación nueva. | Distinguir llamada terminada de respuesta aceptada y ocho operaciones de dos generaciones. |
| Exportación y recarga | Nueva descarga del recibo cancelado; persistencia y cita solo de evidencia anterior. | Explicar para qué guardar JSON y que el original no queda disponible automáticamente para nuevas preguntas. |
| XLSX sin caché y recuperación | Extracción nueva sin/con caché; bloqueo HTTP de evidencia anterior. | Explicar que una fórmula visible no equivale a un valor calculado; caché inyectada, no Excel nativo. |
| Móvil | Capturas históricas revisadas a 375 px; nueva prueba en escritorio. | Señalar el scroll vertical interno si una persona realmente se atasca; registrar esa ayuda cuando ocurra. |

**Respuestas simuladas, no literales humanas:**

- Qué información se envió y cuál se omitió: en el caso nuevo cancelado no hubo llamadas. Si se confirmara el recorrido histórico, la respuesta se apoya en el texto permitido; la imagen del párrafo 3 queda fuera. Haber leído 3/3 unidades textuales no significa haber leído la imagen.
- Qué significa “comprobaciones superadas”: se superaron las comprobaciones exigidas para ese intento; el juez y las respuestas de la demo están prefijados. No es una garantía universal de verdad. El primer intento del recibo histórico falló su comprobación semántica.
- Diferencia entre coste simulado y coste real: 0,00102000 USD es la estimación del fixture histórico, no una factura ni ahorro medido. El nuevo caso cancelado no generó llamadas. Un coste unknown en otro caso no debe sustituirse por cero.
- Qué haría ante caducidad o error: revisar el mismo contenido, archivo y destino antes de renovar. Si el resultado es desconocido, conservar el identificador y pedir comprobar el estado; no repetir la llamada para obtener una respuesta favorable.

Resultado simulado H1: **necesidad de ayuda plausible, no medida**. El modelo puede redactar una explicación correcta tras leer la documentación; eso no acredita que un empleado la comprenda ni cuánta ayuda necesitaría. Incidencias hipotéticas P2-01 a P2-04 en el informe. Sin duración o puntuación.

## H2 sin ayuda durante los pasos: análisis hipotético

| Paso | Qué sí existe | Qué no se afirma |
| --- | --- | --- |
| Saludo y ficha por teclado | Login técnico nuevo; expectativa del saludo y capturas de ficha. | Que P01 encontrara ficha y simulación por sí solo o enviara el saludo. |
| Documento pendiente y cancelación en otra pestaña | Caducidad histórica y cancelación de marcador separadas; nuevo Word cancelado. | Una nueva sesión con dos pestañas, una espera humana o un H2 completo ejecutado. |
| Caducidad, renovación y confirmación | Tres estados históricos con mismo id/SHA/mensaje; cero llamadas hasta reconfirmar. | Que una persona otorgara consentimiento consciente o entendiera la renovación. |
| Cita, exportación, recarga | Teclado/recarga de evidencia anterior; nueva descarga del caso cancelado. | Una cita nueva o capacidad humana de interpretar JSON. |
| Escaneo y cláusula final | Extracción nueva; render anterior muestra 17 días en página 3. | OCR, respuesta semántica nueva sobre el PDF o búsqueda manual realizada por una persona. |
| Secreto, móvil y recuperación | Test del marcador; capturas móviles; coste incierto histórico. | Nuevo bloqueo, móvil físico, desconexión nueva o ejecución viva satisfactoria. |

**Respuestas simuladas e hipótesis de duda, no literales humanas:**

- Por qué pidió confirmar otra vez: el consentimiento anterior había caducado; todavía no había llamadas. Hipótesis a observar: P01 puede interpretar la segunda confirmación como un reenvío, especialmente al cambiar de pestaña.
- Qué acredita una cita: el fragmento conservado del párrafo 2 respalda los 10 euros en el texto utilizado. No demuestra que se leyera la imagen ni que el contrato entero sea correcto.
- Cómo reconoce simulación y coste desconocido: el banner explica la demo; unknown expresa que falta resultado/coste. Hipótesis a observar: el vocabulario inglés y la fila global passed pueden dificultar distinguir estas situaciones sin ayuda.
- Qué haría si falla proveedor o lectura: detener la acción problemática, conservar el identificador y buscar documento legible/soporte según el caso, sin cambiar reglas, permisos, claves ni presupuesto. No se ha observado que P01 escoja ese comportamiento por sí solo.
- Aislamiento: no deberían aparecer datos de Beta, pero ver una lista vacía no basta para concluir que existe aislamiento. No se inició una nueva sesión Alpha/Beta.
- Recuperación ante incertidumbre: no tratar `success=false / outcome_unknown` como éxito o coste cero. La interrupción del laboratorio y la reconstrucción UI son evidencias diferentes; ninguna se realizó durante este formulario.

Resultado simulado H2: **autonomía no acreditada**. No corresponde marcar correcto, con ayudas o no completado a un participante inexistente. La observación humana debe recoger sus decisiones reales y dejar vacíos los campos que no se midan.

## Límites conservados

El nuevo caso técnico de cancelación es correcto en su alcance. No cierra los criterios humanos de participación/comprensión. No se inventan cronómetros, testimonios, satisfacción, tasas de éxito o puntuaciones. Tampoco se añaden etiquetas humanas al corpus ni se altera el banco real.

Próximo uso: entregar H1/H2 a participantes designados y registrar qué hacen y dicen sin sustituirlo por las respuestas simuladas anteriores. La persona no necesita coincidir con estas hipótesis.

