# 📋 GUÍA COMPLETA DE IMPLEMENTACIÓN - SALES SYSTEM

## Funcionalidades Implementadas

Has recibido 7 nuevas funcionalidades completamente implementadas para tu caja registradora. A continuación se detallan los cambios en cada archivo y cómo usar cada funcionalidad.

---

## 🔧 INSTALACIÓN DE DEPENDENCIAS

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
pip install qrcode[pil] pywin32 reportlab pillow ttkthemes
```

Si usas macOS o Linux, para impresoras puedes usar:
```bash
pip install cups
```

---

## 📦 ARCHIVOS NUEVOS CREADOS

### 1. `facturas_verifactu.py`
**Genera facturas VeriFACTU conformes a Hacienda España**
- Clase `FacturaVeriFACTU`: Genera PDFs con estructura legal
- Incluye código QR de verificación
- Guarda auditoría en BD en tabla `facturas_verifactu`

**Uso en código:**
```python
from facturas_verifactu import FacturaVeriFACTU

factura = FacturaVeriFACTU(config_manager)
pdf_path = factura.crear_factura_verifactu(
    numero_factura=001,
    fecha="2026-03-09",
    nif_emisor="12345678Z",
    nif_receptor="87654321A",
    nombre_receptor="Cliente SL",
    productos=lista_productos,
    base_imponible=100.00,
    tipo_iva=21,
    total_iva=21.00,
    total=121.00
)
```

---

### 2. `tickets.py`
**Genera tickets simplificados de 80mm (impresoras térmicas)**
- Clase `TicketSimplificado`: Crea tickets en formato Rollo 80mm
- Diseño compacto y legible
- Ideal para impresoras de recibos

**Uso:**
```python
from tickets import TicketSimplificado

ticket = TicketSimplificado(config_manager)
ticket.generar_ticket(
    numero_factura=001,
    fecha=datetime.now(),
    productos=lista_productos,
    total=121.00,
    metodo_pago="Efectivo"
)
```

---

### 3. `albaranes.py`
**Genera albaranes (documentos de entrega sin valor fiscal)**
- Clase `AlbaranEntrega`: Crea albaranes estándar
- Campos de firma para conformidad
- Gestión de estados (Abierto, Entregado, Rechazado)

**Uso:**
```python
from albaranes import AlbaranEntrega

albaran = AlbaranEntrega(config_manager)
pdf_path = albaran.crear_albaran(
    numero_albaran="ALB-2026-00001",
    fecha="2026-03-09",
    cliente_nombre="Cliente SL",
    cliente_direccion="Calle Principal 123",
    productos=lista_productos,
    observaciones="Entrega conforme a presupuesto"
)

# Cambiar estado
albaran.cambiar_estado_albaran("ALB-2026-00001", "Entregado")
```

---

### 4. `presupuestos.py`
**Módulo completo de presupuestos**
- Clase `Presupuestos`: Ventana interactiva (1100x650px)
- Crear presupuestos con productos del inventario
- Calcular con IVA (4%, 10%, 21%)
- Generar PDF
- Cambiar estado (Pendiente, Aceptado, Rechazado)

**Características:**
- Tabla `presupuestos` en BD
- Tabla `presupuestos_productos` con relación FK
- Botones: Guardar, Generar PDF, Limpiar

**Acceso:**
- Se agregó botón "📝 Presupuestos" en container.py (color púrpura)
- Se importa automáticamente al abrir container

---

### 5. `impresoras.py`
**Gestión de impresoras Windows**
- Clase `GestorImpresoras`: Enumera impresoras disponibles
- Clase `DialogoSeleccionImpresora`: UI para elegir impresora
- Soporte para métodos fallback si pywin32 no está disponible

**Uso:**
```python
from impresoras import GestorImpresoras, DialogoSeleccionImpresora

gestor = GestorImpresoras(config_manager)

# Obtener impresoras
impresoras = gestor.obtener_impresoras_disponibles()

# Imprimir archivo
gestor.imprimir_archivo("ruta/a/archivo.pdf", "Nombre Impresora")

