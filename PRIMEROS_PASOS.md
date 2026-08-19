# 🚀 PRIMEROS PASOS - Herramienta de Captura de Pantalla

## 📋 PASO 1: Descargar e Instalar Pillow

La herramienta necesita la librería **Pillow** para procesar imágenes.

### ¿Cómo hacerlo?

1. **Abre CMD o PowerShell en tu Windows**
   - Presiona `Win + R`
   - Escribe: `cmd`
   - Presiona Enter

2. **En la ventana negra que se abre, copia y pega esto:**
   ```
   pip install Pillow
   ```
   - Presiona Enter
   - Espera a que termine (verás mensajes de instalación)
   - Cuando termine, debería decir "Successfully installed Pillow"

3. **Verifica que se instaló correctamente:**
   ```
   pip list | findstr Pillow
   ```
   - Presiona Enter
   - Debería mostrar: `Pillow  X.X.X` (la versión instalada)

### ✅ PASO 1 COMPLETADO cuando veas que Pillow aparece en `pip list`

---

## 📋 PASO 2: Ir a la Carpeta de VIRAL-VIRO

Necesitamos navegar a donde está instalado VIRAL-VIRO en tu PC.

### ¿Cómo hacerlo?

1. **Abre el Explorador de Archivos (File Explorer)**
   - Presiona `Win + E`
   - O haz doble clic en "Esta PC"

2. **Navega a la carpeta de VIRAL-VIRO**
   - Busca en tu disco C: o donde hayas guardado VIRAL-VIRO
   - Ejemplo: `C:\Users\TuNombre\VIRAL-VIRO`
   - O: `C:\Users\TuNombre\Desktop\VIRAL-VIRO`
   - O pregunta dónde la pusiste

3. **Cuando abras la carpeta, deberías ver archivos como:**
   - `app.py`
   - `screen_capture_tool.py` ← ESTE es el nuevo que agregamos
   - `capturador.bat` ← ESTE también es nuevo
   - `README_CAPTURADOR.md` ← ESTE es nuevo

### ✅ PASO 2 COMPLETADO cuando veas la carpeta de VIRAL-VIRO abierta en el Explorador

---

## 📋 PASO 3: Ejecutar el Script de Validación

Vamos a validar que todo está listo en tu sistema.

### ¿Cómo hacerlo?

1. **Abre CMD o PowerShell** (igual que en Paso 1)
   - Presiona `Win + R`
   - Escribe: `cmd`
   - Presiona Enter

2. **Navega a la carpeta de VIRAL-VIRO**
   - Copia tu ruta (ej: `C:\Users\TuNombre\VIRAL-VIRO`)
   - En CMD, escribe:
   ```
   cd C:\Users\TuNombre\VIRAL-VIRO
   ```
   - Reemplaza con tu ruta real
   - Presiona Enter

3. **Ejecuta el script de validación**
   ```
   python test_screen_capture.py
   ```
   - Presiona Enter
   - Espera a que termine

4. **Verifica los resultados**
   - Deberías ver un resumen de pruebas
   - Busca esta línea: `Total: X/5 pruebas pasadas`
   - Lo importante es que Pillow esté como ✅ PASS

### ✅ PASO 3 COMPLETADO cuando ejecutes `python test_screen_capture.py` sin errores

---

## 📸 Cuando Hayas Completado los 3 Pasos

Una vez que hayas hecho estos 3 pasos:

1. **Dime que completaste el Paso 1** (Pillow instalado)
2. **Dime que completaste el Paso 2** (Carpeta VIRAL-VIRO encontrada)
3. **Dime que completaste el Paso 3** (Script de validación ejecutado)

Y **cópiame la salida completa del script de validación** (todo lo que sale en la pantalla negra).

Entonces te daré los **siguientes pasos** para instalar el atajo en el escritorio y probar la herramienta.

---

## ⚠️ Si Algo Falla

Si en cualquier paso te sale un error:

1. **Cópiame el error exacto** que ves en la pantalla
2. **Dime en qué paso fallaste** (1, 2, o 3)
3. Yo te ayudaré a arreglarlo

---

## 🎯 Resumen Rápido

| Paso | Qué Hacer | ✅ Listo |
|------|-----------|---------|
| 1 | Instalar Pillow con `pip install Pillow` | [ ] |
| 2 | Abrir carpeta VIRAL-VIRO en Explorador | [ ] |
| 3 | Ejecutar `python test_screen_capture.py` | [ ] |

---

**¡Adelante! 🚀 Cuéntame cuando termines los 3 primeros pasos.**
