"""Gestion de categorias de productos (frutas, carnes, informatica...).

Cada producto del inventario pertenece a una categoria. La categoria
``General`` existe siempre y actua como destino de los productos sin
agrupar; no se puede renombrar ni eliminar.
"""

from .db import execute, query, query_one

GENERAL = "General"


def id_general():
    """Devuelve el id de la categoria General (la crea si falta)."""
    fila = query_one("SELECT id FROM categorias WHERE nombre = ?", (GENERAL,))
    if fila:
        return fila["id"]
    return execute("INSERT INTO categorias (nombre) VALUES (?)", (GENERAL,))


def listar():
    """Devuelve [(id, nombre)] ordenado alfabeticamente, General primero."""
    filas = query("SELECT id, nombre FROM categorias ORDER BY nombre")
    general = [tuple(f) for f in filas if f["nombre"] == GENERAL]
    resto = [tuple(f) for f in filas if f["nombre"] != GENERAL]
    return general + resto


def nombres():
    """Devuelve la lista de nombres de categoria (General primero)."""
    return [nombre for _, nombre in listar()]


def crear(nombre):
    """Crea una categoria nueva. Devuelve su id o None si ya existia."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la categoria no puede estar vacio")
    if query_one("SELECT id FROM categorias WHERE nombre = ?", (nombre,)):
        return None
    return execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))


def renombrar(categoria_id, nombre_nuevo):
    """Renombra una categoria. False si el nombre nuevo ya existe."""
    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_nuevo:
        raise ValueError("El nombre de la categoria no puede estar vacio")
    fila = query_one("SELECT nombre FROM categorias WHERE id = ?", (categoria_id,))
    if not fila:
        return False
    if fila["nombre"] == GENERAL:
        raise ValueError("La categoria General no puede renombrarse")
    if query_one(
        "SELECT id FROM categorias WHERE nombre = ? AND id != ?",
        (nombre_nuevo, categoria_id),
    ):
        return False
    execute(
        "UPDATE categorias SET nombre = ? WHERE id = ?",
        (nombre_nuevo, categoria_id),
    )
    return True


def eliminar(categoria_id):
    """Elimina una categoria y reagrupa sus productos en General.

    Devuelve False si la categoria no existe o es la propia General.
    """
    fila = query_one("SELECT nombre FROM categorias WHERE id = ?", (categoria_id,))
    if not fila or fila["nombre"] == GENERAL:
        return False
    general = id_general()
    execute(
        "UPDATE inventario SET categoria_id = ? WHERE categoria_id = ?",
        (general, categoria_id),
    )
    execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
    return True


def productos_por_categoria():
    """Mapa {categoria_nombre: [nombres_de_producto]} para la pantalla de ventas."""
    filas = query(
        """
        SELECT COALESCE(c.nombre, ?) AS categoria, i.nombre AS producto
        FROM inventario i
        LEFT JOIN categorias c ON c.id = i.categoria_id
        ORDER BY categoria, i.nombre
        """,
        (GENERAL,),
    )
    mapa = {}
    for fila in filas:
        mapa.setdefault(fila["categoria"], []).append(fila["producto"])
    return mapa


def categoria_de_producto(nombre_producto):
    """Nombre de la categoria de un producto (General si no tiene)."""
    fila = query_one(
        """
        SELECT COALESCE(c.nombre, ?) AS categoria
        FROM inventario i
        LEFT JOIN categorias c ON c.id = i.categoria_id
        WHERE i.nombre = ?
        """,
        (GENERAL, nombre_producto),
    )
    return fila["categoria"] if fila else None
