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
curl -fsS -o app.py %BASE%/app.py
curl -fsS -o requirements.txt %BASE%/requirements.txt
curl -fsS -o pipeline\article.py %BASE%/pipeline/article.py
curl -fsS -o pipeline\assemble.py %BASE%/pipeline/assemble.py
curl -fsS -o pipeline\avatar.py %BASE%/pipeline/avatar.py
curl -fsS -o pipeline\config.py %BASE%/pipeline/config.py
curl -fsS -o pipeline\images.py %BASE%/pipeline/images.py
curl -fsS -o pipeline\music.py %BASE%/pipeline/music.py
curl -fsS -o pipeline\runner.py %BASE%/pipeline/runner.py
curl -fsS -o pipeline\script_gen.py %BASE%/pipeline/script_gen.py
curl -fsS -o pipeline\subtitles.py %BASE%/pipeline/subtitles.py
curl -fsS -o pipeline\voice.py %BASE%/pipeline/voice.py
curl -fsS -o templates\index.html %BASE%/templates/index.html
curl -fsS -o static\app.js %BASE%/static/app.js
curl -fsS -o static\style.css %BASE%/static/style.css

echo.
echo ============================================================
echo    ACTUALIZACION TERMINADA
echo    Ahora cierra el programa (la ventana negra) si esta abierto
echo    y vuelve a abrirlo con run_windows.bat
echo ============================================================
echo.
pause
