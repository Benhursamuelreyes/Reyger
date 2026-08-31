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

from ..domain.fiscal import IVA_POR_DEFECTO

LATEST_VERSION = 10

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
    """Fase 2: catálogos relacionales, borradores e IVA."""

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
    _add_column(conn, "ventas", "tipo_iva INTEGER")
    _add_column(conn, "ventas", "cuota_iva REAL DEFAULT 0")
    _add_column(conn, "ventas", "base_imponible REAL DEFAULT 0")
    _add_column(conn, "inventario", "proveedor_id INTEGER REFERENCES proveedores(id)")
    _add_column(conn, "presupuestos", "cliente_id INTEGER REFERENCES clientes(id)")
    _add_column(conn, "albaranes", "cliente_id INTEGER REFERENCES clientes(id)")
    _add_column(conn, "facturas_verifactu", "cliente_id INTEGER REFERENCES clientes(id)")


@migracion(2)
def _migracion_2(conn):
    """Fase 3: IVA por producto en el inventario."""

    _add_column(
        conn,
        "inventario",
        f"tipo_iva REAL NOT NULL DEFAULT {IVA_POR_DEFECTO}",
    )


@migracion(3)
def _migracion_3(conn):
    """Categorias de productos (frutas, carnes, informatica, moviles...)."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT OR IGNORE INTO categorias (nombre) VALUES ('General')")
    _add_column(conn, "inventario", "categoria_id INTEGER REFERENCES categorias(id)")
    # Los productos existentes quedan agrupados en la categoria General
    conn.execute(
        """
        UPDATE inventario SET categoria_id =
            (SELECT id FROM categorias WHERE nombre = 'General')
        WHERE categoria_id IS NULL
        """
    )


@migracion(4)
def _migracion_4(conn):
    """Se elimina el inicio de sesión: fuera usuarios, sesiones de caja
    y las columnas usuario_id/sesion_id de las ventas."""

    conn.execute("DROP TABLE IF EXISTS sesiones_caja")
    conn.execute("DROP TABLE IF EXISTS usuarios")

    actuales = [fila[1] for fila in conn.execute("PRAGMA table_info(ventas)")]
    if not any(c in actuales for c in ("usuario_id", "sesion_id")):
        return

    objetivo = (
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "factura INTEGER NOT NULL",
        "nombre_articulo TEXT NOT NULL",
        "valor_articulo REAL NOT NULL",
        "cantidad INTEGER NOT NULL",
        "subtotal REAL NOT NULL",
        "metodo_pago TEXT DEFAULT 'Efectivo'",
        "cantidad_efectivo REAL DEFAULT 0",
        "cantidad_tarjeta REAL DEFAULT 0",
        "fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "cliente_id INTEGER",
        "tipo_iva INTEGER",
        "cuota_iva REAL DEFAULT 0",
        "base_imponible REAL DEFAULT 0",
    )
    conservar = [
        c for c in (parte.split()[0] for parte in objetivo) if c in actuales
    ]
    conn.execute(
        "CREATE TABLE ventas_sin_usuario (" + ", ".join(objetivo) + ")"
    )
    lista = ", ".join(conservar)
    conn.execute(f"INSERT INTO ventas_sin_usuario ({lista}) SELECT {lista} FROM ventas")
    conn.execute("DROP TABLE ventas")
    conn.execute("ALTER TABLE ventas_sin_usuario RENAME TO ventas")


def _indexar(conn, nombre, tabla, columnas, unico=False):
    """Crea un índice si la tabla y todas sus columnas existen.

    Las bases antiguas pueden carecer de columnas que las modernas dan
    por sentadas; en ese caso se omite el índice sin fallar la migración.
    """
    tablas = {
        fila[0] for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if tabla not in tablas:
        return
    presentes = {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
    if not set(columnas) <= presentes:
        return
    prefijo = "UNIQUE INDEX" if unico else "INDEX"
    conn.execute(
        f"CREATE {prefijo} IF NOT EXISTS {nombre} ON {tabla}({', '.join(columnas)})"
    )


@migracion(5)
def _migracion_5(conn):
    """Fase 6: índices de rendimiento y columna codigo_barras centralizada.

    La columna ``codigo_barras`` deja de depender de que el usuario haya
    usado el escáner: se crea aquí (si falta) junto a su índice único.
    """
    _add_column(conn, "inventario", "codigo_barras TEXT")

    _indexar(
        conn,
        "idx_inventario_codigo_barras",
        "inventario",
        ["codigo_barras"],
        unico=True,
    )
    _indexar(conn, "idx_inventario_nombre", "inventario", ["nombre"])
    _indexar(conn, "idx_ventas_fecha", "ventas", ["fecha"])
    _indexar(conn, "idx_ventas_factura", "ventas", ["factura"])
    _indexar(conn, "idx_clientes_nombre", "clientes", ["nombre"])


@migracion(6)
def _migracion_6(conn):
    """Tabla business_profile: datos fiscales y de contacto de la empresa.

    Almacena la información necesaria para facturas, tickets, albaranes
    y el cumplimiento VeriFactu (número de series, NIF, actividad
    económica, etc.). Se usa un patrón singleton: la tabla siempre
    contiene una sola fila (id=1).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS business_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nombre TEXT NOT NULL DEFAULT 'Mi Empresa',
            nif TEXT,
            direccion TEXT,
            codigo_postal TEXT,
            provincia TEXT,
            telefono TEXT,
            email TEXT,
            actividad_economica TEXT,
            numero_series TEXT DEFAULT 'A',
            logo_path TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO business_profile (id, nombre) VALUES (1, 'Mi Empresa')"
    )


