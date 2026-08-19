@echo off
REM ============================================================
REM  INSTALADOR de ProCam (foto + grabador de video)
REM  - Instala las librerias necesarias
REM  - Descarga FFmpeg (motor para grabar video) automaticamente
REM  - Configura que se abra SOLO cada vez que prendes la PC
REM  - Lo abre ahora mismo para que lo empieces a usar
REM ============================================================

setlocal
set SCRIPT_DIR=%~dp0

echo ============================================================
echo   Instalando ProCam (foto + video)...
echo ============================================================
echo.

REM 1) Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Instala Python desde https://www.python.org  ^(marca "Add to PATH"^).
    echo.
    pause
    exit /b 1
)

REM 2) Instalar librerias necesarias
echo [1/4] Instalando librerias ^(Pillow, pystray, keyboard^)... espera un momento.
python -m pip install --user --quiet Pillow pystray keyboard
echo       Librerias listas.
echo.

REM 3) Descargar FFmpeg (motor para grabar video)
echo [2/4] Descargando FFmpeg para grabar video ^(80-120 MB, puede tardar^)...
python "%SCRIPT_DIR%download_ffmpeg.py"
echo.

REM 4) Crear acceso directo en la carpeta de INICIO de Windows
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS=%TEMP%\_mk_procam_shortcut.vbs

echo [3/4] Configurando el arranque automatico...
> "%VBS%" echo Set oWS = WScript.CreateObject("WScript.Shell")
>>"%VBS%" echo sLink = "%STARTUP_DIR%\ProCam.lnk"
>>"%VBS%" echo Set oLink = oWS.CreateShortcut(sLink)
>>"%VBS%" echo oLink.TargetPath = "pythonw.exe"
>>"%VBS%" echo oLink.Arguments = """%SCRIPT_DIR%screen_capture_tool.py"""
>>"%VBS%" echo oLink.WorkingDirectory = "%SCRIPT_DIR%"
>>"%VBS%" echo oLink.Description = "ProCam - foto y grabador de video (icono en la barra de tareas)"
>>"%VBS%" echo oLink.WindowStyle = 7
>>"%VBS%" echo oLink.Save
cscript //nologo "%VBS%"
del "%VBS%" >nul 2>&1
echo       Arranque automatico listo.
echo.

echo ============================================================
echo   LISTO! ProCam quedo instalado.
echo ============================================================
echo.
echo   - Cada vez que prendas la PC, el iconito aparecera solo
echo     junto al reloj.
echo   - CLIC en el icono         = tomar foto (screenshot)
echo   - CLIC DERECHO en el icono = menu (Grabar video / Salir)
echo   - Lo vamos a abrir ahora mismo para que lo uses ya.
echo.

REM 5) Abrirlo ahora mismo (sin consola)
echo [4/4] Abriendo ProCam...
start "" pythonw "%SCRIPT_DIR%screen_capture_tool.py"

echo.
echo Presiona una tecla para cerrar esta ventana.
pause >nul
exit /b 0
