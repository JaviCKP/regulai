# Revisión independiente del banco y de la extensión de alcance

Revisor Astra Max de esta conversación, sin participación en el código revisado. Base `21bdd9f`,
candidato `df91ea1`, corrección verificada `128d66a`. Los dos ejes se revisaron por el mismo agente,
separados en [Spec](Spec-review.md) y [Standards](Standards-review.md), respetando el límite de concurrencia.

Un P2 reproducido y corregido: cambio de autorización durante espera del lock causaba un informe incoherente.
La corrección rechaza ese cambio antes de mutar. Pruebas independientes de expiración tras reserva,
revocación durante lock y conservación monetaria pasan. Cero hallazgos abiertos en el delta revisado.

Además reprodujo detector44 (37 casos con todas las anotaciones), 30 recorridos HTTP focales (27 controles correctos,
los tres rechazos de cita alterada en INJ-05 conservados) y los límites principales. No repitió las 264 ejecuciones del implementador.

[Evidencia](evidence.json), [índice de 28 archivos con hashes](package-files.json), rojo [extension.log](extension.log)
y [seguimiento verde](extension-fixed.log). Los archivos del revisor se copiaron byte a byte tras comprobar sus hashes.

El informe se selló antes de activar la aprobación humana: su mención de permiso pendiente describe ese momento.
La autorización y las llamadas reales posteriores están en [la ejecución real](../adversarial-real-20261003-01/).
No atribuir esta revisión técnica a participantes humanos ni a una evaluación semántica de modelos vivos.