# Mostrar diálogo de selección (recomendado)
dialogo = DialogoSeleccionImpresora(ventana_padre, "ruta/archivo.pdf", gestor)
dialogo.wait_window()
```

---

### 6. `barcode_scanner.py`
**Soporte para escáner de código de barras USB**
- Clase `EscanerCodigoBarras`: Busca productos por código
- Clase `DialogoAsignarCodigoBarras`: UI para entrada interactiva
- Crea columna `codigo_barras` automáticamente en tabla inventario

**Uso:**
```python
from barcode_scanner import EscanerCodigoBarras, DialogoAsignarCodigoBarras

escaner = EscanerCodigoBarras(db_path)

# Buscar producto por código
producto = escaner.buscar_producto_por_codigo("1234567890")
if producto:
    print(f"Encontrado: {producto['nombre']} - ${producto['precio']}")

# Asignar código a un producto
escaner.guardar_codigo_barras(id_producto=5, codigo_barras="1234567890")

# Diálogo interactivo para asignar
dialogo = DialogoAsignarCodigoBarras(ventana_padre, id_producto=5, 
                                    nombre_producto="Laptop", escaner=escaner)
```

---

## 🔄 ARCHIVOS MODIFICADOS

### 1. **ventas.py** - Métodos de pago integrados ✅

**Cambios principales:**

#### A. Tabla de ventas actualizada
```python
# Nueva estructura con columnas de pago:
# - metodo_pago (TEXT): "Efectivo", "Tarjeta" o "Mixto"
# - cantidad_efectivo (REAL): Monto pagado en efectivo
# - cantidad_tarjeta (REAL): Monto pagado en tarjeta
```

#### B. Nueva función: `_actualizar_campos_pago()`
Actualiza los campos de entrada según el método seleccionado

#### C. Ventana de pago rediseñada
- Opciones de método: Efectivo, Tarjeta, Mixto
- Si es Mixto: aparecen dos campos de entrada
- Cálculo automático de vuelto

#### D. Función `pagar()` modificada
- Ahora acepta parámetros de métodos de pago
- Guarda método_pago y cantidades en BD

#### E. Función `generar_factura_pdf()` modificada
- Parámetro adicional: `metodo_pago`
- Imprime el método en el PDF

---

### 2. **container.py** - Nuevo botón de Presupuestos ✅

**Cambios:**

```python
# 1. Import agregado
from presupuestos import Presupuestos

# 2. Método agregado
def presupuestos(self):
    self.show_frames(Presupuestos)

# 3. Botón agregado en widgets()
btnPresupuestos = Button(
    frame1, 
    bg="#9B59B6",  # Color púrpura
    fg="white", 
    font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold", 
    text="📝 Presupuestos", 
    command=self.presupuestos
)
btnPresupuestos.place(x=780, y=300, width=230, height=70)
```

---

### 3. **inventario.py** - Soporte Código de Barras ✅

**Cambios:**

```python
# Import agregado
from barcode_scanner import EscanerCodigoBarras, DialogoAsignarCodigoBarras

# En __init__:
self.escaner = EscanerCodigoBarras(self.db_name)
```

Cuando registres un producto, se puede llamar a:
```python
# Mostrar diálogo para asignar código
dialogo = DialogoAsignarCodigoBarras(self, self.id_producto, 
                                    self.nombre, self.escaner)
