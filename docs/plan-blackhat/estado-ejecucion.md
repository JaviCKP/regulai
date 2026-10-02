# Estado observado de la implementación

Inicio: 2 de octubre de 2026. Rama local `codex/community-blackhat`, base `6a0f667`.

## Base reproducida

Python 3.12.11, entorno `.venv`, instalación exacta de `requirements.txt` raíz (45 paquetes, Django 4.2.28). No se instaló la lista interior: contenía versiones divergentes y `docx` además de `python-docx`.

- `rtk proxy .venv/Scripts/python.exe regulai/manage.py check`: correcto.
- `rtk proxy .venv/Scripts/python.exe regulai/manage.py test front api --settings=regulai.test_settings`: una prueba, fallo previo `0 != 1` al esperar una alerta del validador. La función devuelve coincidencias y documenta que la orquestación crea alertas. Se corrige la expectativa para comprobar coincidencia real y ausencia de efectos; las alertas se probarán desde HTTP.
- `rtk proxy .venv/Scripts/python.exe regulai/manage.py makemigrations --check --dry-run --settings=regulai.test_settings`: sin cambios.

Configuración local creada una sola vez por `scripts/bootstrap_local.py`, claves aleatorias no mostradas y SQLite `community-local.sqlite3`, sin tocar bases anteriores. Skills oficiales y tareas locales documentadas en `docs/agents/`.

## Pendientes actuales

Planes funcionales 01–12 en ejecución. Comparación y calibración real de proveedores pendientes de credenciales y presupuesto expresamente autorizados; no se harán llamadas de pago en este encargo. No hay mediciones reales de ahorro o precisión semántica.

## Plataforma actualizada y arranque visual

Django 5.2.17 LTS y DRF 3.18.1 instalados. El resto de versiones se conserva en esta entrega acotada. `requirements.txt` raíz es la fuente única y el archivo interior la incluye. Revisión de compatibilidad: [Django 5.0](https://docs.djangoproject.com/en/5.0/releases/5.0/), [5.1](https://docs.djangoproject.com/en/5.1/releases/5.1/), [5.2](https://docs.djangoproject.com/en/5.2/releases/5.2/), [DRF](https://www.django-rest-framework.org/community/release-notes/). La rama 5.2 mantiene soporte extendido hasta abril de 2028 según el [calendario oficial](https://www.djangoproject.com/download/).

Comprobado: tres tests (incluyen login web, chat, autenticación REST, cifrado y carga de texto), `check`, `makemigrations --check --dry-run` y `uv pip check`: correctos. Migraciones 0001–0025 aplicadas en la base local nueva. Inicio de sesión y chat abiertos y usados en navegador en `http://127.0.0.1:8765/`; 8000 estaba ocupado por otra aplicación. Cuenta exclusivamente sintética `community-local-demo`, contraseña local `Local-demo-only-2026!`, sin proveedor configurado ni datos reales. Esta contraseña es pública de desarrollo: no reutilizar esa cuenta en una instalación expuesta.

Revisión de preparación: Standards sin hallazgos; Spec pidió completar documento de evidencia tardía, registrar apertura real y actualizar estados de skills. Hecho. El documento sintético tiene la condición «17 dias» después de 10.000 caracteres.
