@echo off
chcp 65001 >nul
title ViroFeed AI Personal - Actualizar
color 0B

echo ============================================================
echo    ViroFeed AI Personal - ACTUALIZAR
echo    Descarga la ULTIMA version del codigo desde GitHub.
echo    (No toca tu archivo .env ni tus videos)
echo ============================================================
echo.

REM --- Verificar que git este instalado ---
git --version >nul 2>&1
if errorlevel 1 (
  echo  ERROR: No tienes Git instalado.
  echo  Descargalo aqui: https://git-scm.com/download/win
  echo  Instala con las opciones por defecto y vuelve a intentar.
  echo.
  pause
  exit /b 1
)

REM --- Verificar que estamos en un repositorio git ---
if not exist .git (
  echo  Este directorio no es un repositorio git.
  echo  Clonando el repositorio desde cero...
  echo.
  cd ..
  git clone https://github.com/MARK-DUTY/VIRAL-VIRO.git VIRAL-VIRO-temp
  if errorlevel 1 (
    echo.
    echo  ERROR: No se pudo clonar. Revisa tu internet y que tengas
    echo  acceso al repositorio en GitHub.
    pause
    exit /b 1
  )
  echo.
  echo  Repositorio clonado en la carpeta VIRAL-VIRO-temp.
  echo  Copia tu archivo .env a esa carpeta y usa esa en adelante.
  pause
  exit /b 0
)

REM --- Actualizar con git pull ---
echo Descargando la ultima version...
echo.
git pull origin main
if errorlevel 1 (
  echo.
  echo  AVISO: git pull fallo. Intentando forzar la actualizacion...
  git fetch origin main
  git reset --hard origin/main
  if errorlevel 1 (
    echo.
    echo  ERROR: No se pudo actualizar. Posibles causas:
    echo  - No tienes internet
    echo  - No tienes acceso al repositorio en GitHub
    echo  - Git no esta configurado con tu cuenta
    echo.
    echo  Solucion: abre Git Bash aqui y ejecuta:
    echo    git pull origin main
    echo.
    pause
    exit /b 1
  )
)

echo.
echo ============================================================
echo    ACTUALIZACION TERMINADA
echo    Ahora cierra el programa ^(la ventana negra^) si esta abierto
echo    y vuelve a abrirlo con run_windows.bat
echo ============================================================
echo.
pause
