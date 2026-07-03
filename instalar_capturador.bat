@echo off
REM ============================================================
REM  INSTALADOR del Capturador de Pantalla
REM  - Instala las librerias necesarias
REM  - Configura que se abra SOLO cada vez que prendes la PC
REM  - Lo abre ahora mismo para que lo empieces a usar
REM ============================================================

setlocal
set SCRIPT_DIR=%~dp0

echo ============================================================
echo   Instalando el Capturador de Pantalla...
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
echo Instalando librerias ^(Pillow, pystray^)... espera un momento.
python -m pip install --user --quiet Pillow pystray
echo Librerias listas.
echo.

REM 3) Crear un acceso directo en la carpeta de INICIO de Windows
REM    (asi se abre solo cada vez que prendes o reinicias la PC)
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS=%TEMP%\_mk_capturador_shortcut.vbs

echo Configurando el arranque automatico...
> "%VBS%" echo Set oWS = WScript.CreateObject("WScript.Shell")
>>"%VBS%" echo sLink = "%STARTUP_DIR%\Capturador de Pantalla.lnk"
>>"%VBS%" echo Set oLink = oWS.CreateShortcut(sLink)
>>"%VBS%" echo oLink.TargetPath = "pythonw.exe"
>>"%VBS%" echo oLink.Arguments = """%SCRIPT_DIR%screen_capture_tool.py"""
>>"%VBS%" echo oLink.WorkingDirectory = "%SCRIPT_DIR%"
>>"%VBS%" echo oLink.Description = "Capturador de Pantalla (icono en la barra de tareas)"
>>"%VBS%" echo oLink.WindowStyle = 7
>>"%VBS%" echo oLink.Save
cscript //nologo "%VBS%"
del "%VBS%" >nul 2>&1

echo.
echo ============================================================
echo   LISTO! El capturador quedo instalado.
echo ============================================================
echo.
echo   - A partir de ahora, cada vez que prendas la PC, el
echo     iconito de camara aparecera solo junto al reloj.
echo   - Lo vamos a abrir ahora mismo para que lo uses ya.
echo.

REM 4) Abrirlo ahora mismo (sin consola)
start "" pythonw "%SCRIPT_DIR%screen_capture_tool.py"

echo Presiona una tecla para cerrar esta ventana.
pause >nul
exit /b 0
