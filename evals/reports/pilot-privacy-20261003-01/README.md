# Privacidad obligatoria — evidencia local

Fecha: 3 de octubre de 2026. Agente A. Base inicial: `6c78cd3`.

El chat y la simulación semántica detienen la salida cuando falta una máscara activa, propia y autorizada. El servidor exige detección de datos personales y secretos (`detect='both'`); el borrador inicial avisa de la configuración pendiente. La política no ofrece un interruptor para omitir esta protección. No se requiere migración de esquema ni se modifican históricos.

Antes de cada destino se comprueban otra vez empresa, usuario, política, consentimiento y el conjunto completo de máscaras activas con su identidad. El original se evalúa con YARA antes de llegar al enmascarador autorizado. Generador y Jev reciben el lote devuelto por la máscara. Un lote con tamaño/tipos/JSON inválidos detiene el recorrido, sin salida parcial ni coste inferido como gratuito.

Una regresión adicional detectó que asignar `actor.profile = fresh` sustituía la caché inversa `fresh.user` de Django por el actor anterior. Los tres controles semánticos comprueban ahora los privilegios recién leídos antes de esa asignación. La revocación de administrador durante el enmascarado impide la llamada siguiente a Jev.

## Resultados observados

| Evidencia | Resultado |
| --- | --- |
| `red-required-masking-exit.txt` | Antes de cambios: 3 tests, 5 fallos de aserción; exit 1. Sin máscara el chat completaba o redirigía y el simulador semántico enviaba. |
| `red-semantic-role-revocation.txt` | Regresión adicional: 1 test, 1 fallo de aserción; exit 1. El simulador completaba después de revocar administrador durante la máscara. |
| `green-required-masking.txt` | 13 tests nuevos OK en 2,092 s; exit 0. |
| `privacy-final-verified.txt` | 134 tests del área OK en 40,985 s; exit 0, después del último cambio funcional. |
| `check-final.txt` | Django check: cero incidencias; exit 0. |
| `migrations-final.txt` | Sin cambios de migración; exit 0. |
| `git diff --check` | Sin errores; exit 0. |

Los intentos intermedios permanecen en archivos separados. `privacy-final-pass.txt` contiene el error de la primera versión de la prueba de revocación; no representa el resultado final. El rojo de revocación posterior permitió la respuesta sintética para obtener una aserción de comportamiento en lugar de una excepción de fixture.

Comandos de verificación (ejecutados con `rtk proxy`, settings de test y salida redirigida a los archivos indicados):

```powershell
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_required_masking --settings=regulai.test_settings --verbosity=1
rtk proxy .venv/Scripts/python.exe regulai/manage.py test front.test_required_masking front.test_chat_flow front.test_pipeline front.test_pipeline_privacy front.test_state front.test_policy_simulator front.test_history_departments front.test_onboarding front.test_review front.test_review_regressions front.test_backend_hardening front.tests --settings=regulai.test_settings --verbosity=1
rtk proxy .venv/Scripts/python.exe regulai/manage.py check --settings=regulai.test_settings
rtk proxy .venv/Scripts/python.exe regulai/manage.py makemigrations --check --dry-run --settings=regulai.test_settings
rtk git diff --check
```

## Contratos y alcance

- Los fixtures compartidos crean `ChatFixture.required_mask`, autorizan `obfuscation:<id>` y usan `masking.max_call_cost='0'`. `test_pipeline.jev_http` también responde al contrato HTTP de máscara. Los registros cuentan máscara de entrada, generación, máscara de respuesta y las comprobaciones semánticas que correspondan.
- `send_chat_message(actor, command, *, call_observer=None)` admite un observador interno con `before_call(call) -> token` y `after_call(call, token)`. Recibe copias de metadatos persistidos, nunca el contenido. La reserva se realiza antes de red y va seguida de una segunda validación de autorización. Las denegaciones previas a transporte se marcan `not_started`, coste `0`, procedencia `not_incurred`; costes comunicados, estimados y cero configurado tienen procedencias distintas. `cost_bound` conserva la cota original y `cost_exposure_bound` guarda la exposición mayor o la ausencia comprobada de envío.
- La prueba de las tres entradas utiliza el SDK OpenAI real con `httpx.MockTransport`, y comprueba los bytes que llegarían al transporte. Los demás proveedores y máscaras son sintéticos. No hubo llamadas pagadas ni proveedor vivo.
- Los 134 tests usan SQLite de test aislado. La integración operativa PostgreSQL/Gunicorn/HTTPS pertenece al coordinador y se registra por separado.
- La barrera exige una respuesta válida del enmascarador autorizado. Estas pruebas no miden la detección semántica de un proveedor vivo ni garantizan que un detector identifique cualquier dato sensible. No se añade ofuscación reversible.
- `views.mask_texts` conserva su import público; la implementación está en `front/masking.py`. Configuraciones antiguas sin máscara o con detección parcial dejan de enviar y deben completarse explícitamente.

`manifest.json` contiene SHA-256 de los bytes exactos de los archivos fuente y registros verificados en el árbol de trabajo. No se realizó commit ni se tocó el índice desde este agente.
