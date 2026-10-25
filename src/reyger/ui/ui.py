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


def aplicar_colores_por_defecto(raiz, colores):
    """Fija en la base de opciones de Tk los colores del tema activo.

    Afecta solo a los widgets clásicos (tk.*) que no indican color propio,
    p. ej. un Label sin ``fg`` o un Entry sin ``bg``; los ttk los gestiona
    ThemedStyle. Debe llamarse antes de crear la interfaz.
    """
    texto = colores["fg_texto"]
    for clase in ("Label", "Labelframe", "Checkbutton", "Radiobutton", "Message"):
        raiz.option_add(f"*{clase}.foreground", texto)
    for clase in ("Checkbutton", "Radiobutton"):
        raiz.option_add(f"*{clase}.activeForeground", texto)
        raiz.option_add(f"*{clase}.selectColor", colores["entry_bg"])
    for clase in ("Entry", "Text", "Listbox", "Spinbox"):
        raiz.option_add(f"*{clase}.background", colores["entry_bg"])
        raiz.option_add(f"*{clase}.foreground", colores["entry_fg"])
        raiz.option_add(f"*{clase}.insertBackground", colores["entry_fg"])
    raiz.option_add("*Toplevel.background", colores["bg_principal"])
    raiz.option_add("*highlightBackground", colores["borde_foco"])


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
