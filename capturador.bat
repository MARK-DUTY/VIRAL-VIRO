@echo off
REM Herramienta de Captura de Pantalla para VIRAL-VIRO
REM Este archivo ejecuta el capturador de pantalla sin mostrar consola

setlocal enabledelayedexpansion

REM Obtener la ruta del directorio actual
set SCRIPT_DIR=%~dp0

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python no esta instalado o no esta en el PATH
    echo.
    echo Soluciones:
    echo 1. Instala Python desde https://www.python.org
    echo 2. O usa Python desde la carpeta de VIRAL-VIRO
    echo 3. O agrega Python a tu PATH de Windows
    echo.
    pause
    exit /b 1
)

REM Verificar si el script existe
if not exist "%SCRIPT_DIR%screen_capture_tool.py" (
    echo.
    echo ERROR: No se encontro screen_capture_tool.py
    echo Asegurate de que este archivo esta en la misma carpeta que capturador.bat
    echo.
    pause
    exit /b 1
)

REM Ejecutar el capturador en background sin mostrar consola
start "" pythonw "%SCRIPT_DIR%screen_capture_tool.py"

REM Mensaje de confirmacion rapido
echo Abriendo herramienta de captura...
timeout /t 1 /nobreak >nul

exit /b 0
