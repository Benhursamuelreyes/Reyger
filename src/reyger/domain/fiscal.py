"""Cálculos fiscales: tipos de IVA y desglose base/cuota.

Los precios de catálogo se consideran PVP con IVA incluido (uso común
en comercio minorista español). El desglose por línea es:

    base  = precio_con_iva * cantidad / (1 + tipo_iva / 100)
    cuota = total_linea - base

Los importes se calculan en **céntimos enteros** con redondeo comercial
(mitad hacia arriba): con ``float`` 0,1 + 0,2 no es exactamente 0,3 y un
redondeo podía caer al céntimo equivocado. Las ventas se guardan así en la
base de datos; :func:`desglose_linea` da el mismo resultado en euros.
"""

from decimal import ROUND_HALF_UP, Decimal

TIPOS_IVA = (21.0, 10.0, 4.0)
IVA_POR_DEFECTO = 21.0


def a_centimos(euros):
    """Convierte un importe en euros a céntimos enteros (2,675 → 268)."""
    if euros is None:
        return 0
    return int((Decimal(str(euros)) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def a_euros(centimos):
    """Convierte céntimos enteros a euros (268 → 2.68)."""
    return round((centimos or 0) / 100, 2)


def desglose_linea_cent(precio_cent, cantidad, tipo_iva=IVA_POR_DEFECTO):
    """Devuelve (total, base, cuota) de una línea, en céntimos enteros."""
    total = int(precio_cent) * int(cantidad)
    divisor = 1 + Decimal(str(tipo_iva)) / 100
    base = int((Decimal(total) / divisor).quantize(Decimal("1"), ROUND_HALF_UP))
    return total, base, total - base


def desglose_linea(precio_con_iva, cantidad, tipo_iva=IVA_POR_DEFECTO):
    """Devuelve (total, base, cuota) de una línea redondeado a céntimos."""
    return tuple(
        a_euros(c)
        for c in desglose_linea_cent(a_centimos(precio_con_iva), cantidad, tipo_iva)
    )


def desglose_total(lineas):
    """Suma el desglose de varias líneas.

    *lineas* es una secuencia de tuplas (precio_con_iva, cantidad,
    tipo_iva). Devuelve (total, base, cuota) agregados.
    """
    total = base = cuota = 0
    for precio, cantidad, tipo in lineas:
        t, b, c = desglose_linea_cent(a_centimos(precio), cantidad, tipo)
        total += t
        base += b
        cuota += c
    return a_euros(total), a_euros(base), a_euros(cuota)


def normalizar_tipo_iva(valor):
    """Convierte la entrada del usuario a un tipo válido o None."""
    try:
        tipo = float(str(valor).strip().replace(",", ".").rstrip("%"))
    except (TypeError, ValueError):
        return None
    if tipo < 0 or tipo > 100:
        return None
    return tipo
