# Instalación local con agente real

Este arranque usa Django ASGI, PostgreSQL y un worker que ejecuta código en
microVM E2B privadas. No arranca proveedores simulados ni carga conversaciones
de demostración. La cuenta inicial es **admin / admin** y el acceso se publica
únicamente en `127.0.0.1`.

## Requisitos

- Windows x86-64 con Docker Desktop/WSL2, o Linux x86-64 con Docker Engine.
- Virtualización de CPU habilitada y `/dev/kvm` disponible para Docker, con
  virtualización anidada. El instalador prueba que puede crear una VM KVM real.
- Python 3.11 o posterior; Docker en modo contenedores Linux.
- Al menos 10 GiB asignados a Docker, 16 GiB de RAM física recomendados y
  50 GB libres para imágenes, caché y disco persistente.
- Internet para descargar Ubuntu y construir las imágenes. La primera
  instalación tarda bastante más que los arranques posteriores.

Mac/ARM no está soportado por este ejecutor local. No se sustituye E2B por
ejecución en el equipo anfitrión cuando falta KVM.

## Primera instalación

1. Descarga o clona este repositorio privado.
2. Copia el archivo privado **regulai-private.json** junto a `setup.py`.
   Contiene los usuarios, conexiones API y políticas exportados de la instancia
   real. Se entrega por separado y está excluido de Git. No lo compartas junto
   al código ni lo subas a incidencias o capturas.
3. Con Docker arrancado, ejecuta desde la carpeta del proyecto:

   Windows:
   ```powershell
   .\setup.cmd install
   ```

   Linux:
   ```sh
   sh setup.sh install
   ```

   También puedes conservar el archivo fuera del repositorio:
   ```sh
   python setup.py install --private-profile "/ruta privada/regulai-private.json"
   ```

4. Cuando aparezca `READY`, abre <http://127.0.0.1:8800/login/> y entra con
   **admin / admin**. El chat abre el agente profesional por defecto.

El instalador crea claves internas nuevas para cada equipo y vuelve a cifrar
las credenciales importadas. No importa chats, archivos generados, sesiones ni
facturación histórica. Reiniciar o repetir la instalación no restablece una
contraseña que ya hayas cambiado.

## Uso diario

```sh
python setup.py start
python setup.py status
python setup.py stop
```

Mantén abierta la ventana de `start`: proporciona el túnel local. `Ctrl+C`
cierra el acceso local; `stop` detiene los servicios. Los datos permanecen en
el volumen Docker `regulai-v2-state`. No borres ese volumen para actualizar.
El instalador no reemplaza una instalación ajena ni elimina datos existentes.
No es un procedimiento de actualización automática entre versiones.

Si el puerto 8800 está ocupado, identifica el servicio o usa `--port 8801`.
`python setup.py doctor` comprueba Docker, arquitectura y memoria; el arranque
comprueba además KVM anidado, PostgreSQL, web, E2B y conversión DOCX/PDF en una
microVM con salida directa a Internet bloqueada. Si una comprobación falla,
no muestra `READY`. Consulta `docker logs regulai-v2-vm` para fallos de la VM.

## APIs y alcance

El perfil privado preparado actualmente contiene la conexión real de DeepSeek.
Las peticiones al modelo consumen el saldo de esa API. La instalación y sus
pruebas de disponibilidad no hacen llamadas de generación de pago.
No hay clave Tavily configurada: la búsqueda con Tavily queda desactivada.
La lectura web a través del servidor está disponible; el navegador JavaScript
del agente permanece desactivado hasta completar su validación.

`admin/admin` es exclusivamente el acceso local solicitado. Este instalador
no configura un servidor público ni HTTPS. No expongas su túnel en la LAN.

## Comprobaciones del código

```sh
python -m unittest ops.setup.test_installer
```

CI ejecuta cada módulo en un proceso nuevo: SQLite para las evaluaciones
aisladas heredadas y PostgreSQL para el agente. La prueba marcada
`namespace_integration` requiere el laboratorio Linux preparado y no forma
parte de ese CI. La disponibilidad real de E2B y LibreOffice se comprueba
además durante `setup.py start`.

Las dependencias de aplicación y ejecutor se construyen en contenedores; no
hace falta instalar RTK, uv, Node, LibreOffice ni PostgreSQL en el anfitrión.
Las versiones Python, PostgreSQL, SDK y plantillas se fijan en los Dockerfiles
y locks. Los paquetes del sistema de la VM se descargan de Ubuntu; la
reproducibilidad aquí es funcional, no una imagen idéntica byte a byte.
