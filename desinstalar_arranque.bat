@echo off
REM ============================================================
REM  Quitar el Capturador del ARRANQUE automatico de Windows
REM  (deja de abrirse solo al prender la PC)
REM  El programa NO se borra: lo puedes seguir abriendo a mano
REM  con capturador.bat cuando quieras.
REM ============================================================

set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set LINK=%STARTUP_DIR%\Capturador de Pantalla.lnk

if exist "%LINK%" (
    del "%LINK%"
    echo Listo. El capturador YA NO se abrira solo al prender la PC.
) else (
    echo No estaba configurado el arranque automatico. Nada que quitar.
)

echo.
pause
exit /b 0
