"""Esquema de documentos de venta y conversión desde la tabla ``ventas``.

Hasta la versión 13 del esquema, cada venta ocupaba una fila de ``ventas``
**por línea de producto**, y los datos del documento (número, método de
pago, importes entregados, cliente, tipo, estado y fecha) se repetían en
cada línea. Eso impedía exigir un número único, multiplicaba el efectivo
entregado al sumarlo y no guardaba qué producto se vendía (solo el nombre).

Desde la versión 14:

* ``documentos``: una fila por ticket, factura o borrador, con número único.
* ``lineas_documento``: sus líneas, con ``producto_id`` y copia del nombre
  (el documento no cambia si después se renombra el producto).
* Los importes se guardan en **céntimos enteros** (``*_cent``), así que los
  totales se calculan con ``SUM`` exacto.
* La fecha es la hora **local** en formato ISO (``AAAA-MM-DD HH:MM:SS``).
* ``ventas`` pasa a ser una **vista de solo lectura** con las columnas de
  siempre (importes en euros), para consultas y herramientas antiguas.

:func:`convertir_ventas_legado` traslada las filas del formato antiguo; la
usan la migración 14 y la importación de copias antiguas en Excel/CSV.
"""

import logging
from datetime import datetime, timezone

from ..domain.fiscal import IVA_POR_DEFECTO, a_centimos, desglose_linea_cent

log = logging.getLogger(__name__)

TIPOS_DOCUMENTO = ("ticket", "factura")
ESTADOS_DOCUMENTO = ("emitido", "borrador")

#: Fecha local actual en el formato de ``documentos.fecha``.
FECHA_LOCAL_SQL = "(strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))"

_ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- «T-0001», «F-0003» o, en un borrador, «BORRADOR-…».
    numero TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL CHECK (tipo IN ('ticket', 'factura')),
    estado TEXT NOT NULL CHECK (estado IN ('emitido', 'borrador')),
    fecha TEXT NOT NULL DEFAULT {FECHA_LOCAL_SQL},
    cliente_id INTEGER REFERENCES clientes(id),
    metodo_pago TEXT NOT NULL DEFAULT 'Efectivo',
    efectivo_cent INTEGER NOT NULL DEFAULT 0 CHECK (efectivo_cent >= 0),
    tarjeta_cent INTEGER NOT NULL DEFAULT 0 CHECK (tarjeta_cent >= 0)
);

CREATE TABLE IF NOT EXISTS lineas_documento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    -- NULL si el producto se borró del inventario: la línea se conserva.
    producto_id INTEGER REFERENCES inventario(id) ON DELETE SET NULL,
    nombre TEXT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad <> 0),
    precio_cent INTEGER NOT NULL CHECK (precio_cent >= 0),
    tipo_iva REAL NOT NULL CHECK (tipo_iva >= 0 AND tipo_iva <= 100),
    subtotal_cent INTEGER NOT NULL,
    base_cent INTEGER NOT NULL,
    cuota_cent INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documentos_fecha ON documentos(fecha);
CREATE INDEX IF NOT EXISTS idx_documentos_cliente_id ON documentos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_documentos_tipo_estado ON documentos(tipo, estado);
CREATE INDEX IF NOT EXISTS idx_lineas_documento_documento_id ON lineas_documento(documento_id);
CREATE INDEX IF NOT EXISTS idx_lineas_documento_producto_id ON lineas_documento(producto_id);
"""

#: Vista de compatibilidad: una fila por línea, con las columnas y unidades
#: (euros) de la antigua tabla ``ventas``. Los importes entregados se repiten
#: en cada línea igual que antes: no deben sumarse por línea.
VISTA_VENTAS = """
CREATE VIEW IF NOT EXISTS ventas AS
SELECT l.id AS id,
       d.numero AS factura,
       l.nombre AS nombre_articulo,
       l.precio_cent / 100.0 AS valor_articulo,
       l.cantidad AS cantidad,
       l.subtotal_cent / 100.0 AS subtotal,
       d.metodo_pago AS metodo_pago,
       d.efectivo_cent / 100.0 AS cantidad_efectivo,
       d.tarjeta_cent / 100.0 AS cantidad_tarjeta,
       d.fecha AS fecha,
       d.cliente_id AS cliente_id,
       l.tipo_iva AS tipo_iva,
       l.cuota_cent / 100.0 AS cuota_iva,
       l.base_cent / 100.0 AS base_imponible,
       d.tipo AS tipo_documento,
       d.estado AS estado,
       CASE WHEN d.tipo = 'ticket' AND d.estado = 'emitido' THEN d.numero END
           AS numero_ticket,
       l.documento_id AS documento_id,
       l.producto_id AS producto_id