@migracion(7)
def _migracion_7(conn):
    """VeriFactu AEAT: cadenas de hash SHA-256, tipología y trazabilidad.

    Añade columnas a ``facturas_verifactu`` para el cumplimiento de la
    normativa VeriFactu: huella SHA-256, encadenamiento con la factura
    anterior, tipo de comprobante y campos de envío a AEAT.
    """
    _add_column(conn, "facturas_verifactu", "huella TEXT")
    _add_column(conn, "facturas_verifactu", "huella_anterior TEXT")
    _add_column(conn, "facturas_verifactu", "numero_ord INTEGER")
    _add_column(conn, "facturas_verifactu", "tipo_comprobante TEXT DEFAULT 'F1'")
    _add_column(conn, "facturas_verifactu", "cadena_valores TEXT")
    _add_column(conn, "facturas_verifactu", "fecha_generacion TEXT")
    _add_column(conn, "facturas_verifactu", "estado_envio TEXT DEFAULT 'pendiente'")
    _add_column(conn, "facturas_verifactu", "respuesta_aeat TEXT")
    _add_column(conn, "facturas_verifactu", "numero_precinto TEXT")
    _indexar(conn, "idx_verifactu_huella", "facturas_verifactu", ["huella"])
    _indexar(conn, "idx_verifactu_estado", "facturas_verifactu", ["estado_envio"])


@migracion(8)
def _migracion_8(conn):
    """Multimoneda y configuración regional.

    Añade a la tabla singleton ``business_profile`` la moneda del sistema
    (código ISO) y el formato regional/locale. Por defecto siguen siendo
    EUR y es_ES.
    """
    _add_column(conn, "business_profile", "moneda TEXT NOT NULL DEFAULT 'EUR'")
    _add_column(conn, "business_profile", "locale TEXT NOT NULL DEFAULT 'es_ES'")


@migracion(9)
def _migracion_9(conn):
    """Nombre comercial de la empresa.

    Añade a la tabla singleton ``business_profile`` el nombre comercial /
    nombre de la tienda (p. ej. 'GIGA'), que se imprime bajo la razón
    social en tickets y facturas si está informado.
    """
    _add_column(conn, "business_profile", "nombre_comercial TEXT DEFAULT ''")


@migracion(10)
def _migracion_10(conn):
    """Cierre y conteo de caja (arqueo).

    Crea las tablas de movimientos de caja (ingresos/retiros manuales que
    ajustan el total esperado) y de cierres de caja (registro del arqueo:
    resumen de ventas por método de pago, total esperado, total contado,
    descuadre y desglose por denominaciones).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK (tipo IN ('INGRESO', 'RETIRO')),
            importe REAL NOT NULL DEFAULT 0,
            concepto TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cierres_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_apertura TEXT,
            fecha_cierre TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario TEXT,
            total_ventas REAL DEFAULT 0,
            total_efectivo_esperado REAL DEFAULT 0,
            total_tarjeta REAL DEFAULT 0,
            num_facturas_mixtas INTEGER DEFAULT 0,
            ingreso_manual REAL DEFAULT 0,
            retiro_manual REAL DEFAULT 0,
            total_esperado REAL DEFAULT 0,
            total_contado REAL DEFAULT 0,
            diferencia REAL DEFAULT 0,
            notas TEXT,
            desglose TEXT
        )
        """
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
