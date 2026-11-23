@echo off
cd /d "%~dp0"

docker compose up --build -d
if errorlevel 1 goto error

timeout /t 3 /nobreak >nul
start "" "http://localhost:8501"
exit /b 0

:error
echo No se pudo iniciar FEMSA App. Verifica que Docker Desktop este instalado y activo.
pause
exit /b 1
