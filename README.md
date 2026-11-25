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

No se incluye `.env` ni archivos CSV en el ZIP: el archivo de entorno puede
contener credenciales y los CSV contienen datos del usuario. La imagen incluye
el código, las dependencias, el mapa y el logo, pero no los datos. La opción de
PostgreSQL sigue disponible en la app, aunque requiere una base configurada
por separado.

---

## Documentación Técnica y Replicabilidad

### 1. En general, ¿qué hace la aplicación?
La aplicación es un dashboard interactivo desarrollado en **Streamlit** (servido en el puerto `8501`) para el reto de **FEMSA**, orientado al análisis operativo de equipos y visualización de métricas, mapas geográficos de Latinoamérica y generación de reportes automatizados. Permite trabajar directamente con archivos CSV validados (encabezado iniciando en `EquipoID`, validación de nombres, orden de columnas y existencia de filas) o mediante integración con base de datos PostgreSQL, ofreciendo filtros interactivos, visualizaciones gráficas y descarga de reportes ejecutivos y técnicos en PDF.

### 2. Contenido del repositorio
* `Dockerfile` y `compose.yaml`: Definición de la imagen y configuración del servicio para ejecutar la aplicación en contenedores Docker.
* `iniciar_app.bat`: Script de arranque automatizado para Windows.
* `.streamlit/config.toml` y `reportes/.streamlit/config.toml`: Configuración de tema visual y parámetros de Streamlit.
* `.vscode/settings.json`, `.dockerignore` y `.gitignore`: Configuraciones de entorno de desarrollo y reglas de exclusión para Docker y Git.
* `reportes/app.py`: Punto de entrada principal de la aplicación.
* `reportes/app2.py`: Interfaz y lógica principal del dashboard interactivo (carga/validación de CSV, filtros, navegación y descarga de reportes PDF).
* `reportes/reporte.py`: Generación de reportes ejecutivos y técnicos en formato PDF.
* `reportes/visualizaciones.py`: Construcción de gráficas y componentes visuales del dashboard.
* `reportes/mapa_latam.json`: Datos geográficos en formato GeoJSON/JSON para el mapa de Latinoamérica.
* `reportes/assets/logo_femsa.png`: Logotipo institucional utilizado en la interfaz y en los reportes PDF.
* `reportes/app1/conexion.py`: Manejo de conexión a base de datos (PostgreSQL).
* `reportes/app1/cargar_datos.py`: Rutinas de carga y procesamiento de datos hacia base de datos.
* `reportes/app1/sql/crear_tabla.sql`: Script SQL para crear la estructura de tabla en PostgreSQL.
* `reportes/requirements.txt` y `reportes/app1/requirements.txt`: Listados de dependencias de Python para la aplicación y el módulo `app1`.

### 3. Versiones de software y librerías
* **Software del entorno:**
  * Docker / Docker Desktop (`docker` y `docker compose` v2).
  * Python 3 (`python3` / `pip`) utilizado en la construcción de la imagen y ejecución local.
  * Git / utilidades de terminal (`unzip`, PowerShell en Windows o Terminal en macOS/Linux).
  * PostgreSQL (opcional, si se utiliza la integración con base de datos en lugar de la carga directa de CSV).
  * *[Completa con tu equipo: anota las versiones exactas verificadas en su entorno, por ejemplo `Python 3.11.x`, `Docker Desktop 4.x`, `PostgreSQL 15/16`].*
* **Librerías de Python:**
  * Declaradas en `reportes/requirements.txt` y `reportes/app1/requirements.txt` (instaladas automáticamente al construir la imagen Docker o mediante `pip install -r ...`).
  * *[Completa con tu equipo: copia aquí las versiones exactas contenidas en `reportes/requirements.txt` y `reportes/app1/requirements.txt`, por ejemplo `streamlit==...`, `pandas==...`, etc.]*.

### 4. Cómo se puede reproducir el proyecto

#### Reproducción con Docker (Windows, macOS y Linux)
1. Asegúrate de tener **Docker Desktop** abierto y con el motor activo (`docker info`).
2. Descarga o clona el repositorio y descomprime el archivo ZIP si aplica:
   ```bash
   cd ~/Downloads
   unzip -o "FEMSA_APP_RETO-main.zip"
   cd FEMSA_APP_RETO-main
   ```
