# 📥 GUÍA DE INSTALACIÓN - PASO A PASO

## 🔍 VERIFICAR ENTORNO PYTHON

Abre **PowerShell** o **CMD** en tu carpeta de proyecto:

```powershell
# Ver versión de Python
python --version
# → Python 3.12.5 (o superior)

# Ver dónde está Python
python -c "import sys; print(sys.executable)"
# → C:\Users\bensa\OneDrive\Documentos\Programacion\projectos\sales_system\.venv\Scripts\python.exe

# Ver si ya est activado venv
# Si aparece (.venv) al inicio = está activo
```

---

## ⚡ INSTALACIÓN RÁPIDA (5 minutos)

### 1️⃣ Activar entorno virtual (si no está activo)

**En Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
# → Deberías ver (.venv) al inicio de la línea
```

**En Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**En macOS/Linux:**
```bash
source .venv/bin/activate
```

### 2️⃣ Instalar librerías

Copia y pega este comando completo:

```bash
pip install --upgrade pip && pip install qrcode[pil] pywin32 reportlab pillow ttkthemes
```

**Esto instalará:**
- `qrcode[pil]` - Generación de códigos QR
- `pywin32` - Acceso a impresoras Windows
- `reportlab` - Generación de PDFs
- `pillow` - Manejo de imágenes
- `ttkthemes` - Temas visuales Tkinter

### 3️⃣ Configurar pywin32 (IMPORTANTE para Windows)

```bash
python -m pywin32_postinstall -install
```

⚠️ **Si da error de permisos**, ejecuta como Administrador:

```powershell
# En PowerShell como Admin:
python -m pywin32_postinstall -install -remove
python -m pywin32_postinstall -install
```

---

## ✅ VERIFICACIÓN

Ejecuta estos comandos para verificar que todo está correcto:

```bash
# Test 1: Código QR
python -c "import qrcode; print('✓ qrcode instalado')"

# Test 2: Reportlab
python -c "import reportlab; print('✓ reportlab instalado')"

# Test 3: PIL
python -c "from PIL import Image; print('✓ PIL instalado')"

# Test 4: Impresoras (Windows)
python -c "import win32print; print('✓ win32print instalado')"

# Test 5: Módulos nuevos de la app
python -c "from facturas_verifactu import FacturaVeriFACTU; print('✓ VeriFACTU OK')"
python -c "from tickets import TicketSimplificado; print('✓ Tickets OK')"
python -c "from albaranes import AlbaranEntrega; print('✓ Albaranes OK')"
python -c "from presupuestos import Presupuestos; print('✓ Presupuestos OK')"
python -c "from impresoras import GestorImpresoras; print('✓ Impresoras OK')"
python -c "from barcode_scanner import EscanerCodigoBarras; print('✓ Scanner OK')"
```

Si todos dicen ✓, **¡estás listo!**

---

## 📋 INSTALACIÓN POR LIBRERÍAS INDIVIDUALES

Si prefieres instalar de una en una:

### qrcode (Códigos QR)
```bash
pip install qrcode[pil]
pip install --upgrade Pillow  # Mejora de manejo de imágenes
```

### reportlab (Generación de PDFs)
```bash
pip install reportlab
```

### pywin32 (Impresoras Windows)
```bash
pip install pywin32
python -m pywin32_postinstall -install
```

### ttkthemes (Temas visuales)
```bash
pip install ttkthemes
```

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### ❌ "ModuleNotFoundError: No module named 'qrcode'"
```bash
pip install qrcode[pil] --upgrade
```

### ❌ "ModuleNotFoundError: No module named 'win32print'"
```bash
# 1. Reinstala pywin32
pip install pywin32 --upgrade --force-reinstall

# 2. Ejecuta post-install
python -m pywin32_postinstall -install -remove
python -m pywin32_postinstall -install

# 3. Si aún hay error, ejecuta como Admin y repite el paso 2
```

### ❌ "ModuleNotFoundError: No module named 'PIL'"
```bash
pip install Pillow --upgrade
```

### ❌ "ModuleNotFoundError: No module named 'reportlab'"
```bash
pip install reportlab --upgrade
```

### ❌ Entorno virtual no se activa
```powershell
# Verifica que .venv exista
Test-Path .\.venv

# Si no existe, crealo:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### ❌ Permiso denegado en instalación
```bash
# Ejecuta PowerShell como Administrador (botón derecho)
# Luego intenta instalar
```

---

## 📦 LISTA COMPLETA DE DEPENDENCIAS

```bash
# Verificar todas las dependencias instaladas
pip list
```

Deberías ver algo como esto:

```
Package           Version
---------         -------
qrcode            8.0  (o superior)
Pillow            10.0  (o superior)
reportlab         4.0  (o superior)
pywin32           305  (o superior)
ttkthemes         3.2  (o superior)
tkinter           <incluido en Python>
sqlite3           <incluido en Python>
```

---

## 🚀 PUESTA EN MARCHA

Una vez instalado todo, ejecuta:

```bash
# Desde la carpeta del proyecto, con venv activado:
python index.py
```

La aplicación debería abrirse sin errores.

---

## 🔗 REFERENCIAS OFICIALES

- **qrcode**: https://github.com/lincolnloop/python-qrcode
- **reportlab**: https://www.reportlab.com/
- **pywin32**: https://github.com/pywin32/pywin32
- **Pillow**: https://python-pillow.org/
- **ttkthemes**: https://github.com/TkinterEasyGUI/ttkbootstrap

---

## 💡 TIPS DE MANTENIMIENTO

### Actualizar todas las dependencias
```bash
pip install --upgrade qrcode reportlab pywin32 Pillow ttkthemes
```

### Crear requirements.txt para futuros proyectos
```bash
pip freeze > requirements.txt
# Luego, en un nuevo proyecto:
pip install - r requirements.txt
```

### Ver detalles de una librerías
```bash
pip show qrcode
pip show reportlab
pip show pywin32
```

### Desinstalar (si es necesario)
```bash
pip uninstall qrcode reportlab pywin32 Pillow ttkthemes -y
```

---

## ✨ LISTO PARA USAR

Una vez completados todos los pasos:

✅ Facturas VeriFACTU con QR  
✅ Tickets de 80mm  
✅ Albaranes de entrega  
✅ Métodos de pago integrados  
✅ Módulo de presupuestos  
✅ Impresoras disponibles  
✅ Escáner de código de barras  

**¡Tu aplicación está lista para producción!** 🎉

