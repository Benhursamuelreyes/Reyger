# Reyger

[![Build](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml/badge.svg)](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml)
[![Versión](https://img.shields.io/badge/versión-v0.1.0--beta.1-blue.svg)](https://github.com/Benhursamuelreyes/Reyger/releases)
[![Licencia](https://img.shields.io/badge/licencia-MIT-green.svg)](./LICENSE)

> **ESTADO: BETA** — En desarrollo activo. Puede haber cambios y errores.

**Reyger** es un sistema de ventas y facturación **multiplataforma (POS)**
desarrollado en Python con Tkinter. Genera facturas en PDF, tickets de
80 mm, presupuestos y albaranes; incluye códigos QR de verificación,
gestión de inventario y métodos de pago. Disponible para **Windows,
macOS y Linux**.

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

## Requisitos del entorno

### Para usar los instaladores (usuarios)

| Plataforma | Requisitos |
|------------|------------|
| **Windows** | Windows 10 u 11 (64 bits) |
| **macOS** | macOS 11 (Big Sur) o superior |
| **Linux** | Distribución con glibc 2.17+ y sistema gráfico X11/Wayland |

No es necesario instalar Python: los instaladores llevan el runtime
incorporado.

### Para desarrollar o compilar (desarrolladores)

| Requisito | Versión |
|-----------|---------|
| Python | 3.9 o superior |
| [Briefcase](https://briefcase.readthedocs.io/) | Última estable |
| [Pillow](https://python-pillow.org/) | Para generar los iconos |
| Sistema | Linux: `python3-tk`, `tk-dev` · macOS: Xcode CLT · Windows: sin extras |

---

## Descarga e instalación

Los instaladores de cada versión se publican como **Release assets** y
pueden descargarse de forma permanente desde:

👉 **[Descargar Reyger — Releases](https://github.com/Benhursamuelreyes/Reyger/releases)**

| Plataforma | Archivo |
|------------|---------|
| **Windows** | `Reyger-0.1.0b1.msi` |
| **macOS** | `Reyger-0.1.0b1.dmg` |
| **Linux** | `Reyger-0.1.0b1-x86_64.AppImage` |

### Guía de instalación por plataforma

**Windows**
1. Descarga el archivo `Reyger-0.1.0b1.msi`.
2. Ejecútalo y sigue el asistente (Next → Install → Finish).
3. Abre **Reyger** desde el menú de inicio o el acceso directo del escritorio.
   - Si SmartScreen muestra una advertencia, pulsa *"Más información"* →
     *"Ejecutar de todas formas"* (los binarios de beta aún no están firmados).

**macOS**
1. Descarga el archivo `Reyger-0.1.0b1.dmg`.
2. Ábrelo y arrastra el icono **Reyger** a la carpeta *Aplicaciones*.
3. Al abrirlo por primera vez, si Gatekeeper lo bloquea: clic derecho sobre
   el icono → *Abrir* → *Abrir*.

**Linux**
1. Descarga el archivo `Reyger-0.1.0b1-x86_64.AppImage`.
2. Hazlo ejecutable y lánzalo:
   ```bash
   chmod +x Reyger-0.1.0b1-x86_64.AppImage
   ./Reyger-0.1.0b1-x86_64.AppImage
   ```

---

## Desarrollo local

### Clonar el repositorio

```bash
git clone https://github.com/Benhursamuelreyes/Reyger.git
cd Reyger
```

### Crear el entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

python -m pip install --upgrade pip
python -m pip install briefcase reportlab "qrcode[pil]" Pillow ttkthemes platformdirs
```

### Ejecutar con Briefcase

El modo desarrollo compila y arranca la aplicación con el entorno local:

```bash
briefcase dev
```

También puedes arrancar la app directamente:

```bash
python run.py
```

### Compilar instaladores con Briefcase

```bash
# Windows (.msi)
briefcase create
python scripts/bundle_tkinter_windows.py
briefcase build
briefcase package

# macOS (.dmg)
briefcase create
briefcase build
briefcase package --adhoc-sign

# Linux (.AppImage)
briefcase create linux appimage
briefcase build linux appimage
briefcase package linux appimage
```

Los instaladores se generan en la carpeta `dist/`.

---

## Releases automáticas (CI)

El flujo `.github/workflows/release.yml` se encarga de todo al etiquetar
una versión:

```bash
git tag v0.1.0-beta.1
git push origin main --tags
```

Esto compila los tres instaladores (`.msi`, `.dmg`, `.AppImage`) y crea una
**publicación en GitHub Releases marcada como *Pre-release*** con los
artefactos adjuntos y las notas de versión generadas automáticamente.

---

## Estructura del proyecto

```
Reyger/
├── .github/workflows/
│   ├── build.yml                # CI: build de cada push/PR a main
│   └── release.yml              # Release: tag v* -> compila + publica
├── src/reyger/                  # Código fuente de la aplicación
│   ├── app.py                   # Punto de entrada (Briefcase)
│   ├── manager.py               # Ventana principal
│   ├── ventas.py                # Módulo de ventas
│   ├── inventario.py            # Módulo de inventario
│   ├── facturas_verifactu.py    # Facturación VeriFACTU
│   ├── tickets.py               # Tickets 80 mm
│   ├── albaranes.py             # Albaranes
│   ├── presupuestos.py          # Presupuestos
│   └── assets/                  # Iconos e imágenes
├── scripts/                     # Utilidades (bundling tkinter, iconos)
├── pyproject.toml               # Configuración del proyecto y Briefcase
├── requirements.txt             # Dependencias
├── LICENSE                      # Licencia MIT
└── README.md
```

---

## Licencia

Distribuido bajo la [licencia MIT](./LICENSE).

© 2026 Reyger. Se permite el uso, copia, modificación y distribución
tanto comercial como privada.
