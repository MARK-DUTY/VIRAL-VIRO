# ✅ Checklist de Pruebas - Capturador de Pantalla

Documento para verificar que la herramienta de captura funciona correctamente en tu Windows.

## 📋 Pre-requisitos

Antes de empezar, verifica:

- [ ] **Windows 10 o superior** instalado
- [ ] **Python 3.8+** instalado y en PATH
  - Verifica: Abre CMD y escribe `python --version`
  - Debe mostrar: `Python 3.X.X` (X.X.X es la versión)
- [ ] **Pillow instalada**
  - Verifica: `pip list | findstr Pillow`
  - Si no aparece, instala: `pip install Pillow`

---

## 🧪 Pruebas Fase 1: Archivos

### ✅ Verificar archivos existen

En la carpeta de VIRAL-VIRO, comprueba que estos archivos existen:

- [ ] `screen_capture_tool.py` - Script principal de captura
- [ ] `capturador.bat` - Ejecutable Windows
- [ ] `crear_atajo_capturador.ps1` - Script para crear atajo
- [ ] `launch_screenshot_tool.py` - Wrapper opcional
- [ ] `test_screen_capture.py` - Script de pruebas
- [ ] `README_CAPTURADOR.md` - Documentación
- [ ] `TESTING_CHECKLIST.md` - Este archivo

---

## 🧪 Pruebas Fase 2: Ejecución Directa

### ✅ Prueba 1: Ejecutar capturador.bat

1. **Haz doble clic en `capturador.bat`**
   - [ ] Se abre una ventana (puede ser rápido o minimizado)
   - [ ] Debería abrirse el capturador (overlay negro semi-transparente)
   - [ ] Aparece el cursor como "crosshair" (cruz)

2. **Si esto funcionó:** ✅ Continúa a Fase 3
3. **Si no funcionó:**
   - [ ] Abre CMD en la carpeta de VIRAL-VIRO
   - [ ] Ejecuta: `python screen_capture_tool.py`
   - [ ] Revisa el error en la consola
   - [ ] Ver sección "Solucionar Problemas"

---

## 🧪 Pruebas Fase 3: Funcionalidad de Captura

### ✅ Prueba 2: Capturar una región

1. **Ejecuta `capturador.bat`** (o `python screen_capture_tool.py`)
2. **Pantalla cambió a overlay semi-transparente gris/negro**
   - [ ] ¿Sí? Continúa
   - [ ] ¿No? Problema con overlay - ver solucionar problemas

3. **Arrastra el mouse:**
   - Presiona clic izquierdo
   - Arrastra en diagonal (ej: de arriba-izquierda a abajo-derecha)
   - [ ] Aparece un rectángulo blanco mientras arrastras
   - [ ] El rectángulo sigue tu mouse

4. **Suelta el clic izquierdo:**
   - [ ] Aparece un popup con la captura
   - [ ] Se ve la región que capturaste
   - [ ] Muestra las dimensiones (ej: "800 × 600 px")
   - [ ] Tiene 3 botones: "Subir", "Guardar", "Descartar"

---

## 🧪 Pruebas Fase 4: Opciones del Popup

### ✅ Prueba 3: Botón "Guardar"

1. **En el popup, haz clic en "💾 Guardar"**
2. **Se abre un diálogo para guardar archivo**
   - [ ] Puedes elegir la carpeta
   - [ ] El nombre por defecto es `screenshot_YYYYMMDD_HHMMSS.png`
   - [ ] Puedes cambiar el nombre
3. **Haz clic en "Guardar"**
   - [ ] Aparece mensaje "✅ Guardado"
   - [ ] Se cierra el popup
4. **Verifica la imagen se guardó**
   - [ ] Abre Explorador de Archivos
   - [ ] Navega a la carpeta donde guardaste
   - [ ] Verifica que la imagen aparece
   - [ ] Haz doble clic para ver la captura

---

### ✅ Prueba 4: Botón "Descartar"

1. **Ejecuta `capturador.bat` de nuevo**
2. **Captura una región (cualquiera)**
3. **En el popup, haz clic en "❌ Descartar"**
   - [ ] Aparece mensaje "Screenshot descartado"
   - [ ] Se cierra el popup y la herramienta
   - [ ] Puedes ejecutar `capturador.bat` de nuevo sin problemas

---

### ✅ Prueba 5: Botón "Subir a VIRAL-VIRO"

**Esta prueba requiere acceso a VIRAL-VIRO corriendo:**

