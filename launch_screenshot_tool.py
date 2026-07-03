#!/usr/bin/env python3
"""
Script wrapper para ejecutar screen_capture_tool.py en background
sin bloquear la interfaz web
"""
import subprocess
import sys
import os

def launch_screenshot_tool():
    """Lanza la herramienta de captura en un proceso separado"""
    try:
        # Obtener la ruta del script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, 'screen_capture_tool.py')
        
        # Ejecutar en background sin mostrar ventana de consola (Windows)
        if sys.platform == 'win32':
            # CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                [sys.executable, script_path],
                creationflags=0x08000000  # No mostrar ventana de consola
            )
        else:
            subprocess.Popen([sys.executable, script_path])
        
        return True
    except Exception as e:
        print(f"Error al lanzar screenshot tool: {e}")
        return False

if __name__ == "__main__":
    launch_screenshot_tool()