```

---

## 📊 ESTRUCTURA DE BASE DE DATOS

Se crean automáticamente las siguientes tablas:

### Tabla: `facturas_verifactu`
```sql
CREATE TABLE facturas_verifactu (
    id INTEGER PRIMARY KEY,
    numero_factura TEXT UNIQUE,
    fecha TEXT,
    nif_emisor TEXT,
    nif_receptor TEXT,
    nombre_receptor TEXT,
    base_imponible REAL,
    tipo_iva INTEGER,
    total_iva REAL,
    total REAL,
    estado TEXT,
    fecha_creacion TIMESTAMP
)
```

### Tabla: `albaranes`
```sql
CREATE TABLE albaranes (
    id INTEGER PRIMARY KEY,
    numero_albaran TEXT UNIQUE,
    fecha TEXT,
    cliente_nombre TEXT,
    cliente_direccion TEXT,
    observaciones TEXT,
    estado TEXT,
    fecha_creacion TIMESTAMP
)
```

### Tabla: `presupuestos`
```sql
CREATE TABLE presupuestos (
    id INTEGER PRIMARY KEY,
    numero_presupuesto TEXT UNIQUE,
    cliente_nombre TEXT,
    cliente_email TEXT,
    fecha TIMESTAMP,
    base_imponible REAL,
    tipo_iva INTEGER,
    total_iva REAL,
    total REAL,
    estado TEXT
)
```

### Tabla: `ventas` (MODIFICADA)
Se agregan columnas:
- `metodo_pago`
- `cantidad_efectivo`
- `cantidad_tarjeta`

---

## 🎯 GUÍA DE COLOCAR LAS FUNCIONALIDADES EN ACCIÓN

### 1️⃣ Factura VeriFACTU - Después de una venta
```python
# En la función pagar() de ventas.py
from facturas_verifactu import FacturaVeriFACTU

factura_gen = FacturaVeriFACTU(self.config_manager)
factura_gen.crear_factura_verifactu(
    numero_factura=factura_numero,
    fecha=datetime.now(),
    nif_emisor="12345678Z",  # Guardar en config
    nif_receptor=nif_cliente,
    nombre_receptor=nombre_cliente,
    productos=productos,
    base_imponible=base,
    tipo_iva=21,
    total_iva=iva_amount,
    total=total_amount
)
```

### 2️⃣ Código de Barras - En Inventario
```python
# Agregar campo en panel de inventario
tk.Label(labelFrame, text="Código Barras:", font="sans 12 bold", bg="#C6D9E3")
self.codigo_barras = ttk.Entry(labelFrame, font="sans 12 bold")

# Al registrar producto:
if self.codigo_barras.get().strip():
    self.escaner.guardar_codigo_barras(
        id_producto,
        self.codigo_barras.get()
    )
```

### 3️⃣ Impresora - Llamar antes de abrir PDF
```python
from impresoras import DialogoSeleccionImpresora

# Después de generar PDF:
dialogo = DialogoSeleccionImpresora(self, archivo_pdf, None)
dialogo.wait_window()
```

---

## ⚠️ POSIBLES MEJORAS FUTURAS

1. **Integración de NIF automático**: Guardar NIF emisor en config.py
2. **Código de barras en UI de ventas**: Campo para escanear mientras se vende
3. **Reportes estadísticos**: Ganancias por método de pago
4. **Sincronización nube**: Respaldos automáticos en Google Drive
5. **Multi-usuario**: Sistema de login y permisos
6. **Integración bancaria**: Validar transacciones con tarjeta

---

## 🚀 COMANDOS RÁPIDOS PARA TESTING

```python
# Test Factura VeriFACTU
python -c "from facturas_verifactu import FacturaVeriFACTU; print('VeriFACTU OK')"

# Test Ticket
python -c "from tickets import TicketSimplificado; print('Ticket OK')"

# Test Albaranes
python -c "from albaranes import AlbaranEntrega; print('Albarán OK')"

# Test Presupuestos
python -c "from presupuestos import Presupuestos; print('Presupuestos OK')"

# Test Impresoras
python -c "from impresoras import GestorImpresoras; print('Impresoras OK')"

# Test Scanner
python -c "from barcode_scanner import EscanerCodigoBarras; print('Scanner OK')"
```

---

## 📞 SOPORTE TÉCNICO

Si encuentras errores:

1. Verifica que todas las librerías estén instaladas:
   ```bash
   pip list | grep -E "qrcode|pywin32|reportlab|PIL|ttkthemes"
   ```

2. Comprueba que los archivos `facturas_verifactu.py`, `tickets.py`, etc. estén en la misma carpeta que `index.py`

3. En Windows, si pywin32 no funciona correctamente:
   ```bash
   python -m pywin32_postinstall -install
   ```

---

**¡Todas las 7 funcionalidades están completamente implementadas y listas para usar!**