FROM lineas_documento l
JOIN documentos d ON d.id = l.documento_id
"""


def crear_esquema(conn):
    """Crea ``documentos``, ``lineas_documento`` y sus índices (idempotente)."""
    for sentencia in _ESQUEMA.split(";"):
        if sentencia.strip():
            conn.execute(sentencia)


def crear_vista_ventas(conn):
    conn.execute(VISTA_VENTAS)


# --------------------------------------------------------------- conversión
_FORMATOS_LOCALES = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")


def normalizar_fecha(valor):
    """Convierte una fecha del formato antiguo a hora local ISO.

    * ``AAAA-MM-DD HH:MM:SS`` venía de ``CURRENT_TIMESTAMP`` (UTC): se pasa a
      la hora local.
    * ``dd/mm/aaaa [HH:MM]`` (borradores) ya era hora local.

    Devuelve ``None`` si el valor está vacío o no se reconoce.
    """
    if valor in (None, ""):
        return None
    texto = str(valor).strip()
    try:
        utc = datetime.fromisoformat(texto.replace("T", " ")[:19])
    except ValueError:
        utc = None
    if utc is not None:
        if len(texto) <= 10:  # solo fecha: no hay hora que convertir
            return utc.strftime("%Y-%m-%d 00:00:00")
        local = utc.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        return local.strftime("%Y-%m-%d %H:%M:%S")
    for formato in _FORMATOS_LOCALES:
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _ids(conn, tabla):
    try:
        return {fila[0] for fila in conn.execute(f"SELECT id FROM {tabla}")}
    except Exception:
        return set()


def _ids_por_nombre(conn):
    """{nombre: id} de los productos con nombre único en el inventario."""
    try:
        filas = conn.execute(
            "SELECT nombre, MIN(id), COUNT(*) FROM inventario GROUP BY nombre"
        ).fetchall()
    except Exception:
        return {}
    return {nombre: id_ for nombre, id_, n in filas if n == 1}


def _numero(valor):
    try:
        return a_centimos(float(valor))
    except (TypeError, ValueError):
        return None


def _entero(valor):
    """Entero desde un valor de BD, Excel o CSV («7», «2.0»); ``None`` si no."""
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def convertir_ventas_legado(conn, tabla="ventas"):
    """Pasa las filas de *tabla* (formato antiguo) a documentos y líneas.

    Tolera las columnas que falten en bases muy antiguas. Las filas que no
    pueden convertirse (sin número de documento, cantidad 0 o precio
    negativo) se omiten y se registran en el log, en vez de impedir que la
    aplicación arranque. Devuelve ``{"documentos", "lineas", "omitidas"}``.
    """
    cursor = conn.execute(f"SELECT * FROM {tabla} ORDER BY rowid")
    columnas = [d[0] for d in cursor.description]
    filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

    clientes = _ids(conn, "clientes")
    productos = _ids(conn, "inventario")
    por_nombre = _ids_por_nombre(conn)
    hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    grupos = {}
    omitidas = []
    for fila in filas:
        numero = fila.get("factura")
        if numero in (None, ""):
            omitidas.append((fila.get("id"), "sin número de documento"))
            continue
        grupos.setdefault(str(numero), []).append(fila)

    fechas_desconocidas = 0
    n_documentos = n_lineas = 0
    for numero, lineas in grupos.items():
        primera = lineas[0]
        tipo = "factura" if primera.get("tipo_documento") == "factura" else "ticket"
        estado = (
            "emitido"
            if any(l.get("estado", "emitido") != "borrador" for l in lineas)
            else "borrador"
        )
        fecha = normalizar_fecha(primera.get("fecha"))
        if fecha is None:
            fechas_desconocidas += 1
            fecha = hoy
        cliente_id = _entero(primera.get("cliente_id"))
        if cliente_id not in clientes:
            cliente_id = None
        # Los importes entregados se repetían en cada línea: se toman una vez.
        efectivo = max(0, _numero(primera.get("cantidad_efectivo")) or 0)
        tarjeta = max(0, _numero(primera.get("cantidad_tarjeta")) or 0)

        validas = []
        for linea in lineas:
            cantidad = _entero(linea.get("cantidad")) or 0
            precio = _numero(linea.get("valor_articulo"))
            if cantidad == 0:
                omitidas.append((linea.get("id"), "cantidad 0 o vacía"))
                continue
            if precio is None or precio < 0:
                omitidas.append((linea.get("id"), "precio vacío o negativo"))
                continue
            try:
                tipo_iva = float(linea.get("tipo_iva"))
            except (TypeError, ValueError):
                tipo_iva = IVA_POR_DEFECTO
            if not 0 <= tipo_iva <= 100:
                tipo_iva = IVA_POR_DEFECTO
            subtotal = _numero(linea.get("subtotal"))
            base = _numero(linea.get("base_imponible"))
            cuota = _numero(linea.get("cuota_iva"))
            if subtotal is None:
                subtotal = precio * cantidad
            # Filas anteriores al desglose de IVA: base y cuota quedaban a 0.
            if base is None or cuota is None or (not base and not cuota and subtotal):
                _, base, cuota = desglose_linea_cent(precio, cantidad, tipo_iva)
            nombre = linea.get("nombre_articulo") or "(sin nombre)"
            producto_id = _entero(linea.get("producto_id"))
            if producto_id not in productos:
                producto_id = por_nombre.get(nombre)
            validas.append((
                producto_id, nombre, cantidad, precio, tipo_iva, subtotal, base, cuota,
            ))
        if not validas:
            continue

        documento_id = conn.execute(
            "INSERT INTO documentos (numero, tipo, estado, fecha, cliente_id,"
            " metodo_pago, efectivo_cent, tarjeta_cent) VALUES (?,?,?,?,?,?,?,?)",
            (numero, tipo, estado, fecha, cliente_id,
             primera.get("metodo_pago") or "Efectivo", efectivo, tarjeta),
        ).lastrowid
        conn.executemany(
            "INSERT INTO lineas_documento (documento_id, producto_id, nombre,"
            " cantidad, precio_cent, tipo_iva, subtotal_cent, base_cent, cuota_cent)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [(documento_id,) + v for v in validas],
        )
        n_documentos += 1
        n_lineas += len(validas)

    if omitidas:
        log.warning(
            "Conversión de ventas: %d filas omitidas: %s",
            len(omitidas), omitidas[:20],
        )
    if fechas_desconocidas:
        log.warning(
            "Conversión de ventas: %d documentos sin fecha reconocible; se les "
            "asigna la fecha de la conversión", fechas_desconocidas,
        )
    resumen = {"documentos": n_documentos, "lineas": n_lineas, "omitidas": len(omitidas)}
    log.info("Conversión de ventas: %s", resumen)
    return resumen
