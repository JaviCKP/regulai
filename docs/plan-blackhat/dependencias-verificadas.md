# Dependencias comprobadas

Fuente de instalación: `requirements.txt` de la raíz. `regulai/requirements.txt` remite a ella.
Python local: 3.12.11; Django 5.2.17 LTS; DRF 3.18.1.

El 2 de octubre de 2026, `pip-audit` detectó 96 avisos en 12 paquetes fijados en la instalación anterior. Se actualizaron anyio, cryptography, SimpleJWT, PyJWT, idna, lxml, Pillow, python-dotenv, requests, urllib3 y sqlparse a versiones corregidas. PyPDF2 se sustituyó por pypdf 6.19.0, su continuación mantenida, conservando la extracción en proceso separado y sus límites. [Historia oficial de pypdf](https://pypdf.readthedocs.io/en/stable/meta/history.html).

Comprobaciones realizadas:

- Instalación de los 45 paquetes desde la lista única con `uv pip install --python .venv/Scripts/python.exe -r requirements.txt`.
- Auditoría posterior: `uv tool run pip-audit -r requirements.txt`: **ninguna vulnerabilidad conocida encontrada**. Es el resultado de esa base de avisos en esa fecha, no una garantía de ausencia de vulnerabilidades.
- 45 pruebas de documentos sintéticos, conectores, Jev, selección, verificación y runtime: correctas tras las actualizaciones.

La auditoría se ejecuta mediante la caché aislada de herramientas de uv; no se instala globalmente ni forma parte de las dependencias de producción.

Django 5.2 tiene soporte extendido hasta abril de 2028 según el [calendario oficial](https://www.djangoproject.com/download/#supported-versions). Antes de trasladar una instalación existente, conservar copia de su base de datos y configuración y ejecutar las migraciones; no sustituir claves de cifrado.
