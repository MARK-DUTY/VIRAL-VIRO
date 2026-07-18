# Script PowerShell para crear atajo de capturador en el escritorio
# Ejecucion: powershell -ExecutionPolicy Bypass -File crear_atajo_capturador.ps1

$ErrorActionPreference = "Stop"

# Obtener la ruta de este script
$scriptPath = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$batchFile = Join-Path $scriptPath "capturador.bat"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "📸 Capturador VIRAL-VIRO.lnk"

# Verificar que el archivo .bat existe
if (-not (Test-Path $batchFile)) {
    Write-Host "ERROR: No se encontro capturador.bat en $batchFile" -ForegroundColor Red
    Read-Host "Presiona Enter para cerrar"
    exit 1
}

try {
    # Crear el atajo
    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $batchFile
    $shortcut.WorkingDirectory = $scriptPath
    $shortcut.WindowStyle = 7  # Minimizado
    $shortcut.Description = "Capturador de pantalla para VIRAL-VIRO - Arrastra el mouse para capturar"
    $shortcut.Save()
    
    Write-Host ""
    Write-Host "✅ EXITO: Atajo creado en el escritorio" -ForegroundColor Green
    Write-Host "   Nombre: 📸 Capturador VIRAL-VIRO.lnk" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Para usar:" -ForegroundColor Cyan
    Write-Host "   1. Haz doble clic en el atajo del escritorio" -ForegroundColor Cyan
    Write-Host "   2. Arrastra el mouse para seleccionar la region" -ForegroundColor Cyan
    Write-Host "   3. Suelta el clic para capturar" -ForegroundColor Cyan
    Write-Host "   4. Elige una opcion: Subir/Guardar/Descartar" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Presiona Enter para cerrar"
}
catch {
    Write-Host "ERROR: No se pudo crear el atajo" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host "Presiona Enter para cerrar"
    exit 1
}
