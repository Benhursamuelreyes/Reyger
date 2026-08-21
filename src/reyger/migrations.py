"""Migraciones versionadas del esquema de la base de datos.

Cada migración se ejecuta una única vez dentro de una transacción y
queda registrada en ``PRAGMA user_version``. De este modo las
instalaciones existentes (con una base antigua) se actualizan solas al
arrancar, sin perder datos, y las bases nuevas creadas desde la
plantilla empaquetada ya llegan al día.

Para añadir un cambio de esquema:
    1. Incrementar ``LATEST_VERSION``.
    2. Añadir una función decorada con ``@migracion(N)`` que reciba la
       conexión y aplique los cambios (idempotente siempre que sea
       posible: CREATE TABLE IF NOT EXISTS, _add_column, ...).
"""

from .auth import hash_password

LATEST_VERSION = 1

MIGRACIONES = []


def migracion(version):
    """Registra la función como migración de la *version* indicada."""

    def decorador(fn):
        MIGRACIONES.append((version, fn))
        return fn

    return decorador


def _add_column(conn, tabla, definicion):
    """Añade la columna si la tabla existe y aún no la tiene.

    *definicion* es algo como ``"cliente_id INTEGER REFERENCES clientes(id)"``.
    """
    columnas = {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
    if not columnas:
        return
    nombre = definicion.split()[0]
    if nombre not in columnas:
        conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {definicion}")


@migracion(1)
def _migracion_1(conn):
    """Fase 2: catálogos relacionales, usuarios/sesiones, borradores e IVA."""

    # --- Catálogos nuevos -------------------------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo_documento TEXT NOT NULL DEFAULT 'NIF',
            documento TEXT,
            direccion TEXT,
            codigo_postal TEXT,
            provincia TEXT,
            telefono TEXT,
            email TEXT,
            fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notas TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cif TEXT,
            contacto TEXT,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            codigo_postal TEXT,
            fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --- Usuarios y sesiones de caja --------------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'cajero',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sesiones_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cierre TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'abierta'
        )
        """
    )

    # --- Borradores de facturas -------------------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_borradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metodo_pago TEXT DEFAULT 'Efectivo',
            notas TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_borradores_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrador_id INTEGER NOT NULL
                REFERENCES facturas_borradores(id) ON DELETE CASCADE,
            nombre_producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            tipo_iva INTEGER NOT NULL DEFAULT 21,
            subtotal REAL NOT NULL
        )
        """
    )

    # --- Documentos existentes: crearlos si faltan (esquema completo) -----
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_presupuesto TEXT UNIQUE NOT NULL,
            cliente_nombre TEXT NOT NULL,
            cliente_email TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            base_imponible REAL DEFAULT 0,
            tipo_iva INTEGER DEFAULT 21,
            total_iva REAL DEFAULT 0,
            total REAL DEFAULT 0,
            estado TEXT DEFAULT 'Pendiente',
            notas TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS presupuestos_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            presupuesto_id INTEGER NOT NULL,
            nombre_producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY(presupuesto_id) REFERENCES presupuestos(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS albaranes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_albaran TEXT UNIQUE NOT NULL,
            fecha TEXT NOT NULL,
            cliente_nombre TEXT NOT NULL,
            cliente_direccion TEXT NOT NULL,
            observaciones TEXT,
            estado TEXT DEFAULT 'Abierto',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS albaranes_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            albaran_id INTEGER NOT NULL,
            nombre_producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            descripcion TEXT,
            FOREIGN KEY(albaran_id) REFERENCES albaranes(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_verifactu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT UNIQUE NOT NULL,
            fecha TEXT NOT NULL,
            nif_emisor TEXT NOT NULL,
            nif_receptor TEXT NOT NULL,
            nombre_receptor TEXT NOT NULL,
            base_imponible REAL NOT NULL,
            tipo_iva INTEGER NOT NULL,
            total_iva REAL NOT NULL,
            total REAL NOT NULL,
            estado TEXT DEFAULT 'Emitida',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_verifactu_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            nombre_producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY(factura_id) REFERENCES facturas_verifactu(id)
        )
        """
    )

    # --- Tablas base (ventas e inventario) ---------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura INTEGER NOT NULL,
            nombre_articulo TEXT NOT NULL,
            valor_articulo REAL NOT NULL,
            cantidad INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'Efectivo',
            cantidad_efectivo REAL DEFAULT 0,
            cantidad_tarjeta REAL DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            stock INTEGER NOT NULL
        )
        """
    )

    # --- Columnas nuevas en tablas existentes ------------------------------
    _add_column(conn, "ventas", "cliente_id INTEGER")
    _add_column(conn, "ventas", "usuario_id INTEGER")
    _add_column(conn, "ventas", "sesion_id INTEGER")
    _add_column(conn, "ventas", "tipo_iva INTEGER")
    _add_column(conn, "ventas", "cuota_iva REAL DEFAULT 0")
    _add_column(conn, "ventas", "base_imponible REAL DEFAULT 0")
    _add_column(conn, "inventario", "proveedor_id INTEGER REFERENCES proveedores(id)")
    _add_column(conn, "presupuestos", "cliente_id INTEGER REFERENCES clientes(id)")
    _add_column(conn, "albaranes", "cliente_id INTEGER REFERENCES clientes(id)")
    _add_column(conn, "facturas_verifactu", "cliente_id INTEGER REFERENCES clientes(id)")

    # --- Usuario administrador por defecto ---------------------------------
    conn.execute(
        """
        INSERT OR IGNORE INTO usuarios (usuario, password_hash, nombre, rol)
        VALUES (?, ?, ?, ?)
        """,
        ("admin", hash_password("admin"), "Administrador", "admin"),
    )


def run_migrations(conn):
    """Aplica sobre *conn* todas las migraciones pendientes, en orden."""
    version_actual = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, fn in sorted(MIGRACIONES):
        if version <= version_actual:
            continue
        try:
            fn(conn)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def ensure_database():
    """Abre la base del usuario y aplica migraciones pendientes.

    Punto de entrada único para el arranque de la app.
    """
    from .db import get_connection

    run_migrations(get_connection())
