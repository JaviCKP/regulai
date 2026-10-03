# Revalidación de destino tras reserva

Base observada: `c1e3a360e7ba3051bb8f0bda487b005dd29834a0`.

Hallazgo independiente Standards: `before_call(generation)` puede esperar mientras cambian la credencial, el modelo o el destino. La revalidación posterior revisaba empresa/política/máscaras pero no repetía la identidad de generación.

Ámbito autorizado: `chat_service.py`, `test_required_masking.py` y evidencia propia. Sin cambios de UI/evaluación, índice, commits, datos de usuario ni llamadas vivas.

Regresión nueva antes de corregir: diez mutaciones durante la reserva, SDK OpenAI real sobre transporte HTTP simulado; diez fallos de aserción, exit 1. Tras corregir: todas detienen antes del transporte y conservan la cota original con reserva `not_started`/coste 0; repetir la petición no reenvía.

Fuente congelada. Gate focal final: 19 tests OK en 5,290 s, exit 0; check y diff exit 0. Evidencia y manifiesto listos para commit serializado del coordinador. Sin trabajo pendiente en este seguimiento.
