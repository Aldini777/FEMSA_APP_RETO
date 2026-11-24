# FEMSA_APP_RETO

## Ejecutar App 2 con Docker

La App 2 puede trabajar directamente con el CSV: no necesita cargarlo a
PostgreSQL. El CSV debe tener las columnas esperadas por la aplicación
(encabezado que comienza con `EquipoID`); se validan los nombres, el orden y
que existan filas de datos.

### Requisitos

- Windows con Docker Desktop instalado y abierto; espera a que el motor indique
  que está activo.
- En el primer inicio se necesita conexión a internet para descargar la imagen
  base de Python e instalar las dependencias.

Puedes comprobar que Docker está disponible desde PowerShell:

```powershell
docker --version
docker compose version
docker info
```

### Iniciar la aplicación

1. Instala [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/) si aún no lo tienes y ábrelo.
2. Desde el Explorador de archivos, haz doble clic en
   [`iniciar_app.bat`](./iniciar_app.bat). El script construye e inicia la app y
   abre el navegador. La primera construcción puede tardar varios minutos.
3. En el navegador, selecciona tu `data.csv` en el control **Archivo CSV** de la
   barra lateral.
4. Usa los filtros, el mapa y las visualizaciones. Desde la barra lateral
   también puedes descargar un reporte ejecutivo o técnico en PDF.

La aplicación valida el encabezado, las columnas esperadas y que el CSV tenga
filas de datos. No es necesario cargarlo a PostgreSQL.

### Inicios posteriores y detener la app

La imagen de Docker y sus capas quedan guardadas en el equipo. Para iniciar la
versión ya construida sin solicitar otra construcción, abre PowerShell en la
carpeta del repositorio y ejecuta:

```powershell
docker compose up -d
```

Abre <http://localhost:8501> si el navegador no se abrió automáticamente. Para
detener la app sin eliminar el contenedor:

```powershell
docker compose stop
```

Para iniciarla nuevamente después de detenerla:

```powershell
docker compose start
```

`docker compose down` elimina el contenedor y la red, pero conserva la imagen;
puedes volver a crear el contenedor con `docker compose up -d`.

### Actualizar la aplicación

Docker ejecuta una copia del código incluida en la imagen: los cambios que
hagas en `app2.py`, en las gráficas u otros archivos no aparecen solos. Después
de modificar el código:

1. Abre Docker Desktop y espera a que indique que el motor está en ejecución.
   Puedes comprobar desde PowerShell que Docker responde con:

   ```powershell
   docker info
   ```

2. Abre una terminal en la carpeta raíz del proyecto, donde está `compose.yaml`.
   Si PowerShell está en otra carpeta, cambia a la del proyecto con:

   ```powershell
   Set-Location -LiteralPath "C:\ruta\de\tu\proyecto"
   ```

   Sustituye la ruta de ejemplo por la ubicación real del proyecto.

3. Reconstruye la imagen e inicia el contenedor:

```powershell
docker compose up --build -d
```

4. Recarga <http://localhost:8501> en el navegador. Docker reutiliza las capas
   que no cambiaron, por lo que normalmente no vuelve a descargar e instalar
   todas las dependencias. Si cambias `requirements.txt`, instalará las
   dependencias nuevas.

El lanzador `iniciar_app.bat` también ejecuta `docker compose up --build -d`.

Para consultar los registros del contenedor:

```powershell
docker compose logs -f app
```

### Compartir la aplicación

Comparte un ZIP con el proyecto completo, no solo el archivo `.bat`. La otra
persona necesita Docker Desktop en Windows; en el primer inicio necesitará
internet para construir la imagen y después podrá cargar su propio CSV desde la
interfaz. No es una aplicación independiente ni un `.exe`.

No incluyas `.env` ni archivos CSV en el ZIP: el archivo de entorno puede
contener credenciales y los CSV contienen datos del usuario. La imagen incluye
el código, las dependencias, el mapa y el logo, pero no los datos. La opción de
PostgreSQL sigue disponible en la app, aunque requiere una base configurada
por separado.