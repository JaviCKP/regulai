# Revalidar generación después de reservar presupuesto

Fecha: 3 de octubre de 2026. Base reproducida: `c1e3a360e7ba3051bb8f0bda487b005dd29834a0`. Hallazgo independiente de Standards, leído en `.claude/review-standards/probe_tests.py`.

La reserva externa de presupuesto podía esperar mientras cambiaban el motor, modelo o credencial. El segundo `preflight` comprobaba empresa, política y máscaras, pero la comprobación del destino de generación había ocurrido antes del observador. El transporte utilizaba la identidad anterior y la petición podía completar.

La comprobación de generación se incorpora ahora al `preflight` común con el identificador del modelo seleccionado. Antes y después de reservar, exige credencial activa de la empresa, modelo activo del motor original, relación motor/credencial intacta y la misma identidad de credencial, endpoint, capacidades y tarifa. Se elimina la comprobación anterior duplicada. Si cambia el destino durante la reserva, se conserva la cota original y se registra `not_started`, coste `0`, procedencia `not_incurred` y exposición `0`, sin transporte ni reenvío al repetir la petición.

## Evidencia

| Archivo | Resultado |
| --- | --- |
| `red-destination-reservation.txt` | Regresión antes de corregir: 1 test, 10 fallos de aserción, exit 1. En las diez variantes se observó una llamada del SDK al transporte simulado. |
| `green-destination-reservation.txt` | La misma regresión: 1 test con diez variantes, OK en 0,745 s; exit 0. |
| `targeted-verified.txt` | Después del último cambio: 19 tests OK en 5,290 s; exit 0. Incluye control positivo con observador, las pruebas previas de privacidad, las tres entradas con SDK real y confirmación concurrente. |
| `check.txt` | Django check: cero incidencias; exit 0. |
| `git diff --check` | Sin errores; exit 0. |

Las variantes cambian durante `before_call(generation)`: activación de credencial y modelo, clave, empresa propietaria, endpoint, tipo de conector, identificador del modelo, motor del modelo, motor de la credencial y tarifa. La regresión compara la cota reservada con la cota persistida al cerrar, verifica `not_started` y vuelve a presentar el mismo identificador para demostrar que no se reenvía.

Comando de rojo/verde:

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_required_masking.RequiredMaskingBoundaryTests.test_generation_destination_changed_during_reservation_never_reaches_transport_or_replays --settings=regulai.test_settings --verbosity=2
```

Comando focal final:

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_required_masking front.test_pipeline.PipelineTests.test_all_http_entries_reach_the_real_connector_sdk_boundary front.test_pipeline.PipelineTests.test_company_reconfiguration_during_classification_stops_generator front.test_pipeline.PipelineTests.test_history_mutation_during_classification_prevents_next_egress front.test_state.RequestStateTests.test_overlapping_confirmation_posts_generate_once_without_open_transaction --settings=regulai.test_settings --verbosity=1
```

Se ejecutaron mediante un wrapper PowerShell que conserva salida y código de retorno en los archivos indicados. `targeted-final.txt` corresponde a la pasada anterior a reforzar la aserción de conservación exacta de la cota; `targeted-verified.txt` es la última.

Solo se modifican `regulai/front/chat_service.py`, `regulai/front/test_required_masking.py` y esta evidencia. Sin cambios de esquema, UI, evaluación, dependencias, índice ni commits. No se ejecutó la suite completa, según el alcance asignado. Las pruebas usan SQLite aislado y el SDK OpenAI real con `httpx.MockTransport`; fuerzan el intercalado mediante el observador. No hubo llamadas a proveedores vivos ni pagadas.

`manifest.json` registra SHA-256 de los bytes exactos verificados.
