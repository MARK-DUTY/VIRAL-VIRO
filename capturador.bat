@echo off
REM ============================================================
REM  ProCam - abrir manualmente (foto + grabador de video)
REM  Instala lo necesario (solo la 1a vez) y arranca el icono
REM ============================================================

setlocal
set SCRIPT_DIR=%~dp0

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Instala Python desde https://www.python.org  (marca "Add to PATH").
    echo.
    pause
    exit /b 1
)

REM Instalar librerias necesarias (si ya estan, no pasa nada)
echo Verificando librerias (Pillow, pystray)...
python -m pip install --quiet --user Pillow pystray >nul 2>&1

REM Verificar FFmpeg (para grabar video); si falta, lo descarga
if not exist "%SCRIPT_DIR%ffmpeg\ffmpeg.exe" (
    echo Descargando FFmpeg para grabar video (solo la primera vez)...
    python "%SCRIPT_DIR%download_ffmpeg.py"
)

REM Ejecutar ProCam SIN ventana de consola
start "" pythonw "%SCRIPT_DIR%screen_capture_tool.py"

exit /b 0
