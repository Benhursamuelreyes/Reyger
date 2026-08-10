# Reyger

[![Build](https://github.com/Benhursamuelreyes/sales_system/actions/workflows/build.yml/badge.svg)](https://github.com/Benhursamuelreyes/sales_system/actions/workflows/build.yml)
[![Versión](https://img.shields.io/badge/versión-v2.0.0--beta.2-blue.svg)](https://github.com/Benhursamuelreyes/Reyger/releases)
[![Licencia](https://img.shields.io/badge/licencia-MIT-green.svg)](./LICENSE)

**Sistema de ventas y facturación multiplataforma** desarrollado en Python.
Facturas en PDF, códigos QR de verificación, gestión de inventario y un
catálogo completo de documentos comerciales para Windows, macOS y Linux.

---

## Características principales

- **Facturación VeriFACTU** — Facturas con cumplimiento normativo español,
  códigos QR de verificación y auditoría en base de datos.
- **PDF profesional con ReportLab** — Facturas, presupuestos y albaranes
  generados como documentos PDF listos para imprimir o enviar.
- **Interfaz moderna con ttkthemes** — Temas configurables (claro/oscuro) y
  ventanas optimizadas para uso en punto de venta (POS).
- **Base de datos SQLite** — Sin servidor, portable y de fácil respaldo.
  Se crea automáticamente en la primera ejecución.
- **Tickets de 80 mm** — Formato compacto para impresoras térmicas.
- **Métodos de pago** — Efectivo (con cálculo de vuelto), tarjeta y mixto.
- **Albaranes** — Documentos de entrega con estados y firma.
- **Presupuestos** — Módulo con IVA configurable (4%, 10%, 21%).
- **Gestión de impresoras** — Detección y configuración (Windows).
- **Escáner de código de barras** — Búsqueda rápida de productos por código.
- **Empaquetado multiplataforma con Briefcase** — Instaladores `.msi`,
  `.dmg` y `.AppImage` generados automáticamente en CI.

---

## Descarga e instalación

Los instaladores oficiales de Reyger se publican como **Release assets**
y pueden descargarse de forma permanente desde:

👉 **[Descargar Reyger — Releases](https://github.com/Benhursamuelreyes/sales_system/releases)**

| Plataforma | Archivo |
|------------|---------|
| **Windows** | `Reyger-2.0.0b2.msi` |
| **macOS** | `Reyger-2.0.0b2.dmg` |
| **Linux** | `Reyger-2.0.0b2-x86_64.AppImage` |

Una vez instalado, abre la aplicación y empieza a vender.

---

## Desarrollo local

### Requisitos

- Python 3.9 o superior
- [Briefcase](https://briefcase.readthedocs.io/)

### Clonar el repositorio

```bash
git clone https://github.com/Benhursamuelreyes/sales_system.git
cd sales_system
```

### Crear el entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

python -m pip install --upgrade pip
python -m pip install briefcase reportlab "qrcode[pil]" Pillow ttkthemes platformdirs
```

### Ejecutar en modo desarrollo

```bash
briefcase dev
```

También puedes arrancar la app directamente con:

```bash
python run.py
```

### Compilar instaladores localmente

```bash
# Windows (.msi)
briefcase create && briefcase build && briefcase package

# macOS (.dmg)
briefcase create && briefcase build && briefcase package --adhoc-sign

# Linux (.AppImage)
briefcase create linux appimage && briefcase build linux appimage && briefcase package linux appimage
```

> En CI, los tres instaladores se compilan y publican automáticamente al
> etiquetar el repositorio con una versión (por ejemplo, `git tag v2.0.0`).

---

## Estructura del proyecto

```
sales_system/
├── .github/workflows/build.yml   # CI: build + release automático
├── src/reyger/                   # Código fuente de la aplicación
│   ├── app.py                    # Punto de entrada (Briefcase)
│   ├── manager.py                # Ventana principal
│   ├── ventas.py                 # Módulo de ventas
│   ├── inventario.py             # Módulo de inventario
│   ├── facturas_verifactu.py     # Facturación VeriFACTU
│   ├── tickets.py                # Tickets 80 mm
│   ├── albaranes.py              # Albaranes
│   ├── presupuestos.py           # Presupuestos
│   └── assets/                   # Iconos e imágenes
├── pyproject.toml                # Configuración del proyecto y Briefcase
├── requirements.txt              # Dependencias
├── LICENSE                       # Licencia MIT
└── README.md
```

---

## Licencia

Distribuido bajo la [licencia MIT](./LICENSE).

© 2026 Reyger. Se permite el uso, copia, modificación y distribución
tanto comercial como privada.
