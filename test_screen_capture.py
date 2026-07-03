#!/usr/bin/env python3
"""
Script de prueba para verificar que screen_capture_tool.py funciona
Ejecutar en Windows: python test_screen_capture.py
"""

import sys
import subprocess
from pathlib import Path

def test_python_version():
    """Verifica versión de Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ requerido")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def test_imports():
    """Verifica que las librerías necesarias estén disponibles"""
    imports_needed = [
        ("tkinter", "Interface gráfica"),
        ("PIL", "Pillow - procesamiento de imágenes"),
        ("subprocess", "Ejecución de procesos"),
        ("json", "Serialización JSON"),
    ]
    
    all_ok = True
    for module, description in imports_needed:
        try:
            __import__(module)
            print(f"✅ {module:20} - {description}")
        except ImportError:
            print(f"❌ {module:20} - {description} (NO ENCONTRADO)")
            all_ok = False
    
    return all_ok

def test_file_exists():
    """Verifica que el archivo screen_capture_tool.py existe"""
    script_path = Path(__file__).parent / "screen_capture_tool.py"
    if script_path.exists():
        print(f"✅ screen_capture_tool.py encontrado")
        return True
    else:
        print(f"❌ screen_capture_tool.py NO encontrado")
        return False

def test_syntax():
    """Verifica la sintaxis del Python"""
    try:
        import py_compile
        script_path = Path(__file__).parent / "screen_capture_tool.py"
        py_compile.compile(str(script_path), doraise=True)
        print(f"✅ Sintaxis válida en screen_capture_tool.py")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Error de sintaxis: {e}")
        return False

def test_windows_only():
    """Verifica que estamos en Windows"""
    if sys.platform != 'win32':
        print(f"⚠️  Sistema operativo: {sys.platform} (se requiere Windows)")
        return False
    else:
        print(f"✅ Windows detectado")
        return True

def main():
    print("=" * 60)
    print("  🧪 Prueba de Screen Capture Tool")
    print("=" * 60)
    print()
    
    tests = [
        ("Python Version", test_python_version),
        ("Windows Detection", test_windows_only),
        ("File Exists", test_file_exists),
        ("Imports", test_imports),
        ("Syntax", test_syntax),
    ]
    
    results = {}
    for name, test_fn in tests:
        print(f"\n📋 {name}:")
        try:
            results[name] = test_fn()
        except Exception as e:
            print(f"❌ Error en prueba: {e}")
            results[name] = False
    
    print()
    print("=" * 60)
    print("  📊 Resumen de Pruebas")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} - {name}")
    
    print()
    print(f"Total: {passed}/{total} pruebas pasadas")
    print()
    
    if passed == total:
        print("🎉 ¡Todo está listo! Puedes usar screen_capture_tool.py")
        print()
        print("Para ejecutar:")
        print("  1. Haz doble clic en capturador.bat")
        print("  2. O ejecuta: python screen_capture_tool.py")
        print("  3. O desde VIRAL-VIRO: haz clic en '📸 Capturar región'")
        return 0
    else:
        print("⚠️  Hay problemas. Revisa los errores arriba.")
        print()
        print("Soluciones:")
        print("  - Instala Python 3.8+: https://www.python.org")
        print("  - Instala Pillow: pip install Pillow")
        print("  - Asegúrate de estar en Windows")
        return 1

if __name__ == "__main__":
    sys.exit(main())
