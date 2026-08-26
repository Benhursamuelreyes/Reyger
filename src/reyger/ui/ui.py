"""Constantes y utilidades de interfaz gráfica.

Centraliza los tamaños por defecto de las ventanas: todas las pantallas
de Reyger son grandes y redimensionables, con un tamaño mínimo por
debajo del cual el diseño no se degrada.
"""

# Ventana principal (menú)
GEOMETRIA_PRINCIPAL = "1280x800"
MINIMO_PRINCIPAL = (1024, 640)

# Módulos que se abren como Toplevel (ventas, inventario, clientes, ...)
GEOMETRIA_MODULO = "1280x800"
MINIMO_MODULO = (1100, 700)


def configurar_ventana(ventana, titulo=None, geometria=GEOMETRIA_MODULO,
                       minimo=MINIMO_MODULO, resizable=(True, True)):
    """Aplica a *ventana* el tamaño, redimensionado y mínimo estándar."""
    if titulo:
        ventana.title(titulo)
    ventana.geometry(geometria)
    ventana.resizable(*resizable)
    if minimo:
        ventana.minsize(*minimo)
    return ventana
