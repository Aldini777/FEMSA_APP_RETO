# FEMSA_APP_RETO

## Ejecutar App 2 con Docker

La App 2 puede trabajar directamente con el CSV: no necesita cargarlo a
PostgreSQL. El CSV debe tener las columnas esperadas por la aplicación
(encabezado que comienza con `EquipoID`); se validan los nombres, el orden y
que existan filas de datos.

### Inicio rápido en Windows

1. Instala e inicia Docker Desktop.
2. Haz doble clic en [`iniciar_app.bat`](./iniciar_app.bat).
3. En el navegador, selecciona `data.csv` en el control **Archivo CSV** de la
   barra lateral.
4. Usa los filtros, el mapa y las visualizaciones de App 2. En la barra lateral
   puedes descargar un reporte ejecutivo o técnico en PDF.

También puedes iniciar el contenedor desde una terminal en la carpeta del
repositorio:

```powershell
docker compose up --build -d
```

Abre <http://localhost:8501> y carga el CSV en la aplicación. Para detenerla:

```powershell
docker compose down
```

Si necesitas revisar el inicio del contenedor:

```powershell
docker compose logs -f app
```

La imagen contiene el código, las dependencias, el mapa y el logo, pero no
incluye datos ni el archivo `.env`. El CSV se selecciona desde la interfaz y
no se importa a una base de datos. La opción de PostgreSQL sigue disponible en
la aplicación, pero requiere una base configurada por separado.