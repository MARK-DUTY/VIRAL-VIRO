@echo off
chcp 65001 >nul
title ViroFeed AI Personal - Actualizar
color 0B

echo ============================================================
echo    ViroFeed AI Personal - ACTUALIZAR
echo    Descarga la ultima version del codigo desde GitHub.
echo    (No toca tu archivo .env ni tus videos)
echo ============================================================
echo.

set BASE=https://raw.githubusercontent.com/MARK-DUTY/VIROFEED-PERSONAL/main

echo Actualizando archivos...
curl -s -o app.py %BASE%/app.py
curl -s -o requirements.txt %BASE%/requirements.txt
curl -s -o pipeline\article.py %BASE%/pipeline/article.py
curl -s -o pipeline\assemble.py %BASE%/pipeline/assemble.py
curl -s -o pipeline\avatar.py %BASE%/pipeline/avatar.py
curl -s -o pipeline\config.py %BASE%/pipeline/config.py
curl -s -o pipeline\images.py %BASE%/pipeline/images.py
curl -s -o pipeline\runner.py %BASE%/pipeline/runner.py
curl -s -o pipeline\script_gen.py %BASE%/pipeline/script_gen.py
curl -s -o pipeline\subtitles.py %BASE%/pipeline/subtitles.py
curl -s -o pipeline\voice.py %BASE%/pipeline/voice.py
curl -s -o templates\index.html %BASE%/templates/index.html
curl -s -o static\app.js %BASE%/static/app.js
curl -s -o static\style.css %BASE%/static/style.css

echo.
echo ============================================================
echo    ACTUALIZACION TERMINADA
echo    Ahora cierra el programa (la ventana negra) si esta abierto
echo    y vuelve a abrirlo con run_windows.bat
echo ============================================================
echo.
pause