3. Construye y levanta el contenedor:
   ```bash
   docker compose up --build --force-recreate
   ```
   *(En Windows también puedes ejecutar directamente `iniciar_app.bat` o `docker compose up --build -d`)*.
4. Abre `http://localhost:8501` en tu navegador y carga el archivo CSV correspondiente.

#### Reproducción local con Python (sin Docker)
1. Entra a la carpeta `reportes/`:
   ```bash
   cd reportes
   ```
2. Crea y activa un entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   *(En Windows PowerShell: `.\.venv\Scripts\Activate.ps1`)*.
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   pip install -r app1/requirements.txt
   ```
4. Ejecuta la aplicación:
   ```bash
   streamlit run app.py
   ```

### 5. Fundamentos que deben cumplirse para replicar la aplicación
* **Motor de contenedores o entorno Python funcional:** Docker Desktop activo con acceso a internet en la primera compilación, o Python 3 con las dependencias de ambos `requirements.txt` instaladas.
* **Estructura de rutas intacta:** Preservar la jerarquía del repositorio (`reportes/`, `reportes/assets/logo_femsa.png`, `reportes/mapa_latam.json`, `reportes/app1/...`).
* **Calidad y formato de datos:** Si se usa carga por CSV, el archivo debe iniciar con encabezado `EquipoID`, cumplir con las columnas esperadas en el orden requerido y contener al menos una fila de datos; si se usa PostgreSQL, contar con el servicio activo, credenciales válidas y el esquema creado con `reportes/app1/sql/crear_tabla.sql`.
* **Configuración segura:** Mantener credenciales o variables de entorno (`.env`) fuera del control de versiones y del ZIP compartido.

### 6. Cómo FEMSA puede replicar el proyecto
1. **Despliegue del código base:** Obtener el repositorio desde GitHub o el paquete ZIP oficial sin archivos sensibles (`.env` o CSV con datos confidenciales).
2. **Alineación de datos:** Utilizar archivos CSV operativos que cumplan la estructura validada por la app (iniciando en `EquipoID`) o configurar una instancia de PostgreSQL ejecutando `reportes/app1/sql/crear_tabla.sql` y adaptando `reportes/app1/conexion.py` y `reportes/app1/cargar_datos.py` a los estándares internos de FEMSA.
3. **Ejecución en entorno controlado:** Levantar el servicio mediante `docker compose up --build -d` (o integrarlo en el orquestador/servidor interno de FEMSA) exponiendo el puerto `8501`.
4. **Validación operativa y de reportes:** Probar los filtros, el mapa de Latinoamérica (`mapa_latam.json`), las gráficas (`visualizaciones.py`) y la exportación de reportes ejecutivos y técnicos en PDF (`reporte.py`) con datos representativos de operación.

### 7. Problemas de programación encontrados y cómo se resolvieron
* **Ejecución de comandos de Docker fuera de la carpeta raíz:** Ejecutar `docker compose up --build` desde un directorio padre (como `Downloads`) en lugar de dentro de `FEMSA_APP_RETO-main` provoca `no configuration file provided: not found`; se resuelve navegando primero a la carpeta donde se encuentra `compose.yaml`.
* **Diferencias entre sistemas operativos (Windows vs. macOS):** El archivo `iniciar_app.bat` está diseñado para Windows, mientras que en macOS se utilizan comandos de terminal (`unzip`, `python3`, `source .venv/bin/activate`, `docker compose`).
* **Cambios de código no reflejados tras actualizar el ZIP:** Docker empaqueta el código al construir la imagen; al descargar una nueva versión del ZIP, es necesario detener y recrear el contenedor (`docker compose down` y `docker compose up --build --force-recreate`) para que aplique los cambios recientes.
* **Validación de estructura de archivos CSV:** Se implementaron comprobaciones de encabezado (iniciando en `EquipoID`), columnas esperadas, orden y presencia de filas para evitar fallos silenciosos o gráficas vacías al cargar archivos incompletos o con formato distinto.
* ***[Completa con tu equipo: agrega aquí incidencias específicas de programación o datos que hayan surgido en `app2.py`, `reporte.py`, `visualizaciones.py` o `app1/` y cómo las resolvieron]*.**
