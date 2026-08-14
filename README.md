# Reyger

[![Build](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml/badge.svg)](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml)
[![Versión](https://img.shields.io/badge/versión-v2.0.0--beta.8-blue.svg)](https://github.com/Benhursamuelreyes/Reyger/releases)
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
| **Windows** | `Reyger-2.0.0b6.msi` |
| **macOS** | `Reyger-2.0.0b6.dmg` |
| **Linux** | `Reyger-2.0.0b6-x86_64.AppImage` |

### Guía de instalación por plataforma

**Windows**
1. Descarga el archivo `Reyger-2.0.0b6.msi`.
2. Ejecútalo y sigue el asistente (Next → Install → Finish).
3. Abre **Reyger** desde el menú de inicio o el acceso directo del escritorio.
   - Si SmartScreen muestra una advertencia, pulsa *"Más información"* →
     *"Ejecutar de todas formas"* (los binarios de beta aún no están firmados).

**macOS**
1. Descarga el archivo `Reyger-2.0.0b6.dmg`.
2. Ábrelo y arrastra el icono **Reyger** a la carpeta *Aplicaciones*.
3. Al abrirlo por primera vez, si Gatekeeper lo bloquea: clic derecho sobre
   el icono → *Abrir* → *Abrir*.

**Linux**
1. Descarga el archivo `Reyger-2.0.0b6-x86_64.AppImage`.
2. Hazlo ejecutable y lánzalo:
   ```bash
   chmod +x Reyger-2.0.0b6-x86_64.AppImage
   ./Reyger-2.0.0b6-x86_64.AppImage
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
git tag v2.0.0-beta.6
git push origin main --tags
```

Esto compila los tres instaladores (`.msi`, `.dmg`, `.AppImage`), verifica
que tkinter funciona en el bundle de Windows antes de empaquetar y crea una
**publicación en GitHub Releases** con los artefactos adjuntos y las notas
de versión generadas automáticamente.

---

## Registro de cambios

### v2.0.0-beta.8 — 2026-08-14

**Arreglado**

- Crash del módulo **Albaranes** con reportlab 5.0.0: `albaranes.py` importaba
  `Line` desde `reportlab.platypus`, que dejó de existir en reportlab 5
  (import muerto, sin usos); eliminado.
- Actualizado `test_nuevas_funcionalidades.py` a la estructura de paquete
  (imports `reyger.*`, rutas absolutas, `Presupuestos` con `parent` tkinter):
  ahora refleja el estado real del proyecto y pasa 6/6.

### v2.0.0-beta.7 — 2026-08-14

**Arreglado**

- **Causa raíz del crash del `.msi` de Windows** (`ModuleNotFoundError:
  No module named 'tkinter'`). Aunque beta.6 ya inyectaba tkinter completo en
  el bundle (`Lib/tkinter`, `tcl/`, `_tkinter.pyd`), el stub de arranque que
  Briefcase descarga con su **branch `v0.4.4` del template** es la revisión
  b10/b11, que construye `sys.path` a mano **sin** `<home>\Lib` ni
  `<home>\DLLs`. El stub b12 (que sí los añade) solo está en la rama `main`
  del template, sin release de Briefcase todavía.
- Fix aplicado en dos capas:
  1. **`sitecustomize.py`** (inyectado por `scripts/bundle_tkinter_windows.py`)
     inserta `<home>\Lib` y `<home>\DLLs` al inicio de `sys.path` cuando
     existen. Como el stub importa `site` antes de arrancar la app, tkinter es
     importable con **cualquier** revisión de stub (validado en wine con el
     stub real del MSI: `Tk() CREATED OK`).
  2. **`stub_binary_revision = "12"`** en `[tool.briefcase.app.reyger.windows]`
     (`pyproject.toml`) fuerza a Briefcase a usar el stub b12, que ya añade
     Lib/DLLs por sí mismo.
- El CI no detectaba el fallo porque `bundle_tkinter_windows.py` verificaba
  con `python.exe` temporal (que respeta el `._pth`), no con el stub real.

### v2.0.0-beta.6 — 2026-08-14

**Arreglado (parcial)**

- Inyección de tkinter/Tcl/Tk en el runtime embebido del `.msi` de Windows
  (tkinter llegaba al bundle, pero el stub b10/b11 no lo veía; ver
  v2.0.0-beta.7).
- Nuevo script `scripts/bundle_tkinter_windows.py` que inyecta tkinter,
  Tcl/Tk y las DLLs en el runtime embebido y **verifica con una ventana
  `Tk()` real** antes de publicar; si la verificación falla, la publicación
  se aborta.
- Detección del runtime embebido basada en `python*._pth`/`python*.dll`:
  el paquete *embeddable* de python.org no incluye directorio `Lib/`.
- Esta versión se publica como **Release** completo (no *Pre-release*).

**Nota**: a pesar del CI en verde, el `.msi` de esta versión seguía
crasheando al arrancar en Windows (el stub b10/b11 no añade `Lib`/`DLLs`
a `sys.path`); la causa raíz está corregida en **v2.0.0-beta.7**.

### v2.0.0-beta.5 — 2026-08-13

**Arreglado**

- Inyección de tkinter en el bundle de Windows vía PowerShell.
- Desbloqueo del archivo `python._pth` del runtime embebido.
- Publicaciones de tag idempotentes: se limpia el release anterior del
  mismo tag antes de recrearlo.

**Nota**: el `.msi` de esta versión seguía crasheando en Windows (tkinter
no se inyectaba en la ruta correcta); corregido en **v2.0.0-beta.6**.

### v2.0.0-beta.4 — 2026-08-11

**Correcciones**

- Insertar el código QR de VeriFACTU en el PDF de la factura.
- Corregir el off-by-one del número de factura en el PDF.
- Preservar los céntimos con formato `:.2f` en las ventas.
- Pre-rellenar la edición de inventario desde la BD sin formato euro.
- Normalizar la coma decimal al registrar productos.
- Numerar los presupuestos por id autoincremental.
- Cerrar correctamente la ventana de ajustes (sin `withdraw` sobre `Frame`).
- Cerrar conexiones SQLite con gestor de contexto en el escáner.
- Importar `cm` faltante en `tickets.py`.
- Agrupar la escritura de configuración en `guardar_cambios`.
- Documentar el estado BETA y automatizar la publicación de pre-releases.

### v2.0.0-beta.3 — 2026-08-10

**Novedades**

- Rebranding: **VentaPRO** → **Reyger**, con nueva identidad.

**Empaquetado y CI**

- Incluir tkinter en el build del instalador `.msi` de Windows.
- Verificación del bundle en CI para Linux y macOS (incluidas las
  dependencias de sistema de tkinter).
- Flujo de publicación de GitHub Releases separado en `release.yml`.

### v2.0.0-beta.1 — 2026-07-31

**Novedades**

- Primera beta pública de **Reyger**: facturación VeriFACTU con códigos QR,
  PDF con ReportLab, tickets de 80 mm, inventario, albaranes, presupuestos
  e instaladores `.msi`, `.dmg` y `.AppImage`.

---

## Bugs conocidos

- **Binarios sin firmar**: Windows SmartScreen y macOS Gatekeeper muestran
  advertencias al instalar o abrir la aplicación en las versiones beta.
- **Estado beta**: el software está en desarrollo activo y pueden existir
  errores no detectados en flujos poco habituales.
- **macOS**: el módulo de detección y configuración de impresoras solo está
  disponible en Windows; en macOS y Linux se usa la impresora del sistema.

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
