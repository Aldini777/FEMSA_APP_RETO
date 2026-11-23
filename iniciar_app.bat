@echo off
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 goto missing_docker

docker compose version >nul 2>nul
if errorlevel 1 goto missing_compose

docker compose up --build -d
if errorlevel 1 goto startup_error

timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"
exit /b 0

:missing_docker
echo No se encontro el comando Docker.
echo Instala Docker Desktop para Windows y vuelve a abrir esta ventana.
goto finish

:missing_compose
echo Docker esta instalado, pero no se encontro Docker Compose.
echo Actualiza o reinstala Docker Desktop y vuelve a intentar.
goto finish

:startup_error
echo Docker esta disponible, pero no pudo iniciar FEMSA App.
echo Abre Docker Desktop, espera a que el motor este activo e intenta de nuevo.

:finish
pause
exit /b 1
