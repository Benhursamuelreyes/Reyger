"""Lógica de cierre de caja (arqueo).

Calcula el resumen de ventas por método de pago de un período, el total
esperado en caja (neto de efectivo + movimientos manuales), el total
contado a partir del desglose por denominaciones y el descuadre resultante.
También persiste el registro del arqueo en :table:`cierres_caja`.
"""
import json

from . import db

# Denominaciones típicas en euros (billetes y monedas), de mayor a menor.
DENOMINACIONES_EUR = [
    500, 200, 100, 50, 20, 10, 5, 2, 1,
    0.50, 0.20, 0.10, 0.05, 0.02, 0.01,
]


def denominaciones():
    """Devuelve las denominaciones para el conteo de efectivo."""
    return list(DENOMINACIONES_EUR)


def _filtro_rango(desde, hasta):
    condicion = []
    parametros = []
    if desde:
        condicion.append("fecha >= ?")
        parametros.append(desde)
    if hasta:
        condicion.append("fecha <= ?")
        parametros.append(hasta)
    if condicion:
        return "AND " + " AND ".join(condicion), parametros
    return "", parametros


def resumen_ventas(desde=None, hasta=None):
    """Devuelve el resumen de ventas del período.

    ``desde`` y ``hasta`` son strings ISO ``YYYY-MM-DD HH:MM:SS`` (la
    columna ``fecha`` de ``ventas`` usa SQLite ``CURRENT_TIMESTAMP``). Si
    son ``None`` se incluyen todas las ventas.

    El efectivo esperado es el *neto* real que queda en caja:
      - facturas pagadas solo en efectivo → suma de su subtotal.
      - facturas mixtas → lo abonado en efectivo (``cantidad_efectivo``).
    La tarjeta de la misma manera para la parte de tarjeta.
    """
    donde, parametros = _filtro_rango(desde, hasta)
    filas = db.query(
        "SELECT factura, metodo_pago, "
        "       SUM(subtotal) AS total_factura, "
        "       SUM(cantidad_efectivo) AS efectivo, "
        "       SUM(cantidad_tarjeta) AS tarjeta "
        "FROM ventas "
        f"WHERE 1=1 {donde} "
        "GROUP BY factura, metodo_pago",
        parametros,
    )

    total_ventas = 0.0
    efectivo = 0.0
    tarjeta = 0.0
    num_mixtas = 0
    num_facturas = 0
    facturas_vistas = set()

    for fila in filas:
        metodo = (fila["metodo_pago"] or "Efectivo").strip()
        total_factura = fila["total_factura"] or 0.0
        total_ventas += total_factura
        if fila["factura"] not in facturas_vistas:
            facturas_vistas.add(fila["factura"])
            num_facturas += 1
        if metodo == "Tarjeta":
            tarjeta += total_factura
        elif metodo == "Mixto":
            num_mixtas += 1
            efectivo += fila["efectivo"] or 0.0
            tarjeta += fila["tarjeta"] or 0.0
        else:  # Efectivo (u otro) → neto en caja
            efectivo += total_factura

    return {
        "total_ventas": round(total_ventas, 2),
        "efectivo_neto": round(efectivo, 2),
        "tarjeta": round(tarjeta, 2),
        "num_facturas_mixtas": int(num_mixtas),
        "num_facturas": int(num_facturas),
    }


def total_movimientos(desde=None, hasta=None):
    """Suma de ingresos/retiros manuales del período.

    Devuelve ``(ingreso, retiro)``. Un retiro es un movimiento que resta
    efectivo de la caja física.
    """
    donde, parametros = _filtro_rango(desde, hasta)
    filas = db.query(
        "SELECT tipo, SUM(importe) AS total FROM movimientos_caja "
        f"WHERE 1=1 {donde} GROUP BY tipo",
        parametros,
    )
    ingreso = 0.0
    retiro = 0.0
    for fila in filas:
        if fila["tipo"] == "INGRESO":
            ingreso += fila["total"] or 0.0
        elif fila["tipo"] == "RETIRO":
            retiro += fila["total"] or 0.0
    return round(ingreso, 2), round(retiro, 2)


def total_esperado(resumen, ingreso=0.0, retiro=0.0):
    """Efectivo físico esperado = neto en efectivo + ingresos − retiros.

    La tarjeta no queda en la caja física, por lo que no forma parte del
    total contado, aunque sí se informa en el ticket.
    """
    return round(resumen["efectivo_neto"] + ingreso - retiro, 2)


def calcular_total_contado(conteo):
    """Suma el efectivo real a partir de un dict {denominación: unidades}."""
    total = 0.0
    for denominacion, unidades in (conteo or {}).items():
        try:
            total += float(denominacion) * int(unidades)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def calcular_diferencia(total_contado, esperado):
    """Descuadre: a favor si positivo, en contra si negativo."""
    return round(total_contado - esperado, 2)


def registrar_movimiento(tipo, importe, concepto=""):
    """Registra un ingreso o retiro manual de caja. Devuelve el id."""
    if tipo not in ("INGRESO", "RETIRO"):
        raise ValueError("tipo debe ser 'INGRESO' o 'RETIRO'")
    return db.execute(
        "INSERT INTO movimientos_caja (tipo, importe, concepto) "
        "VALUES (?, ?, ?)",
        (tipo, float(importe), concepto or ""),
    )


def guardar_cierre(datos):
    """Persiste el registro del arqueo en ``cierres_caja``.

    ``datos`` debe incluir: fecha_apertura, fecha_cierre, usuario, notas y
    los campos numéricos del resumen (ver columnas de la tabla). Retorna el
    id insertado.
    """
    desglose = datos.get("desglose") or {}
    if isinstance(desglose, dict):
        desglose = json.dumps(desglose, ensure_ascii=False)

    with db.transaccion() as conn:
        cur = conn.execute(
            "INSERT INTO cierres_caja ("
            "  fecha_apertura, fecha_cierre, usuario, notas, "
            "  total_ventas, total_efectivo_esperado, total_tarjeta, "
            "  num_facturas_mixtas, ingreso_manual, retiro_manual, "
            "  total_esperado, total_contado, diferencia, desglose"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datos.get("fecha_apertura"),
                datos.get("fecha_cierre"),
                datos.get("usuario"),
                datos.get("notas"),
                datos.get("total_ventas", 0),
                datos.get("total_efectivo_esperado", 0),
                datos.get("total_tarjeta", 0),
                datos.get("num_facturas_mixtas", 0),
                datos.get("ingreso_manual", 0),
                datos.get("retiro_manual", 0),
                datos.get("total_esperado", 0),
                datos.get("total_contado", 0),
                datos.get("diferencia", 0),
                desglose,
            ),
        )
        return cur.lastrowid
