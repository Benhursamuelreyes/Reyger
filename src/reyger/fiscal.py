"""Cálculos fiscales: tipos de IVA y desglose base/cuota.

Los precios de catálogo se consideran PVP con IVA incluido (uso común
en comercio minorista español). El desglose por línea es:

    base  = precio_con_iva * cantidad / (1 + tipo_iva / 100)
    cuota = total_linea - base
"""

TIPOS_IVA = (21.0, 10.0, 4.0)
IVA_POR_DEFECTO = 21.0


def desglose_linea(precio_con_iva, cantidad, tipo_iva=IVA_POR_DEFECTO):
    """Devuelve (total, base, cuota) de una línea redondeado a céntimos."""
    total = round(float(precio_con_iva) * int(cantidad), 2)
    base = round(total / (1 + float(tipo_iva) / 100.0), 2)
    cuota = round(total - base, 2)
    return total, base, cuota


def desglose_total(lineas):
    """Suma el desglose de varias líneas.

    *lineas* es una secuencia de tuplas (precio_con_iva, cantidad,
    tipo_iva). Devuelve (total, base, cuota) agregados.
    """
    total = base = cuota = 0.0
    for precio, cantidad, tipo in lineas:
        t, b, c = desglose_linea(precio, cantidad, tipo)
        total += t
        base += b
        cuota += c
    return round(total, 2), round(base, 2), round(cuota, 2)


def normalizar_tipo_iva(valor):
    """Convierte la entrada del usuario a un tipo válido o None."""
    try:
        tipo = float(str(valor).strip().replace(",", ".").rstrip("%"))
    except (TypeError, ValueError):
        return None
    if tipo < 0 or tipo > 100:
        return None
    return tipo
