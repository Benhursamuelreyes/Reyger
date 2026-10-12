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

LATEST_VERSION = 13

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
    """Flujo Ticket/Factura, correlatividad fiscal y configuración Veri*factu*.

    Añade a ``ventas`` el tipo de documento (ticket simplificado o factura
    completa), el estado (emitido / borrador) y una numeración independiente
    para tickets (``numero_ticket``), ya que hasta ahora ``numero_factura``
    era la única secuencia y el flujo emitía siempre como factura.

    Así mismo amplía la tabla singleton ``business_profile`` con:
      - ``numero_serie_ticket`` / ``numero_serie_factura``: serie/número
        inicial configurable de la secuencia de cada tipo de documento.
      - ``verifactu_activo``: conmutador (toggle) para activar/desactivar
        la integración Veri*factu*.
      - ``whatsapp``: contacto WhatsApp mostrado en la cabecera de los
        tickets (Módulo 2).

    La seguridad de secuencia (imposibilidad de retroceder un número ya
    emitido) se garantiza en la capa de aplicación comprobando el máximo
    ya registrado antes de asignar cualquier número nuevo.
    """
    _asegurar_esquema_correlatividad(conn)


def _asegurar_esquema_correlatividad(conn):
    """Crea/repare las columnas y la tabla de contadores del flujo Ticket/Factura.

    Es idempotente (``_add_column`` y ``CREATE TABLE IF NOT EXISTS``) y se
    invoca desde la migración 9 (aplicación normal) y desde la 10
    (consolidación), de modo que una instalación que quedó en la versión 9
    con un esquema parcial de iteraciones anteriores de desarrollo queda
    reparada antes de sembrar los contadores.
    """
    _add_column(conn, "ventas", "tipo_documento TEXT NOT NULL DEFAULT 'ticket'")
    _add_column(conn, "ventas", "estado TEXT NOT NULL DEFAULT 'emitido'")
    _add_column(conn, "ventas", "numero_ticket TEXT")

    _add_column(conn, "business_profile", "numero_serie_ticket TEXT NOT NULL DEFAULT 'T-'")
    _add_column(conn, "business_profile", "numero_serie_factura TEXT NOT NULL DEFAULT 'F-'")
    _add_column(conn, "business_profile", "verifactu_activo INTEGER NOT NULL DEFAULT 1")
    _add_column(conn, "business_profile", "whatsapp TEXT")

    # Contadores independientes y a prueba de retroceso.
    #
    # La secuencia correlativa NUNCA puede retroceder: guardamos el último
    # número oficial asignado para cada tipo de documento y serie. Un
    # borrado físico de una venta no vuelve a ofrecer números ya usados,
    # porque aqui persiste el máximo asignado.
    #
    # Nota: la unicidad es compuesta (tipo, serie); una iteración previa de
    # desarrollo creó la tabla con UNIQUE sobre tipo solo, lo que impedía
    # varias series para un mismo tipo. Se detecta y se reconstruye.
    tablas = {
        fila[0] for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "contadores_documentos" in tablas:
        fila_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'contadores_documentos'"
        ).fetchone()
        ddl = (fila_sql[0] if fila_sql and fila_sql[0] else "").upper()
        # La unicidad debe ser compuesta (tipo, serie); si no lo es (una
        # iteración previa la creó con UNIQUE sobre tipo solo) se reconstruye.
        if "UNIQUE(TIPO, SERIE)" not in ddl.replace(" ", ""):
            # Reconstruir la tabla NO puede perder los contadores: son el
            # máximo de número ya emitido, y si se pierden la secuencia
            # retrocede y la app reemite números de factura ya usados (duplicado
            # fiscal). Antes de tirar la tabla se preserva el máximo por
            # (tipo, serie). MAX también colapsa de forma segura cualquier
            # fila duplicada que una UNIQUE(tipo) previa hubiera permitido.
            conn.execute("DROP TABLE IF EXISTS _contadores_respaldo")
            conn.execute(
                "CREATE TABLE _contadores_respaldo AS "
                "SELECT tipo, serie, MAX(ultimo_numero) AS ultimo_numero "
                "FROM contadores_documentos GROUP BY tipo, serie"
            )
            conn.execute("DROP TABLE contadores_documentos")
            conn.execute("""
                CREATE TABLE contadores_documentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    serie TEXT NOT NULL,
                    ultimo_numero INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(tipo, serie)
                )
            """)
            conn.execute(
                "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
                "SELECT tipo, serie, ultimo_numero FROM _contadores_respaldo"
            )
            conn.execute("DROP TABLE _contadores_respaldo")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contadores_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            serie TEXT NOT NULL,
            ultimo_numero INTEGER NOT NULL DEFAULT 0,
            UNIQUE(tipo, serie)
        )
    """)


def _sembrar_contadores_documentos(conn):
    """Calcula los contadores iniciales desde las ventas existentes.

    Se ejecuta como parte de la migración 9 para que una instalación con
    datos históricos siga numerando después del máximo ya asignado.
    Es tolerante a bases antiguas sin tabla ``ventas`` o sin las columnas
    de estado, de modo que las migraciones siempre pueden aplicarse.
    """
    tablas = {
        fila[0] for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "ventas" not in tablas:
        _sembrar_contadores_vacios(conn)
        return

    columnas_ventas = {
        fila[1] for fila in conn.execute("PRAGMA table_info(ventas)")
    }
    if not ({"factura", "estado"} <= columnas_ventas):
        _sembrar_contadores_vacios(conn)
        return

    # Facturas: máximo de numero_factura numérico ya emitido (los
    # borradores NO cuentan para la secuencia oficial).
    fila_facturas = conn.execute(
        "SELECT serie, MAX(numero) FROM ("
        "  SELECT SUBSTR(factura, 1, 1) AS serie, "
        "         CAST(SUBSTR(factura, 2) AS INTEGER) AS numero "
        "  FROM ventas WHERE estado = 'emitido' AND factura NOT LIKE 'BORRADOR%'"
        "  AND factura NOT GLOB '*[a-zA-Z]*'"
        ") WHERE serie IS NOT NULL AND numero IS NOT NULL "
        "GROUP BY serie"
    ).fetchall()
    for serie, maximo in fila_facturas:
        conn.execute(
            "INSERT OR IGNORE INTO contadores_documentos (tipo, serie, ultimo_numero) "
            "VALUES ('factura', ?, ?)",
            (serie, maximo or 0),
        )

    # Tickets: los emitidos sí cuentan (fase actual solo tickets).
    if "numero_ticket" in columnas_ventas:
        fila_tickets = conn.execute(
            "SELECT serie, MAX(numero) FROM ("
            "  SELECT SUBSTR(numero_ticket, 1, 1) AS serie, "
            "         CAST(SUBSTR(numero_ticket, 2) AS INTEGER) AS numero "
            "  FROM ventas WHERE estado = 'emitido' AND numero_ticket IS NOT NULL "
            ") WHERE serie IS NOT NULL AND numero IS NOT NULL "
            "GROUP BY serie"
        ).fetchall()
        for serie, maximo in fila_tickets:
            conn.execute(
                "INSERT OR IGNORE INTO contadores_documentos (tipo, serie, ultimo_numero) "
                "VALUES ('ticket', ?, ?)",
                (serie, maximo or 0),
            )

    _sembrar_contadores_vacios(conn)


def _sembrar_contadores_vacios(conn):
    """Si no hay contadores aún, siembra ticket y factura en 0.

    La serie inicial configurable se aplica luego en la capa de
    aplicación (``core/correlativos.py``) usando ``max(contador, inicio)``.
    """
    if not conn.execute("SELECT COUNT(*) FROM contadores_documentos").fetchone()[0]:
        conn.execute(
            "INSERT OR IGNORE INTO contadores_documentos (tipo, serie, ultimo_numero) VALUES "
            "('ticket', 'T-', 0), ('factura', 'F-', 0)"
        )


@migracion(10)
def _migracion_10(conn):
    """Consolida el esquema de correlatividad y siembra los contadores.

    Además de sembrar, repara instalaciones que quedaron en la versión 9 con
    un esquema parcial (columnas o tabla ausentes por iteraciones previas de
    desarrollo) antes de calcular los contadores iniciales.
    """
    _asegurar_esquema_correlatividad(conn)
    _sembrar_contadores_documentos(conn)


@migracion(11)
def _migracion_11(conn):
    """Nombre comercial de la empresa.

    Añade a la tabla singleton ``business_profile`` el nombre comercial /
    nombre de la tienda (p. ej. 'GIGA'), que se imprime bajo la razón
    social en tickets y facturas si está informado.
    """
    _add_column(conn, "business_profile", "nombre_comercial TEXT DEFAULT ''")


@migracion(12)
def _migracion_12(conn):
    """Margen de ganancia en productos.

    Añade la columna ``margen_porcentaje`` a ``inventario`` para guardar el
    porcentaje de margen/ganancia configurado al crear o editar un producto.
    """
    _add_column(conn, "inventario", "margen_porcentaje REAL")


# ---------------------------------------------------------------------------
# Índices y reconciliación de correlatividad
# ---------------------------------------------------------------------------

#: Índices que crea la migración 13, con el motivo medido de cada uno.
#:
#: Todos son ``IF NOT EXISTS`` y solo(additivos): no se reescribe ni una
#: fila de ``ventas``, ``facturas_verifactu`` ni ``contadores_documentos``.
INDICES_V13 = (
    # Importacion de clientes: `SELECT id FROM clientes WHERE documento = ?` por
    # fila. Medido sobre 5.000 clientes / 20.000 productos:
    # SCAN clientes (200 us) -> SEARCH con indice covering (7 us), 27x.
    ("clientes",
     "CREATE INDEX IF NOT EXISTS idx_clientes_documento ON clientes(documento)"),
    # Listado de ventas de un cliente (FK que se anade en esta migracion).
    # SCAN ventas (1.568 us) -> SEARCH (7 us), 218x.
    ("ventas",
     "CREATE INDEX IF NOT EXISTS idx_ventas_cliente_id ON ventas(cliente_id)"),
    # `SELECT IFNULL(MAX(numero_ord),0)` se ejecuta en CADA factura
    # emitida: SEARCH facturas_verifactu (161 us) -> covering index (7 us),
    # 23x. Ademas elimina el USE TEMP B-TREE de verificar_cadena(),
    # exportar XML y el CSV de verificacion (1.17x-1.27x).
    ("facturas_verifactu",
     "CREATE INDEX IF NOT EXISTS idx_verifactu_numero_ord ON facturas_verifactu(numero_ord)"),
    # Exportacion de XML de pendientes: la consulta filtra por estado y
    # ordena por numero_ord. Sustituye a idx_verifactu_estado, que solo
    # cubria el filtro y obligaba a ordenar en memoria (1.18x).
    ("facturas_verifactu",
     "CREATE INDEX IF NOT EXISTS idx_verifactu_estado_numero_ord ON facturas_verifactu(estado_envio, numero_ord)"),
    # Índices de las claves foráneas hijas. Con foreign_keys=ON, borrar un
    # cliente recorre facturas_verifactu, albaranes y presupuestos; sin
    # estos índices cada borrado pagaba un SCAN completo de las tres.
    ("facturas_verifactu",
     "CREATE INDEX IF NOT EXISTS idx_facturas_verifactu_cliente_id ON facturas_verifactu(cliente_id)"),
    ("albaranes",
     "CREATE INDEX IF NOT EXISTS idx_albaranes_cliente_id ON albaranes(cliente_id)"),
    ("presupuestos",
     "CREATE INDEX IF NOT EXISTS idx_presupuestos_cliente_id ON presupuestos(cliente_id)"),
    # Inventario: mismo motivo al borrar o reasignar una categoría o un
    # proveedor (categorias.eliminar reasigna antes de borrar).
    ("inventario",
     "CREATE INDEX IF NOT EXISTS idx_inventario_categoria_id ON inventario(categoria_id)"),
    ("inventario",
     "CREATE INDEX IF NOT EXISTS idx_inventario_proveedor_id ON inventario(proveedor_id)"),
    # Líneas de documento: se consultan siempre por su padre y las
    # borradoras se borran con ON DELETE CASCADE.
    ("albaranes_productos",
     "CREATE INDEX IF NOT EXISTS idx_albaranes_productos_albaran_id ON albaranes_productos(albaran_id)"),
    ("facturas_verifactu_productos",
     "CREATE INDEX IF NOT EXISTS idx_facturas_verifactu_productos_factura_id ON facturas_verifactu_productos(factura_id)"),
    ("facturas_borradores_productos",
     "CREATE INDEX IF NOT EXISTS idx_facturas_borradores_productos_borrador_id ON facturas_borradores_productos(borrador_id)"),
    ("presupuestos_productos",
     "CREATE INDEX IF NOT EXISTS idx_presupuestos_productos_presupuesto_id ON presupuestos_productos(presupuesto_id)"),
)

#: Índices que dejan de ser necesarios al crear su versión compuesta.
INDICES_V13_SOBRANTES = ("idx_verifactu_estado",)


#: (tipo, columna de ``ventas``, prefijo de serie) usado por la app.
SERIES_CORRELATIVAS = (
    ("factura", "factura", "F-"),
    ("ticket", "numero_ticket", "T-"),
)


def _maximo_correlativo(conn, columna, prefijo):
    """Máximo ya emitido para *prefijo*, con la misma expresión que usa
    ``core.correlativos._maximo_en_ventas`` (red de seguridad)."""
    # ``columna`` y ``prefijo`` provienen de SERIES_CORRELATIVAS, no de
    # entrada del usuario: el identificador se interpola, el prefijo se
    # enlaza. (Si se enlazara también la columna, REPLACE() operaría
    # sobre el texto "numero_ticket" y devolvería siempre 0.)
    fila = conn.execute(
        f"SELECT IFNULL(MAX(CAST(REPLACE({columna}, ?, '') AS INTEGER)), 0) "
        f"FROM ventas WHERE estado = 'emitido' AND {columna} LIKE ?",
        (prefijo, prefijo + "%"),
    ).fetchone()
    return fila[0] if fila and fila[0] and fila[0] > 0 else 0


def _reconciliar_contadores_documentos(conn):
    """Asegura que exista un contador utilizable por cada tipo/serie real.

    ``_sembrar_contadores_documentos`` (migraciones 9/10) siembra la serie
    con ``SUBSTR(numero, 1, 1)`` -- 'T' en vez de 'T-' -- y el número con
    ``CAST(SUBSTR(numero, 2) AS INTEGER)``, que sobre 'T-9999' es -9999.
    Una instalacion heredada de esa siembra queda con filas que la aplicacion
    nunca consulta, asi que el numero sale siempre de la red de seguridad
    ``_maximo_en_ventas``; y si la serie coincide, el contador arranca en
    negativo y se reemiten números ya usados.

    Aquí solo se INSERTA o se SUBE con ``MAX``: la secuencia nunca retrocede
    y ninguna fila existente se reescribe o se borra.
    """
    if "ventas" not in {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }:
        return

    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(ventas)")}
    if "factura" not in columnas or "estado" not in columnas:
        return

    if "contadores_documentos" not in {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }:
        return

    # Deliberadamente NO se usa ``ON CONFLICT(tipo, serie)``: esa cláusula
    # exige que exista una restricción UNIQUE que referencie, y si la tabla
    # heredada se creó con ``UNIQUE(tipo)``, SQLite aborta con
    # "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE
    # constraint", la migración 13 falla y ``ensure_database()`` revierte
    # --> la app no arranca. Resolver la fila a mano (SELECT + INSERT/UPDATE)
    # da el mismo resultado y es independiente del esquema heredado.
    for tipo, columna, prefijo in SERIES_CORRELATIVAS:
        if columna not in columnas:
            continue
        maximo = _maximo_correlativo(conn, columna, prefijo)
        if maximo <= 0:
            continue
        # Invariante del módulo: la secuencia NUNCA retrocede, así que solo
        # se sube el contador, jamás se baja ni se reescribe a la baja.
        existente = conn.execute(
            "SELECT ultimo_numero FROM contadores_documentos "
            "WHERE tipo = ? AND serie = ?",
            (tipo, prefijo),
        ).fetchone()
        if existente is None:
            conn.execute(
                "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
                "VALUES (?, ?, ?)",
                (tipo, prefijo, maximo),
            )
        elif maximo > existente[0]:
            conn.execute(
                "UPDATE contadores_documentos SET ultimo_numero = ? "
                "WHERE tipo = ? AND serie = ?",
                (maximo, tipo, prefijo),
            )


@migracion(13)
def _migracion_13(conn):
    """Índices de acceso y reconciliación de la correlatividad.

    - Crea los índices que convierten en ``SEARCH`` los recorridos que
      antes eran ``SCAN`` completos (clientes por documento, ventas por
      cliente, ordinal VeriFACTu, líneas de documento y claves foráneas
      hijas). Aditivo puro: no reescribe filas ni altera valores.
    - Reemplaza ``idx_verifactu_estado`` por su versión compuesta, que
      además cubre el filtro por estado.
    - Inserta los contadores ``('ticket','T-')`` / ``('factura','F-')``
      que la aplicación realmente consulta, tomando el máximo de ``ventas``
      y **sin decrementar** ningún contador existente.
    - Prepara antes el esquema de correlatividad: una instalación heredada
      con ``contadores_documentos`` en ``UNIQUE(tipo)`` (no compuesta) se
      repara aquí, preservando el máximo ya emitido.
    """
    _asegurar_esquema_correlatividad(conn)
    tablas = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    columnas_por_tabla = {}

    def _columnas_de(tabla):
        if tabla not in columnas_por_tabla:
            columnas_por_tabla[tabla] = {
                fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")
            }
        return columnas_por_tabla[tabla]

    for tabla, sentencia in INDICES_V13:
        # Tolerante igual que _add_column: una base heredada puede no
        # tener la tabla, o tenerla sin la columna (las pruebas de
        # migración crean esquemas mínimos a propósito).
        if tabla not in tablas:
            continue
        columnas = [
            c.strip() for c in sentencia[sentencia.index(f"ON {tabla}(") + len(f"ON {tabla}("):].split(")")[0].split(",")
        ]
        if any(c not in _columnas_de(tabla) for c in columnas):
            continue
        conn.execute(sentencia)
    for indice in INDICES_V13_SOBRANTES:
        conn.execute(f"DROP INDEX IF EXISTS {indice}")
    _reconciliar_contadores_documentos(conn)


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
