# Desarrollo de Reyger

Guía para trabajar en el código: entorno, tests, base de datos, compilación
de instaladores y publicación de versiones. La documentación para quien
usa la aplicación está en el [README](../README.md).

## Requisitos

| Requisito | Versión |
|-----------|---------|
| Python | 3.10 o superior (CI prueba 3.10, 3.12 y 3.14; los instaladores usan 3.12) |
| [Briefcase](https://briefcase.readthedocs.io/) | 0.4.4 (la misma que CI), solo para compilar instaladores |
| Linux | `python3-tk`, `tk-dev`; `xvfb` para los tests sin pantalla; `poppler-utils` para los tests de PDF |
| macOS | Xcode Command Line Tools |
| Windows | Sin extras |

## Entorno

```bash
git clone https://github.com/Benhursamuelreyes/Reyger.git
cd Reyger
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest ruff
```

`requirements.txt` replica las dependencias de `pyproject.toml` (las que
llevan los instaladores); `tests/test_dependencias.py` falla si divergen.

Para arrancar la aplicación:

```bash
python run.py
```

## Tests y lint

```bash
python -m pytest -q          # en Linux sin pantalla: xvfb-run -a python -m pytest -q
ruff check src tests
```

- La suite usa una carpeta de datos temporal (`tests/conftest.py`): no toca
  la configuración ni la base de datos de tu instalación.
- Los tests marcados `orden_dependiente` se excluyen por defecto; se
  ejecutan aislados con `python -m pytest -m orden_dependiente <fichero>`.
- Los tests antiguos (`test_fase*`, `test_backup`…) usan `chequear()`; una
  comprobación fallida hace fallar el test también bajo pytest.

## Base de datos

El esquema se versiona con migraciones (`src/reyger/core/migrations.py`),
registradas en `PRAGMA user_version` y aplicadas solas al arrancar.

Para cambiar el esquema:

1. Sube `LATEST_VERSION` y añade una función `@migracion(N)`. Si reescribe
   datos, haz que sea atómica (`BEGIN` explícito: el módulo `sqlite3` no abre
   transacción antes de un `CREATE`/`DROP`) y guarda antes una copia, como la
   migración 14.
2. Regenera la plantilla que se instala con la app:
   `python scripts/build_template_db.py` (`tests/test_fase1_db.py` falla si
   queda atrasada).
3. Añade tests que construyan una base de la versión anterior con
   `run_migrations(conn, hasta=N - 1)` y comprueben la conversión.

Desde el esquema 14 las ventas viven en `documentos` y `lineas_documento`
(importes en céntimos enteros, fechas en hora local ISO); `ventas` es una
vista de solo lectura por compatibilidad. Detalle en
`src/reyger/core/documentos.py`.

## Compilar instaladores

```bash
python -m pip install briefcase==0.4.4

# Windows (.msi)
briefcase create
python scripts/bundle_tkinter_windows.py
briefcase build
briefcase package

# macOS (.dmg, universal Intel + Apple Silicon)
briefcase create
briefcase build
briefcase package --adhoc-sign

# Linux (.AppImage)
briefcase create linux appimage
briefcase build linux appimage
briefcase package linux appimage
```

Los instaladores se generan en `dist/`. CI hace lo mismo en
`.github/workflows/release.yml` (con pasos extra para que Tk viaje dentro
del AppImage y del MSI).

## Publicar una versión

Reyger sigue [versionado semántico](https://semver.org/lang/es/):

- **PATCH** (1.2.1 → 1.2.2): solo correcciones.
- **MINOR** (1.2.x → 1.3.0): funciones nuevas compatibles; una migración de
  base de datos automática también entra aquí.
- **MAJOR** (1.x → 2.0.0): cambios que exigen acción del usuario o rompen
  la compatibilidad (p. ej. copias de seguridad que ya no se pueden importar).

Pasos:

1. Mueve las notas de `## Sin publicar` en `CHANGELOG` a una sección
   `## vX.Y.Z (AAAA-MM-DD)` con una línea de resumen (`FEATURE:`/`FIX:`).
2. Cambia la versión en `pyproject.toml` (las dos líneas `version =`) y en
   `src/reyger/__init__.py`. El README no lleva número de versión: la
   insignia y los enlaces de descarga apuntan a la última release.
3. Commit `release: vX.Y.Z`, etiqueta y push:

   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

El push de la etiqueta lanza `release.yml`: tests (3.10, 3.12, 3.14), los
tres instaladores y la publicación. `scripts/preparar_release.py` publica
cada instalador con su nombre de versión y con un nombre fijo
(`Reyger-Windows.msi`, `Reyger-macOS.dmg`, `Reyger-Linux-x86_64.AppImage`,
los del README), genera `SHA256SUMS.txt` y toma las notas de la sección del
`CHANGELOG`; **falla** si esa sección no existe o si un instalador no lleva
la versión etiquetada. Si algún test falla, no se publica nada.

Una etiqueta ya publicada no se mueve: si una release falla después del
push, se corrige y se publica la siguiente PATCH.

## Estructura del proyecto

```
Reyger/
├── .github/workflows/
│   ├── build.yml                # CI: tests + build de cada push/PR a main
│   └── release.yml              # Tag v* → tests, instaladores y publicación
├── src/reyger/
│   ├── app.py                   # Punto de entrada (Briefcase)
│   ├── config.py                # Configuración y colores del tema
│   ├── container.py             # Ventana principal (menú)
│   ├── resources.py             # Rutas de datos, salida y recursos
│   ├── core/                    # Infraestructura
│   │   ├── db.py                # Conexión SQLite compartida y db.conectar()
│   │   ├── migrations.py        # Migraciones versionadas
│   │   ├── documentos.py        # Esquema 14 y conversión de ventas antiguas
│   │   ├── backup.py            # Exportar/importar y copias automáticas
│   │   ├── correlativos.py      # Numeración que nunca retrocede
│   │   ├── registro.py          # reyger.log
│   │   ├── hilos.py             # Tareas en segundo plano
│   │   ├── datos.py, moneda.py, seguridad.py, updater.py
│   ├── domain/                  # Lógica de negocio (sin Tk)
│   │   ├── ventas.py            # Cobro, borradores y documentos
│   │   ├── inventario.py        # Productos, proveedores, stock bajo
│   │   ├── informes.py          # Informe de ventas por periodo
│   │   ├── fiscal.py            # IVA y céntimos
│   │   ├── pdf_documento.py, facturas_verifactu.py
│   │   └── verifactu_hash.py, verifactu_xml.py
│   ├── hardware/                # Impresoras, tickets ESC/POS, escáner
│   ├── ui/                      # Ventanas Tkinter
│   └── assets/                  # Plantilla database.db, iconos e imágenes
├── scripts/
│   ├── build_template_db.py     # Regenera la plantilla de base de datos
│   ├── preparar_release.py      # Ficheros y notas de cada release (CI)
│   ├── bundle_tkinter_windows.py, generate_icons.py
├── tests/
├── docs/
├── CHANGELOG
├── pyproject.toml
└── requirements.txt
```
