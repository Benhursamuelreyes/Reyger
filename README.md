# 🛒 SALES SYSTEM - Caja Registradora v2.0

**Sistema profesional de gestión de ventas e inventario** desarrollado en Python con Tkinter.  
Ahora con **7 nuevas funcionalidades empresariales** listas para producción.

---

## 📋 Contenido

- [✨ Novedades (7 funcionalidades)](#-novedades)
- [Inicio rápido](#-inicio-rápido)
- [Estructura del proyecto](#-estructura)
- [Documentación completa](#-documentación)
- [Validación](#-validación)
- [Solución de problemas](#-troubleshooting)

---

## ✨ Novedades

### 1️⃣ **Factura VeriFACTU** 🧾
Cumplimiento normativa Hacienda España
- Código QR de verificación
- NIF emisor/receptor
- Auditoría en BD
- PDF profesional

### 2️⃣ **Tickets Simplificados** 🎫
Para impresoras térmicas 80mm
- Rollo formato compacto
- Método pago visible
- Optimizado POS

### 3️⃣ **Albaranes** 📦
Documentos de entrega
- Signature fields
- Estados: Abierto/Entregado/Rechazado
- Tracking logístico

### 4️⃣ **Métodos de Pago** 💳
Integrado en Ventas
- Efectivo → Cálculo vuelto
- Tarjeta → Últimos 4 dígitos
- Mixto → Parte efectivo + tarjeta
- Registro en BD

### 5️⃣ **Presupuestos** 📝
Módulo interactivo 1100×650px
- Crear desde inventario
- IVA: 4%, 10%, 21%
- PDF profesional
- **Nuevo botón púrpura en navegación**

### 6️⃣ **Gestión de Impresoras** 🖨️
Soporte Windows completo
- Enumera impresoras
- Diálogo selección
- Opciones: color, doble cara
- Métodos fallback

### 7️⃣ **Escáner de Barras** 📷
Lector USB (HID keyboard)
- Búsqueda por código
- Asignar códigos a productos
- Integrado en Inventario

---

## 🚀 Inicio Rápido

### 1. Instalar
```bash
pip install qrcode[pil] pywin32 reportlab pillow ttkthemes
```

### 2. (Opcional pero recomendado para impresoras)
```bash
python -m pywin32_postinstall -install
```

### 3. Ejecutar
```bash
python index.py
```

**⏱️ < 5 minutos de instalación**

---

## 📁 Estructura

```
sales_system/
├── # Núcleo
├── index.py                      # 🟢 Inicio
├── manager.py                    # Ventana principal
├── container.py                  # [MOD] + botón Presupuestos
├── config.py                     # Configuración
│
├── # Módulos (3 modificados, 6 nuevos)
├── ventas.py                     # [MOD] + métodos pago
├── inventario.py                 # [MOD] + barcode
├── ajustes.py                    # Ajustes
├── facturas_verifactu.py         # ✨ VeriFACTU
├── tickets.py                    # ✨ Tickets
├── albaranes.py                  # ✨ Albaranes
├── presupuestos.py               # ✨ Presupuestos
├── impresoras.py                 # ✨ Impresoras
├── barcode_scanner.py            # ✨ Escáner
│
├── # Documentación
├── README.md                     # Este archivo
├── GUIA_CERO_IMPLEMENTACION.md
├── RESUMEN_VISUAL.md
├── INSTALAR_DEPENDENCIAS.md
├── test_nuevas_funcionalidades.py
│
├── database.db                   # SQLite
└── [Directorios se crean automáticamente]
```

---

## 📖 Documentación

| Archivo | Para |
|---------|------|
| [GUIA_CERO_IMPLEMENTACION.md](./docs/GUIA_CERO_IMPLEMENTACION.md) | Referencia técnica |
| [RESUMEN_VISUAL.md](./docs/RESUMEN_VISUAL.md) | Ejemplos código |
| [INSTALAR_DEPENDENCIAS.md](./docs/INSTALAR_DEPENDENCIAS.md) | Troubleshooting |

---

## ✅ Validación

```bash
python test_nuevas_funcionalidades.py
```

Verifica:
- ✓ Librerías instaladas
- ✓ Estructura correcta
- ✓ BD accesible
- ✓ Módulos importables
- ✓ Funcionalidad OK

---

## 💡 Uso

### Vender con método pago
1. Ventas → Agregar productos
2. Pagar
3. Selecciona: Efectivo / Tarjeta / Mixto
4. Sistema calcula vuelto

### Presupuesto
1. Botón púrpura "📝 Presupuestos"
2. Cliente + Productos
3. IVA (4%/10%/21%)
4. Genera PDF

### Factura VeriFACTU
```python
from facturas_verifactu import FacturaVeriFACTU

factura = FacturaVeriFACTU()
pdf = factura.crear_factura_verifactu(
    nif_cliente="12345678A",
    cliente="Juan García",
    productos=[{"nombre": "Producto", "cantidad": 1, "precio": 100}],
    total=121
)
```

### Barcode
```python
from barcode_scanner import EscanerCodigoBarras

scanner = EscanerCodigoBarras()
producto = scanner.buscar_producto_por_codigo("1234567890")
```

---

## 🐛 Troubleshooting

**App no inicia**
```bash
python test_nuevas_funcionalidades.py
```

**No aparece botón Presupuestos**  
Verifica que `presupuestos.py` está en raíz

**Impresoras no se detectan**  
```bash
python -m pywin32_postinstall -install
```

**Código de barras no funciona**  
Instala `barcode_scanner.py` en raíz

---

## 📊 Base de Datos

Se crean automáticamente:
- `facturas_verifactu` - Auditoría facturas
- `albaranes` - Entregas
- `presupuestos` - Presupuestos
- Columnas nuevas en `ventas` - Método pago

---

## 🔧 Configuración

Edita `config.json` o usa panel ⚙️ Ajustes:

```json
{
    "tema": "claro",
    "tamaño_fuente": 14,
    "nombre_empresa": "Mi Empresa",
    "nif_emisor": "12345678Z"
}
```

---

## 📦 Dependencias

| Librería | Para |
|----------|------|
| `tkinter` | GUI |
| `sqlite3` | Base datos |
| `reportlab` | PDF |
| `qrcode` | QR codes |
| `pillow` | Imágenes |
| `pywin32` | Impresoras |
| `ttkthemes` | Temas |

---

## 🎯 Características Implementadas

```
✅ FacturaVeriFACTU completa
✅ Tickets 80mm
✅ Albaranes con workflow
✅ Métodos pago integrados
✅ Módulo Presupuestos
✅ Gestión impresoras
✅ Escáner código barras
✅ BD relacional actualizada
✅ Documentación completa
✅ Testing automático
```

---

## 🔮 Mejoras Futuras

- [ ] Multi-usuario
- [ ] Reportes estadísticos
- [ ] API de bancos
- [ ] Sincronización nube
- [ ] App móvil
- [ ] Devoluciones
- [ ] Descuentos/Promociones

---

## 📄 Version

**v2.0** - 7 nuevas funcionalidades empresariales
**v1.0** - Sistema original

---

**¡Tu sistema está listo! 🚀**

Instala dependencias → Ejecuta `test_nuevas_funcionalidades.py` → Abre `python index.py`
