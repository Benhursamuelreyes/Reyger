"""Operaciones de venta sobre la base de datos, sin interfaz gráfica.

Cobrar el carrito, guardarlo como borrador, emitir un borrador como factura
y leer documentos para reimprimirlos. ``ui.ventas`` se limita a recoger los
datos de los widgets, llamar aquí y encargarse de los efectos secundarios
(PDF, ticket térmico, Veri*factu*), que nunca van dentro de la transacción:
si fallaran harían rollback de una venta ya cobrada.

Se guardan en ``documentos`` (uno por ticket, factura o borrador) y
``lineas_documento``, con importes en céntimos (ver ``core.documentos``).
Hacia fuera los importes van en euros y las líneas de producto se devuelven
como tuplas ``(nombre, precio, cantidad, subtotal, tipo_iva, base, cuota)``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..core import correlativos, db
from ..core.documentos import FECHA_LOCAL_SQL, normalizar_fecha
from .fiscal import a_centimos, a_euros, desglose_linea_cent

#: Métodos de pago admitidos por :func:`validar_pago`.
METODOS_PAGO = ("Efectivo", "Tarjeta", "Mixto")


@dataclass(frozen=True)
class LineaVenta:
    nombre: str
    precio: float
    cantidad: int
    tipo_iva: float
    id_producto: Optional[int] = None


@dataclass
class Documento:
    """Documento guardado: venta emitida o borrador."""

    numero: str
    productos: List[tuple] = field(default_factory=list)
    total: float = 0.0
    base: float = 0.0
    cuota: float = 0.0
    correlativo: Optional[int] = None  # solo en documentos emitidos
    cliente_id: Optional[int] = None
    metodo_pago: Optional[str] = None


def validar_pago(metodo, efectivo, tarjeta, total):
    """Devuelve el mensaje de error si el pago no cubre *total*, o ``None``."""
    if metodo == "Efectivo" and efectivo < total:
        return "Cantidad en efectivo insuficiente"
    if metodo == "Tarjeta" and tarjeta < total:
        return "Cantidad en tarjeta insuficiente"
    if metodo == "Mixto" and (efectivo + tarjeta) < total:
        return "Pago insuficiente (efectivo + tarjeta)"
    return None


def _desglosar(lineas):
    """Devuelve las líneas en céntimos: [(linea, precio, subtotal, base, cuota)]."""
    resultado = []
    for linea in lineas:
        precio = a_centimos(linea.precio)
        subtotal, base, cuota = desglose_linea_cent(precio, linea.cantidad, linea.tipo_iva)
        resultado.append((linea, precio, subtotal, base, cuota))
    return resultado


def _id_producto(conn, nombre, id_producto=None):
    """Id del producto: el del carrito o, si no viene, el único con ese nombre."""
    if id_producto is not None:
        return id_producto
    fila = conn.execute(
        "SELECT id FROM inventario WHERE nombre = ?", (nombre,)
    ).fetchone()
    return fila["id"] if fila else None


def _descontar_stock(conn, nombre, cantidad, id_producto):
    """Descuenta *cantidad* del producto por su id.

    Por nombre se descontarían todas las filas homónimas, y si el producto
    se hubiera renombrado tras añadirlo al carrito no se descontaría
    ninguna (venta sin stock).
    """
    if id_producto is None:
        raise LookupError(
            f"El producto «{nombre}» ya no existe en el inventario; "
            "no se puede emitir el documento."
        )
    cur = conn.execute(
        "UPDATE inventario SET stock = stock - ? WHERE id = ?",
        (cantidad, id_producto),
    )
    if cur.rowcount != 1:
        raise LookupError(f"No se pudo actualizar el stock de «{nombre}»")


def _insertar_documento(conn, numero, tipo, estado, lineas, cliente_id=None,
                        metodo_pago="Efectivo", efectivo=0.0, tarjeta=0.0,
                        fecha=None, descontar_stock=False):
    """Inserta el documento y sus líneas; devuelve el id del documento."""
    columnas = (
        "numero, tipo, estado, cliente_id, metodo_pago, efectivo_cent, tarjeta_cent"
    )
    valores = [
        numero, tipo, estado, cliente_id, metodo_pago,
        a_centimos(efectivo), a_centimos(tarjeta),
    ]
    if fecha is not None:
        columnas += ", fecha"
        valores.append(fecha)
    documento_id = conn.execute(
        f"INSERT INTO documentos ({columnas}) VALUES ({', '.join('?' * len(valores))})",
        valores,
    ).lastrowid
    for linea, precio, subtotal, base, cuota in _desglosar(lineas):
        id_producto = _id_producto(conn, linea.nombre, linea.id_producto)
        if descontar_stock:
            _descontar_stock(conn, linea.nombre, linea.cantidad, id_producto)
        conn.execute(
            "INSERT INTO lineas_documento (documento_id, producto_id, nombre,"
            " cantidad, precio_cent, tipo_iva, subtotal_cent, base_cent, cuota_cent)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (documento_id, id_producto, linea.nombre, linea.cantidad, precio,
             linea.tipo_iva, subtotal, base, cuota),
        )
    return documento_id


def registrar_venta(lineas, tipo_documento, metodo_pago, efectivo=0.0,
                    tarjeta=0.0, cliente_id=None):
    """Cobra *lineas* como ``'ticket'`` o ``'factura'`` en una transacción.

    Asigna el número correlativo oficial (que nunca retrocede), guarda el
    documento y sus líneas, descuenta el stock y registra el número en
    ``contadores_documentos``. Si algo falla (p. ej. un producto borrado,
    que lanza ``LookupError``) no se guarda nada.
    """
    prefijo, correlativo = correlativos.siguiente_numero(tipo_documento)
    numero = f"{prefijo}{correlativo:04d}"
    with db.transaccion() as conn:
        _insertar_documento(
            conn, numero, tipo_documento, "emitido", lineas, cliente_id,
            metodo_pago, efectivo, tarjeta, descontar_stock=True,
        )
        correlativos.reservar_numero(tipo_documento, correlativo, prefijo, conn=conn)
    documento = leer_documento(numero)
    documento.correlativo = correlativo
    return documento


def guardar_borrador(lineas, cliente_id, fecha=None):
    """Guarda *lineas* como borrador de factura (sin número oficial).

    *fecha* puede ser un ``datetime``, un texto ``dd/mm/aaaa HH:MM`` o
    ``None`` (ahora). La clave interna es aleatoria: ``int(time.time())``
    colisionaba entre dos borradores guardados en el mismo segundo, que
    entonces se emitían fusionados como una sola factura.
    """
    clave = f"BORRADOR-{uuid.uuid4().hex[:12]}"
    if isinstance(fecha, datetime):
        fecha = fecha.strftime("%Y-%m-%d %H:%M:%S")
    elif fecha is not None:
        fecha = normalizar_fecha(fecha)
    with db.transaccion() as conn:
        _insertar_documento(
            conn, clave, "factura", "borrador", lineas, cliente_id,
            metodo_pago="Pendiente", fecha=fecha,
        )
    return leer_documento(clave)


def emitir_borrador(clave):
    """Convierte el borrador *clave* en factura con número oficial.

    Emite **todas** sus líneas, descuenta su stock y registra el número. La
    fecha pasa a ser la de emisión (la que lleva el PDF). Devuelve el
    :class:`Documento` emitido, o ``None`` si el borrador ya no existe.
    """
    prefijo, correlativo = correlativos.siguiente_numero("factura")
    numero = f"{prefijo}{correlativo:04d}"

    with db.transaccion() as conn:
        fila = conn.execute(
            "SELECT id FROM documentos WHERE numero = ? AND estado = 'borrador'",
            (clave,),
        ).fetchone()
        if fila is None:
            return None
        lineas = conn.execute(
            "SELECT id, producto_id, nombre, cantidad FROM lineas_documento "
            "WHERE documento_id = ? ORDER BY id",
            (fila["id"],),
        ).fetchall()
        if not lineas:
            return None
        conn.execute(
            f"UPDATE documentos SET numero = ?, estado = 'emitido', "
            f"fecha = {FECHA_LOCAL_SQL} WHERE id = ?",
            (numero, fila["id"]),
        )
        for linea in lineas:
            id_producto = _id_producto(conn, linea["nombre"], linea["producto_id"])
            _descontar_stock(conn, linea["nombre"], linea["cantidad"], id_producto)
            if linea["producto_id"] is None:
                conn.execute(
                    "UPDATE lineas_documento SET producto_id = ? WHERE id = ?",
                    (id_producto, linea["id"]),
                )
        correlativos.reservar_numero("factura", correlativo, prefijo, conn=conn)

    documento = leer_documento(numero)
    documento.correlativo = correlativo
    return documento


def leer_documento(numero, estado=None):
    """Lee el documento *numero* con todas sus líneas.

    *estado* se acepta por compatibilidad: el número ya es único.
    """
    cabecera = db.query_one(
        "SELECT id, cliente_id, metodo_pago FROM documentos WHERE numero = ?"
        + (" AND estado = ?" if estado else ""),
        (numero, estado) if estado else (numero,),
    )
    if cabecera is None:
        return Documento(numero=numero)
    return _documento_por_id(cabecera["id"], numero, cabecera)


def _documento_por_id(documento_id, numero, cabecera):
    filas = db.query(
        "SELECT nombre, precio_cent, cantidad, subtotal_cent, tipo_iva, base_cent,"
        " cuota_cent FROM lineas_documento WHERE documento_id = ? ORDER BY id",
        (documento_id,),
    )
    productos = [
        (
            f["nombre"], a_euros(f["precio_cent"]), f["cantidad"],
            a_euros(f["subtotal_cent"]), f["tipo_iva"],
            a_euros(f["base_cent"]), a_euros(f["cuota_cent"]),
        )
        for f in filas
    ]
    return Documento(
        numero=numero,
        productos=productos,
        total=a_euros(sum(f["subtotal_cent"] for f in filas)),
        base=a_euros(sum(f["base_cent"] for f in filas)),
        cuota=a_euros(sum(f["cuota_cent"] for f in filas)),
        cliente_id=cabecera["cliente_id"],
        metodo_pago=cabecera["metodo_pago"],
    )


def documento_de_linea(id_linea):
    """Devuelve el documento completo al que pertenece la línea *id_linea*.

    El historial muestra una fila por línea de producto; para reimprimir
    hay que recuperar todas las líneas del documento, no solo la elegida.
    """
    cabecera = db.query_one(
        "SELECT d.id, d.numero, d.cliente_id, d.metodo_pago FROM lineas_documento l"
        " JOIN documentos d ON d.id = l.documento_id WHERE l.id = ?",
        (id_linea,),
    )
    if cabecera is None:
        return None
    return _documento_por_id(cabecera["id"], cabecera["numero"], cabecera)


def listar_lineas():
    """Filas del historial (una por línea), más recientes primero."""
    return db.query(
        "SELECT l.id AS id, d.numero AS factura, d.tipo AS tipo_documento,"
        " d.estado AS estado, l.nombre AS nombre_articulo,"
        " l.precio_cent / 100.0 AS valor_articulo, l.cantidad AS cantidad,"
        " l.subtotal_cent / 100.0 AS subtotal"
        " FROM lineas_documento l JOIN documentos d ON d.id = l.documento_id"
        " ORDER BY d.id DESC, l.id DESC"
    )


def nombre_cliente(cliente_id):
    """Nombre del cliente *cliente_id*, o ``None``."""
    if not cliente_id:
        return None
    fila = db.query_one("SELECT nombre FROM clientes WHERE id = ?", (cliente_id,))
    return fila["nombre"] if fila else None
