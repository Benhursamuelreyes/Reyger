"""Lógica de devoluciones / rectificaciones de ventas.

Permite seleccionar una factura emitida, devolver total o parcialmente
algunos productos, reintegrar el stock en el inventario y registrar el
reembolso. El reembolso puede ser en efectivo, tarjeta o mediante la
emisión de un vale (tarjeta regalo).
"""
from datetime import datetime

from . import db
from . import tarjetas_regalo as tr


def productos_de_factura(factura):
    """Devuelve las líneas de productos de una factura (agrupadas por nombre)."""
    filas = db.query(
        "SELECT nombre_articulo AS nombre, valor_articulo AS precio, "
        "       SUM(cantidad) AS cantidad, SUM(subtotal) AS subtotal "
        "FROM ventas WHERE factura = ? "
        "GROUP BY nombre_articulo, valor_articulo ORDER BY nombre_articulo",
        (int(factura),),
    )
    # Restar lo ya devuelto en devoluciones anteriores
    devueltos = db.query(
        "SELECT dp.nombre_articulo AS nombre, SUM(dp.cantidad) AS cantidad "
        "FROM devolucion_productos dp WHERE dp.factura_original = ? "
        "GROUP BY dp.nombre_articulo",
        (int(factura),),
    )
    devueltos_map = {fila["nombre"]: int(fila["cantidad"] or 0) for fila in devueltos}

    resultado = []
    for fila in filas:
        disponible = int(fila["cantidad"] or 0) - devueltos_map.get(fila["nombre"], 0)
        precio = float(fila["precio"] or 0.0)
        resultado.append({
            "nombre": fila["nombre"],
            "precio": precio,
            "disponible": max(disponible, 0),
            "subtotal": float(fila["subtotal"] or 0.0),
        })
    return resultado


def _existe_factura(factura):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM ventas WHERE factura = ?", (int(factura),)
    )["n"] > 0


def procesar_devolucion(factura_original, lineas, metodo_reembolso="Efectivo",
                        usuario="", motivo="", notas=""):
    """Procesa una devolución y devuelve un dict con el resultado.

    *lineas* es una secuencia de ``(nombre_articulo, cantidad)``. Las
    cantidades se validan contra lo disponible (vendido menos lo ya
    devuelto). Reintegra el stock en ``inventario`` y, si el reembolso es
    por vale, crea una tarjeta regalo con el importe devuelto.
    """
    factura = int(factura_original)
    if not _existe_factura(factura):
        raise ValueError("La factura indicada no existe.")

    disponibles = {
        p["nombre"]: p["disponible"] for p in productos_de_factura(factura)
    }

    lineas_validas = []
    for nombre, cantidad in lineas:
        cantidad = int(cantidad)
        if cantidad <= 0:
            continue
        if nombre not in disponibles:
            raise ValueError(f"El producto '{nombre}' no pertenece a esta factura.")
        if cantidad > disponibles[nombre]:
            raise ValueError(
                f"La cantidad a devolver de '{nombre}' excede la disponible "
                f"({disponibles[nombre]})."
            )
        lineas_validas.append((nombre, cantidad))

    if not lineas_validas:
        raise ValueError("No hay productos válidos para devolver.")

    # P. unitario para calcular el importe devuelto (subtotal por unidad).
    precios = {
        p["nombre"]: p["precio"] for p in productos_de_factura(factura)
    }
    importe_devuelto = round(sum(precios[n] * c for n, c in lineas_validas), 2)

    ticket_regalo_id = None
    codigo_vale = None
    with db.transaccion() as conn:
        cur = conn.execute(
            "INSERT INTO devoluciones (factura_original, usuario, motivo, "
            "metodo_reembolso, importe_devuelto, notas) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (factura, usuario or "", motivo or "", metodo_reembolso,
             importe_devuelto, notas or ""),
        )
        devolucion_id = cur.lastrowid

        for nombre, cantidad in lineas_validas:
            precio = precios[nombre]
            conn.execute(
                "INSERT INTO devolucion_productos (devolucion_id, "
                "factura_original, nombre_articulo, valor_articulo, "
                "cantidad, subtotal) VALUES (?, ?, ?, ?, ?, ?)",
                (devolucion_id, factura, nombre, precio, cantidad,
                 round(precio * cantidad, 2)),
            )
            # Reintegrar stock en el inventario
            conn.execute(
                "UPDATE inventario SET stock = stock + ? WHERE nombre = ?",
                (cantidad, nombre),
            )

        if metodo_reembolso == "Vale":
            tarjeta_id, codigo_vale = tr.crear(
                importe_devuelto, notas=f"Vale por devolución de factura {factura}"
            )
            ticket_regalo_id = tarjeta_id
            conn.execute(
                "UPDATE devoluciones SET ticket_regalo_id = ? WHERE id = ?",
                (tarjeta_id, devolucion_id),
            )

    return {
        "devolucion_id": devolucion_id,
        "factura_original": factura,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "lineas": lineas_validas,
        "importe_devuelto": importe_devuelto,
        "metodo_reembolso": metodo_reembolso,
        "codigo_vale": codigo_vale,
    }


def imprimir_ticket_devolucion(resultado, empresa="Mi Empresa", ancho=42,
                               letra="muy_grande", impresora=None, logo=None,
                               negocio=None, usuario=""):
    """Imprime el ticket de rectificación/devolución en la térmica."""
    from ..hardware.impresion_termica import imprimir_ticket_devolucion as envio
    resumen = {
        "factura_original": resultado["factura_original"],
        "fecha": resultado["fecha"],
        "lineas": resultado["lineas"],
        "importe_devuelto": resultado["importe_devuelto"],
        "metodo_reembolso": resultado["metodo_reembolso"],
        "codigo_vale": resultado.get("codigo_vale"),
        "usuario": usuario,
    }
    return envio(
        resumen, empresa=empresa, ancho=ancho, letra=letra,
        impresora=impresora, logo=logo, negocio=negocio,
    )
