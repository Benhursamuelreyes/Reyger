"""Lógica de tarjetas regalo / vales de compra.

Permite crear tarjetas con un saldo inicial, consultar su saldo actual,
aplicarlas como método de pago (descontando total o parcialmente,
quedando el resto para efectivo/tarjeta) y llevar un histórico de
movimientos (emisión, canje y recarga).
"""
import random
import string

from . import db


def generar_codigo(longitud=10):
    """Genera un código alfanumérico único para una tarjeta regalo."""
    abecedario = string.ascii_uppercase + string.digits
    return "".join(random.choices(abecedario, k=longitud))


def _codigo_unico(longitud=10):
    while True:
        codigo = generar_codigo(longitud)
        if not db.query_one(
            "SELECT id FROM tarjetas_regalo WHERE codigo = ?", (codigo,)
        ):
            return codigo


def crear(saldo_inicial, notas="", fecha_vencimiento=None):
    """Crea una tarjeta regalo con saldo inicial. Devuelve su id."""
    saldo = float(saldo_inicial)
    codigo = _codigo_unico()
    with db.transaccion() as conn:
        cur = conn.execute(
            "INSERT INTO tarjetas_regalo (codigo, saldo_inicial, saldo_actual, "
            "fecha_vencimiento, notas) VALUES (?, ?, ?, ?, ?)",
            (codigo, saldo, saldo, fecha_vencimiento, notas or ""),
        )
        tarjeta_id = cur.lastrowid
        conn.execute(
            "INSERT INTO tarjetas_regalo_movimientos "
            "(tarjeta_id, tipo, importe) VALUES (?, 'EMISION', ?)",
            (tarjeta_id, saldo),
        )
    return tarjeta_id, codigo


def obtener(codigo):
    """Devuelve la tarjeta regalo buscada por código, o None."""
    return db.query_one(
        "SELECT * FROM tarjetas_regalo WHERE codigo = ?", (codigo,)
    )


def saldo(codigo):
    """Devuelve el saldo actual de la tarjeta o None si no existe."""
    tarjeta = obtener(codigo)
    if not tarjeta:
        return None
    if tarjeta["estado"] != "ACTIVA":
        return 0.0
    return round(tarjeta["saldo_actual"] or 0.0, 2)


def aplicar_pago(codigo, importe, venta_factura=None):
    """Aplica una tarjeta regalo al pago de un importe.

    Devuelve ``(ok, monto_tarjeta, restante, mensaje)``.
      - Si el saldo cubre el importe: paga todo y queda saldo restante.
      - Si no: descuenta todo el saldo y devuelve el resto a cobrar por
        efectivo/tarjeta.
    """
    tarjeta = obtener(codigo)
    if not tarjeta:
        return False, 0.0, float(importe), "La tarjeta regalo no existe."
    if tarjeta["estado"] != "ACTIVA":
        return False, 0.0, float(importe), "La tarjeta regalo no está activa."
    saldo_disponible = round(tarjeta["saldo_actual"] or 0.0, 2)
    importe = float(importe)
    if saldo_disponible <= 0:
        return False, 0.0, importe, "La tarjeta regalo no tiene saldo."

    if importe <= saldo_disponible:
        monto_tarjeta = importe
        restante = 0.0
    else:
        monto_tarjeta = saldo_disponible
        restante = round(importe - saldo_disponible, 2)

    nuevo_saldo = round(saldo_disponible - monto_tarjeta, 2)
    with db.transaccion() as conn:
        conn.execute(
            "UPDATE tarjetas_regalo SET saldo_actual = ? WHERE id = ?",
            (nuevo_saldo, tarjeta["id"]),
        )
        conn.execute(
            "INSERT INTO tarjetas_regalo_movimientos "
            "(tarjeta_id, tipo, importe, venta_factura) "
            "VALUES (?, 'CANJE', ?, ?)",
            (tarjeta["id"], monto_tarjeta, venta_factura),
        )
    return True, round(monto_tarjeta, 2), round(restante, 2), "OK"


def recargar(codigo, importe):
    """Recarga el saldo de una tarjeta regalo. Devuelve (ok, mensaje)."""
    tarjeta = obtener(codigo)
    if not tarjeta:
        return False, "La tarjeta regalo no existe."
    if tarjeta["estado"] != "ACTIVA":
        return False, "La tarjeta regalo no está activa."
    importe = float(importe)
    nuevo = round((tarjeta["saldo_actual"] or 0.0) + importe, 2)
    with db.transaccion() as conn:
        conn.execute(
            "UPDATE tarjetas_regalo SET saldo_actual = ? WHERE id = ?",
            (nuevo, tarjeta["id"]),
        )
        conn.execute(
            "INSERT INTO tarjetas_regalo_movimientos "
            "(tarjeta_id, tipo, importe) VALUES (?, 'RECARGA', ?)",
            (tarjeta["id"], importe),
        )
    return True, "OK"


def anular(codigo, notas=""):
    tarjeta = obtener(codigo)
    if not tarjeta:
        return False, "La tarjeta regalo no existe."
    db.execute(
        "UPDATE tarjetas_regalo SET estado = 'ANULADA', notas = ? WHERE id = ?",
        (notas, tarjeta["id"]),
    )
    return True, "OK"


def listar():
    """Devuelve todas las tarjetas regalo (más recientes primero)."""
    return db.query(
        "SELECT * FROM tarjetas_regalo ORDER BY id DESC"
    )


def movimientos(tarjeta_id):
    return db.query(
        "SELECT * FROM tarjetas_regalo_movimientos "
        "WHERE tarjeta_id = ? ORDER BY id DESC",
        (tarjeta_id,),
    )
