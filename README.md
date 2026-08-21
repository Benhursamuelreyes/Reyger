# Reyger

[![Build](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml/badge.svg)](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml)
[![Versión](https://img.shields.io/badge/versión-v2.0.0--beta.11-blue.svg)](https://github.com/Benhursamuelreyes/Reyger/releases)
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
| **Windows** | `Reyger-2.0.0b11.msi` |
| **macOS** | `Reyger-2.0.0b11.dmg` |
| **Linux** | `Reyger-2.0.0b11-x86_64.AppImage` |

### Guía de instalación por plataforma

**Windows**
1. Descarga el archivo `Reyger-2.0.0b11.msi`.
2. Ejecútalo y sigue el asistente (Next → Install → Finish).
3. Abre **Reyger** desde el menú de inicio o el acceso directo del escritorio.
   - Si SmartScreen muestra una advertencia, pulsa *"Más información"* →
     *"Ejecutar de todas formas"* (los binarios de beta aún no están firmados).

**macOS**
1. Descarga el archivo `Reyger-2.0.0b11.dmg`.
2. Ábrelo y arrastra el icono **Reyger** a la carpeta *Aplicaciones*.
3. Al abrirlo por primera vez, si Gatekeeper lo bloquea: clic derecho sobre
   el icono → *Abrir* → *Abrir*.

**Linux**
1. Descarga el archivo `Reyger-2.0.0b11-x86_64.AppImage`.
2. Hazlo ejecutable y lánzalo:
   ```bash
   chmod +x Reyger-2.0.0b11-x86_64.AppImage
   ./Reyger-2.0.0b11-x86_64.AppImage
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

### v2.0.0-beta.11 — 2026-08-21

**Corregido — AppImage de Linux**

- El AppImage no empaquetaba los **scripts de Tcl/Tk** (`init.tcl`/`tk.tcl`)
  que el Python de Briefcase enlaza (Tcl 8.6.8), por lo que la aplicación
  fallaba al arrancar en equipos sin `python3-tk` del sistema
  (*"Can't find a usable init.tcl"*). Bug heredado de versiones anteriores.
- El CI ahora copia los scripts oficiales 8.6.8 al bundle y verifica que se
  puede crear una ventana `Tk()` real dentro del AppImage antes de publicar
  (la verificación anterior solo comprobaba `import tkinter`, que no
  inicializa Tcl).

### v2.0.0-beta.10 — 2026-08-21

**Actualización masiva en 4 fases** (base de datos, interfaz, lógica de
negocio y hardware).

**Añadido — Base de datos relacional y migraciones versionadas**

- Nueva capa centralizada de acceso a datos (`db.py`): conexión única con
  claves foráneas activadas y helpers `query`/`query_one`/`execute`/`transaccion`.
- Sistema de **migraciones versionadas** (`migrations.py`) basado en
  `PRAGMA user_version`: las instalaciones existentes se actualizan solas al
  arrancar sin perder datos.
- Nuevas tablas: `clientes`, `proveedores`, `usuarios`, `sesiones_caja`,
  `facturas_borradores(+productos)`; esquema completo garantizado para
  presupuestos, albaranes, facturas VeriFACTU, ventas e inventario.
- Columnas nuevas: `ventas` (+cliente, usuario, sesión, IVA), `inventario`
  (+proveedor_id FK, tipo_iva).
- Autenticación PBKDF2-SHA256 (`auth.py`) y plantilla de base de datos
  regenerada (`user_version=2`).

**Añadido — Interfaz moderna y responsiva**

- Ventana principal y módulos a **1280x800 redimensionables** con tamaño
  mínimo por ventana; layouts convertidos de `place()` fijo a `pack`/`grid`
  elásticos (menú, Ventas, Inventario).
- Nuevo módulo **Clientes**: CRUD completo con datos personales/fiscales y
  validación oficial de **NIF/NIE/CIF** (dígito de control, RD 1065/2007),
  búsqueda y listado.
- Inventario: proveedor como desplegable alimentado por la tabla
  `proveedores` + alta rápida modal; campo **IVA** por producto (21/10/4%)
  en alta, edición y listado.

**Añadido — Lógica de negocio**

- **Login con roles** (admin/cajero): diálogo modal al arrancar con 3
  intentos, sesiones de caja registradas (apertura/cierre) y botón
  *Cerrar sesión* en el menú.
- Restricciones por rol: el cajero no ve **Ajustes** ni puede eliminar
  productos o clientes; cada venta audita `usuario_id` y `sesion_id`.
- **Desglose de IVA** en ventas: columna IVA por línea, Base imponible /
  Cuota / Total calculados en vivo y guardados por línea
  (`tipo_iva`, `cuota_iva`, `base_imponible`); factura PDF con desglose.
- Cliente opcional asociado a cada venta.

**Añadido — Impresión térmica (ESC/POS)**

- Tickets térmicos sin dependencias externas: constructor ESC/POS propio
  (negrita, doble tamaño, corte parcial) con codificación CP858 y papel de
  80 mm o 58 mm.
- Envío multiplataforma solo con stdlib: cola RAW de Windows vía
  ctypes/winspool, `/dev/usb/lp*` o CUPS (`lp -o raw`) en Linux/macOS.
- Impresión automática del ticket al cobrar (si hay impresora configurada)
  y nueva sección **Impresora Térmica** en Ajustes con página de prueba.

### v2.0.0-beta.9 — 2026-08-14

**Arreglado**

- Ventana de **Inventario** en blanco: `inventario.py` llamaba a
  `self.crear_tabla()` que no existía (se perdió en un refactor anterior);
  el `AttributeError` abortaba la construcción antes de dibujar los widgets.

**Actualización de la release (sobrescrita — los cambios se combinan)**

- La primera corrección publicada restauraba `crear_tabla()` en
  `inventario.py` para volver a crear la tabla `inventario` en runtime.
- Después, la release **se sobrescribió** con una solución más robusta y se
  reestructuró la inicialización de la base de datos: `database.db` (con las
  tablas `ventas` e `inventario`) ahora se **empaqueta** con la app y se
  **copia al directorio de datos del usuario en el primer arranque** desde
  `get_db_path()`. Eliminada la creación de tablas en runtime:
  - Eliminada `crear_tabla()` de `inventario.py` (y su llamada).
  - `resources.py` hace el *seed* de `database.db` si no existe aún.

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