1. **Abre VIRAL-VIRO** en tu navegador (http://localhost:5000)
2. **Ve a una escena** (sección "Revisar y aprobar")
3. **Haz clic en el botón "📸 Capturar región"**
   - [ ] Se abre un alerta explicando los pasos
   - [ ] Se abre `screen_capture_tool.py` automáticamente
4. **Captura una región**
5. **En el popup, haz clic en "📤 Subir a VIRAL-VIRO"**
   - [ ] Aparece mensaje "Screenshot copiado al clipboard"
6. **Vuelve a VIRAL-VIRO en el navegador**
7. **En la misma escena, mira la zona "📋 Pegar imagen/video"**
8. **Presiona Ctrl+V**
   - [ ] Aparece la captura que tomaste
   - [ ] Se ve como imagen de preview

---

## 🧪 Pruebas Fase 5: Atajo del Escritorio

### ✅ Prueba 6: Crear atajo

1. **Abre PowerShell como Administrador**
   - Click derecho en escritorio → "Abrir PowerShell como administrador"
   - O busca "PowerShell" en inicio y ejecuta como admin

2. **Ve a la carpeta de VIRAL-VIRO**
   - [ ] `cd C:\ruta\a\VIRAL-VIRO` (reemplaza con tu ruta real)

3. **Ejecuta el script:**
   - [ ] `powershell -ExecutionPolicy Bypass -File crear_atajo_capturador.ps1`

4. **Verifica el atajo se creó**
   - [ ] Cierra PowerShell
   - [ ] Mira el escritorio
   - [ ] Debe haber un ícono llamado "📸 Capturador VIRAL-VIRO.lnk"

5. **Prueba el atajo**
   - [ ] Haz doble clic en el atajo del escritorio
   - [ ] Se abre el capturador
   - [ ] Funciona igual que ejecutar `capturador.bat`

---

## 🆘 Solucionar Problemas

### ❌ "Python no está instalado"

**Síntoma:** Cuando ejecuto `capturador.bat`, veo error de Python

**Solución:**
1. Descarga Python desde https://www.python.org (3.8 o superior)
2. Ejecuta el instalador
3. **IMPORTANTE:** Marca la opción "Add Python to PATH"
4. Haz clic en "Install Now"
5. Cierra y abre CMD nuevamente
6. Verifica: `python --version`

---

### ❌ "Pillow no está instalada"

**Síntoma:** Error sobre `PIL` o `ImageGrab`

**Solución:**
```cmd
pip install Pillow
```

---

### ❌ "No aparece el overlay/crosshair"

**Síntoma:** Ejecuto `capturador.bat` pero no veo nada

**Soluciones posibles:**
1. Asegúrate que Python está instalado (`python --version`)
2. Abre CMD en la carpeta de VIRAL-VIRO
3. Ejecuta: `python screen_capture_tool.py`
4. Mira qué error sale
5. Si dice `no module named 'tkinter'`, instala: `pip install tk`

---

### ❌ "El popup sale pero se ve extraño"

**Síntoma:** El popup de opciones no se ve bien o faltan botones

**Solución:**
1. Verifica que tienes Windows 10 o superior
2. Actualiza el sistema operativo si es necesario
3. Si sigue pasando, revisa que Pillow está actualizada:
   ```cmd
   pip install --upgrade Pillow
   ```

---

### ❌ "No se puede crear el atajo"

**Síntoma:** Error cuando ejecuto `crear_atajo_capturador.ps1`

**Solución:**
1. Abre PowerShell como Administrador (importante)
2. Ejecuta: `powershell -ExecutionPolicy Bypass -File crear_atajo_capturador.ps1`
3. Si sale error de permiso, intenta:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. Luego ejecuta el script de nuevo

---

### ❌ "El screenshot no se sube a VIRAL-VIRO"

**Síntoma:** Hago clic en "Subir a VIRAL-VIRO" pero no aparece en VIRAL-VIRO

**Posibles causas:**
1. VIRAL-VIRO no está corriendo (http://localhost:5000 abierto en navegador)
2. No estás en la sección "Revisar y aprobar"
3. El clipboard no se copió correctamente

**Solución:**
1. Verifica que VIRAL-VIRO está abierto en el navegador
2. Ve a una escena (antes tienes que generar un video)
3. En el popup, haz clic en "Guardar" en lugar de "Subir"
4. Una vez guardado, en VIRAL-VIRO haz clic en "⬆️ Subir foto/video"
5. Busca la imagen que acabas de guardar

---

## 📊 Matriz de Pruebas

| # | Prueba | Status | Notas |
|---|--------|--------|-------|
| 1 | Archivos existen | [ ] | Verificar en carpeta VIRAL-VIRO |
| 2 | capturador.bat abre | [ ] | Debe abrir overlay |
| 3 | Captura región | [ ] | Debe funcionar drag del mouse |
| 4 | Popup aparece | [ ] | Con vista previa y botones |
| 5 | Botón "Guardar" | [ ] | Debe guardar PNG |
| 6 | Botón "Descartar" | [ ] | Debe cerrar sin hacer nada |
| 7 | Botón "Subir" | [ ] | Debe copiar al clipboard |
| 8 | Atajo se crea | [ ] | En escritorio |
| 9 | Atajo funciona | [ ] | Abre capturador |
| 10 | Integración VIRAL-VIRO | [ ] | Pega con Ctrl+V |

---

## ✅ Resumen Final

Si todas las pruebas pasan:

1. ✅ Herramienta de captura funciona perfectamente
2. ✅ Se integra con VIRAL-VIRO
3. ✅ Puedes usar desde escritorio o desde VIRAL-VIRO
4. ✅ Listo para producción

**¡Felicidades! 🎉 La herramienta está lista para usar.**

---

**Versión:** 1.0  
**Última actualización:** Julio 2026  
**Autor:** Kiro Development Assistant
