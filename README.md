# Reyger

[![Build](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml/badge.svg)](https://github.com/Benhursamuelreyes/Reyger/actions/workflows/build.yml)
[![Versión](https://img.shields.io/github/v/release/Benhursamuelreyes/Reyger?label=versión)](https://github.com/Benhursamuelreyes/Reyger/releases/latest)
[![Licencia](https://img.shields.io/badge/licencia-MIT-green.svg)](./LICENSE)

**Reyger** es un sistema de ventas y facturación **multiplataforma (POS)**
desarrollado en Python con Tkinter. Genera facturas en PDF, tickets de
80 mm, presupuestos y albaranes; incluye códigos QR de verificación,
gestión de inventario y métodos de pago. Disponible para **Windows,
macOS y Linux**.

> En desarrollo activo: si encuentras un error, consulta
> [Problemas frecuentes](#problemas-frecuentes) y
> [abre una incidencia](https://github.com/Benhursamuelreyes/Reyger/issues)
> adjuntando el registro de errores.

---

## Características principales

- **Facturación VeriFACTU** — Facturas con cumplimiento normativo español,
  códigos QR de verificación y auditoría en base de datos.
- **PDF profesional** — Facturas, presupuestos y albaranes listos para
  imprimir o enviar.
- **Tickets de 80 y 58 mm** — Para impresoras térmicas, con logotipo.
- **Métodos de pago** — Efectivo (con cálculo de vuelto), tarjeta y mixto.
- **Inventario** — Categorías, proveedores, códigos de barras, margen de
  beneficio y **aviso de stock bajo**.
- **Informe de ventas por periodo** — Totales por día, producto, tipo de
  documento y método de pago, exportable a Excel.
- **Escáner de código de barras** — Captura en vivo en Ventas y alta
  rápida de productos nuevos.
- **Albaranes y presupuestos** — Con estados, firma e IVA configurable.
- **Copias de seguridad** — Copia automática diaria al cerrar, y
  exportación/importación en SQLite, Excel o CSV desde Ajustes.
- **Tema claro y oscuro** — Interfaz pensada para el punto de venta.
- **Sin servidor** — Los datos se guardan en tu equipo (SQLite).

---

## Descarga e instalación

Descarga el instalador de tu sistema. Los enlaces apuntan siempre a la
**última versión**:

| Sistema | Descarga | Requisitos |
|---------|----------|------------|
| **Windows** | [Reyger-Windows.msi](https://github.com/Benhursamuelreyes/Reyger/releases/latest/download/Reyger-Windows.msi) | Windows 10 u 11 (64 bits) |
| **macOS** | [Reyger-macOS.dmg](https://github.com/Benhursamuelreyes/Reyger/releases/latest/download/Reyger-macOS.dmg) | macOS 11 o superior, Intel y Apple Silicon |
| **Linux** | [Reyger-Linux-x86_64.AppImage](https://github.com/Benhursamuelreyes/Reyger/releases/latest/download/Reyger-Linux-x86_64.AppImage) | x86_64 con glibc 2.27 o superior (Ubuntu 18.04, Debian 10, RHEL/Rocky 8 o posteriores) y escritorio gráfico |

No hace falta instalar Python: los instaladores lo llevan incorporado.
Las versiones anteriores y las notas de cada una están en
[Releases](https://github.com/Benhursamuelreyes/Reyger/releases).

### Windows

1. Ejecuta `Reyger-Windows.msi` y sigue el asistente.
2. Abre **Reyger** desde el menú Inicio.

Si aparece *«Windows protegió su PC»* (SmartScreen), pulsa
**Más información → Ejecutar de todas formas**. Ocurre porque el
instalador no está firmado con un certificado comercial.

### macOS

1. Abre `Reyger-macOS.dmg` y arrastra **Reyger** a *Aplicaciones*.
2. Abre Reyger desde *Aplicaciones*.

La aplicación no está notarizada por Apple, así que la primera vez macOS
la bloquea:

- **macOS 15 (Sequoia) o posterior**: tras el aviso, abre
  **Ajustes del Sistema → Privacidad y seguridad**, baja hasta el mensaje
  sobre Reyger y pulsa **Abrir igualmente**.
- **macOS 11 a 14**: clic derecho (o Control + clic) sobre Reyger →
  **Abrir** → **Abrir**.

Solo hace falta la primera vez.

### Linux

```bash
chmod +x Reyger-Linux-x86_64.AppImage
./Reyger-Linux-x86_64.AppImage
```

No necesita instalación ni `libfuse2`. Para tenerlo en el menú de
aplicaciones puedes usar [Gear Lever](https://flathub.org/apps/it.mijorus.gearlever)
o [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher).

### Verificar la descarga (opcional)

Cada release incluye `SHA256SUMS.txt` con la huella de todos los
instaladores. Descárgalo junto al instalador y compruébalo:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing      # Linux
shasum -a 256 -c SHA256SUMS.txt --ignore-missing  # macOS
```

```powershell
Get-FileHash .\Reyger-Windows.msi -Algorithm SHA256   # Windows: compara con SHA256SUMS.txt
```

---

## Actualizar a una versión nueva

Instala la versión nueva **encima** de la anterior: en Windows ejecuta el
nuevo `.msi`, en macOS sustituye la app en *Aplicaciones* y en Linux
reemplaza el fichero `.AppImage`. **Tus datos se conservan**, porque no se
guardan junto al programa sino en tu [carpeta de datos](#tus-datos).

Si la versión nueva cambia la estructura de la base de datos, Reyger la
actualiza sola al abrirse y antes guarda una copia de la base tal como
estaba (p. ej. `database_antes_v14_<fecha>.bak` al pasar a la 1.2).

> No se puede volver a una versión anterior con una base ya actualizada.
> Si lo necesitas, restaura esa copia previa desde
> **Ajustes → Datos y copias de seguridad → Importar base de datos** con la versión antigua instalada.

---

## Tus datos

La base de datos, la configuración, las copias automáticas y el registro de
errores se guardan en:

| Sistema | Carpeta |
|---------|---------|
| Windows | `%LOCALAPPDATA%\Reyger\Reyger` |
| macOS | `~/Library/Application Support/Reyger` |
| Linux | `~/.local/share/Reyger` |

| Fichero | Contenido |
|---------|-----------|
| `database.db` | Ventas, inventario, clientes y documentos |
| `config.json` | Ajustes de la aplicación |
| `respaldos/automatico_AAAAMMDD.db` | Copia automática al cerrar (una por día; se conservan 7) |
| `database_respaldo_*.bak` | Copia previa a cada importación de datos |
| `reyger.log`, `crash.log` | Registro de errores y de cierres inesperados |

**Copias de seguridad.** Además de la copia automática, puedes exportar
los datos desde **Ajustes → Datos y copias de seguridad → Exportar base
de datos** (SQLite, Excel o CSV) y recuperarlos con **Importar base de datos**
en esa misma sección. No copies
`database.db` a mano con la aplicación abierta: los últimos cambios pueden
estar aún en `database.db-wal` y la copia quedaría incompleta.

**Desinstalar.** Desinstalar Reyger (Windows: *Configuración → Aplicaciones*;
macOS: mover la app a la Papelera; Linux: borrar el `.AppImage`) **no
borra tus datos**. Para empezar de cero, borra también la carpeta de datos.

---

## Problemas frecuentes

| Problema | Solución |
|----------|----------|
| Windows: «Windows protegió su PC» | **Más información → Ejecutar de todas formas** (ver [Windows](#windows)). |
| macOS: «No se puede abrir porque Apple no puede comprobar…» | Ver [macOS](#macos): *Privacidad y seguridad → Abrir igualmente*. |
| Linux: el AppImage no arranca por FUSE | Ejecútalo con `./Reyger-Linux-x86_64.AppImage --appimage-extract-and-run`. |
| Linux: error de `GLIBC_2.27` | La distribución es demasiado antigua; ver requisitos en la [tabla de descarga](#descarga-e-instalación). |
| Al cerrar: «La base de datos tiene errores de integridad» | La base está dañada. Se ha conservado la copia automática anterior: impórtala desde **Ajustes → Datos y copias de seguridad → Importar base de datos** y contacta con soporte. |
| macOS y Linux: no aparece la configuración de impresoras | La detección de impresoras solo existe en Windows; en macOS y Linux se usa la impresora del sistema. |

**Para informar de un error**, adjunta `reyger.log` y `crash.log` de tu
[carpeta de datos](#tus-datos) a la
[incidencia](https://github.com/Benhursamuelreyes/Reyger/issues).

---

## Desarrollo

Requisitos, entorno de desarrollo, tests, compilación de instaladores,
proceso de release y estructura del código:
**[docs/DESARROLLO.md](docs/DESARROLLO.md)**.

El historial de cambios está en **[CHANGELOG](CHANGELOG)**.

---

## Licencia

Distribuido bajo la [licencia MIT](./LICENSE).

© 2026 Reyger. Se permite el uso, copia, modificación y distribución
tanto comercial como privada.
