# 📸 Capturador de Pantalla para VIRAL-VIRO

Herramienta para capturar regiones de tu pantalla con un simple drag del mouse y subirlas automáticamente a VIRAL-VIRO.

## 🚀 Instalación Rápida

### Opción 1: Crear Atajo en el Escritorio (Recomendado)

1. **Abre PowerShell** como Administrador:
   - Click derecho en el escritorio
   - Selecciona "Abrir PowerShell aquí como administrador"
   - O busca "PowerShell" en el menú inicio y ejecútalo como admin

2. **Ejecuta este comando:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File "C:\ruta\a\VIRAL-VIRO\crear_atajo_capturador.ps1"
   ```
   (Reemplaza `C:\ruta\a\VIRAL-VIRO\` con la ruta real de tu carpeta)

3. **Presiona Enter** y se creará un atajo en tu escritorio 📸

4. **Listo!** Ya puedes hacer doble clic en el atajo del escritorio para capturar

---

### Opción 2: Ejecutar Directamente (Sin Atajo)

Simplemente haz doble clic en:
```
capturador.bat
```

---

## 📖 Cómo Usar

### Flujo 1: Desde VIRAL-VIRO (Recomendado)

1. En VIRAL-VIRO, ve a la sección de **Revisar y aprobar** (en una escena)
2. Haz clic en el botón **"📸 Capturar región"** (en cualquier escena)
3. Se abrirá automáticamente la herramienta de captura
4. Arrastra el mouse para seleccionar la región que quieres capturar
5. Suelta el clic → verás la captura en un popup
6. Elige una opción:
   - **📤 Subir a VIRAL-VIRO** → se copia al clipboard
   - **💾 Guardar** → guarda en tu PC
   - **❌ Descartar** → vuelve a intentar
7. Si subiste a VIRAL-VIRO, haz **Ctrl+V** en la escena para pegar

### Flujo 2: Desde el Atajo (Independiente)

1. Haz doble clic en el atajo **"📸 Capturador VIRAL-VIRO.lnk"** del escritorio
2. Se abrirá el capturador
3. Selecciona la región con drag del mouse
4. En el popup, elige:
   - **Guardar** → guarda la imagen en tu PC
   - **Descartar** → vuelve a intentar

---

## ⚙️ Requisitos

- **Python 3.8+** instalado en tu PC
- **Librerías Python** (se instalan automáticamente con VIRAL-VIRO):
  - `Pillow` (PIL)
  - `tkinter` (viene con Python)

### Verificar que Python está instalado:

Abre una terminal (PowerShell o CMD) y ejecuta:
```
python --version
```

Si sale algo como `Python 3.11.0`, ¡está listo!

---

## 🎯 Atajos de Teclado

| Tecla | Acción |
|-------|--------|
| **Clic izquierdo + Arrastrar** | Seleccionar región |
| **Soltar clic** | Capturar la región |
| **Escape** | Cancelar la captura |

---

## 🐛 Solucionar Problemas

### "Python no está instalado"

**Solución:** Descarga e instala Python desde https://www.python.org
- Asegúrate de marcar "Add Python to PATH" durante la instalación

### "No se puede crear el atajo"

**Solución:** Ejecuta PowerShell como Administrador:
- Click derecho en PowerShell → "Ejecutar como administrador"
- Luego ejecuta el comando del atajo

### "No aparece la herramienta de captura"

**Solución:** Verifica que `screen_capture_tool.py` esté en la misma carpeta que `capturador.bat`

### "El screenshot no se sube a VIRAL-VIRO"

**Solución:** 
1. Asegúrate de estar en la sección de "Revisar y aprobar"
2. Haz clic en "Subir a VIRAL-VIRO" (no en Guardar)
3. Luego presiona **Ctrl+V** en la zona de paste (o en "Pegar imagen/video")

---

## 📝 Notas

- Los screenshots se capturan en **PNG** (mejor calidad)
- Si haces clic en "Guardar", los archivos van a tu carpeta de **Descargas** por defecto
- La herramienta es **gratis y sin conexión** - funciona completamente offline
- Los screenshots se **guardan temporalmente** en `%TEMP%` durante el proceso

---

## 🆘 ¿Necesitas Ayuda?

Si algo no funciona:

1. Verifica que Python está instalado (`python --version`)
2. Verifica que `screen_capture_tool.py` existe
3. Intenta ejecutar `capturador.bat` directamente (no el atajo)
4. Si sigue sin funcionar, revisa que estés en Windows 10 o superior

---

**Versión:** 1.0  
**Última actualización:** Julio 2026
