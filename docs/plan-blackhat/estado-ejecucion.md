# Estado observado de la implementación

Inicio: 2 de octubre de 2026. Rama local `codex/community-blackhat`, base `6a0f667`.

## Base reproducida

Python 3.12.11, entorno `.venv`, instalación exacta de `requirements.txt` raíz (45 paquetes, Django 4.2.28). No se instaló la lista interior: contenía versiones divergentes y `docx` además de `python-docx`.

- `rtk proxy .venv/Scripts/python.exe regulai/manage.py check`: correcto.
- `rtk proxy .venv/Scripts/python.exe regulai/manage.py test front api --settings=regulai.test_settings`: una prueba, fallo previo `0 != 1` al esperar una alerta del validador. La función devuelve coincidencias y documenta que la orquestación crea alertas. Se corrige la expectativa para comprobar coincidencia real y ausencia de efectos; las alertas se probarán desde HTTP.
- `rtk proxy .venv/Scripts/python.exe regulai/manage.py makemigrations --check --dry-run --settings=regulai.test_settings`: sin cambios.

Configuración local creada una sola vez por `scripts/bootstrap_local.py`, claves aleatorias no mostradas y SQLite `community-local.sqlite3`, sin tocar bases anteriores. Skills oficiales y tareas locales documentadas en `docs/agents/`.

## Pendientes actuales

Actualización de plataforma y planes funcionales 01–12 en ejecución. Comparación y calibración real de proveedores pendientes de credenciales y presupuesto expresamente autorizados; no se harán llamadas de pago en este encargo. No hay mediciones reales de ahorro o precisión semántica.
