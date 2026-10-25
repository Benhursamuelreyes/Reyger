"""Catálogo de productos y proveedores, sin interfaz gráfica.

``ui.inventario`` recoge los datos del formulario y llama aquí; las
consultas, la validación y los cálculos de margen viven en este módulo para
poder probarlos sin abrir ventanas.
"""

from ..core import db
from ..ui import categorias


def parse_float(texto):
    """Convierte ``"12,50"`` o ``"12.50"`` a float; ``None`` si no es número."""
    try:
        return float(str(texto).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def calcular_precio_venta(costo, margen):
    """Precio de venta a partir del coste y el margen (%):
    ``costo * (1 + margen / 100)``."""
    return costo * (1 + margen / 100)


def calcular_margen(costo, precio_venta):
    """Margen (%) a partir del coste y el precio de venta:
    ``((venta - costo) / costo) * 100``."""
    if not costo:
        return 0.0
    return ((precio_venta - costo) / costo) * 100


def validar_producto(nombre, proveedor, precio, costo, stock):
    """Valida los campos del producto. Devuelve ``(ok, mensaje)``.

    Un precio, coste o stock negativos no se aceptan: el coste negativo
    inflaba el margen y el precio negativo llegaba a
    :func:`fiscal.desglose_linea` como base imponible negativa en una venta.
    """
    if not (nombre and proveedor and precio and costo and stock):
        return False, "Rellene todos los campos correctamente"
    try:
        precio_num = float(precio)
        costo_num = float(costo)
        stock_num = int(stock)
    except (TypeError, ValueError):
        return False, "Precio, coste y stock deben ser numéricos"
    if precio_num < 0:
        return False, "El precio de venta no puede ser negativo"
    if costo_num < 0:
        return False, "El coste no puede ser negativo"
    if stock_num < 0:
        return False, "El stock no puede ser negativo"
    return True, ""


def estado_stock(stock, umbral):
    """``"agotado"`` (0 o menos), ``"bajo"`` (hasta *umbral*) o ``None``."""
    try:
        stock = int(stock)
    except (TypeError, ValueError):
        return None
    if stock <= 0:
        return "agotado"
    if stock <= umbral:
        return "bajo"
    return None


# ---------------------------------------------------------------- productos
def listar_productos(categoria=None):
    """Filas ``(id, nombre, proveedor, precio, costo, stock, tipo_iva,
    categoria)``, más recientes primero, opcionalmente de una categoría.

    Columnas explícitas: ``i.*`` es frágil porque ALTER TABLE añade las
    columnas nuevas al final y desplaza los índices posicionales.
    """
    consulta = (
        "SELECT i.id, i.nombre, i.proveedor, i.precio, i.costo,"
        " i.stock, i.tipo_iva, c.nombre FROM inventario i "
        "LEFT JOIN categorias c ON c.id = i.categoria_id "
    )
    if categoria:
        return db.query(consulta + "WHERE c.nombre = ? ORDER BY i.id DESC", (categoria,))
    return db.query(consulta + "ORDER BY i.id DESC")


def obtener_producto(id_producto):
    """Datos editables del producto o ``None`` si no existe."""
    return db.query_one(
        "SELECT precio, costo, tipo_iva, categoria_id, codigo_barras,"
        " margen_porcentaje FROM inventario WHERE id = ?",
        (id_producto,),
    )


def codigo_en_uso(codigo, excluir_id=None):
    """``True`` si *codigo* ya está asignado a otro producto."""
    if excluir_id is None:
        fila = db.query_one("SELECT id FROM inventario WHERE codigo_barras = ?", (codigo,))
    else:
        fila = db.query_one(
            "SELECT id FROM inventario WHERE codigo_barras = ? AND id != ?",
            (codigo, excluir_id),
        )
    return fila is not None


def _id_categoria(nombre):
    fila = db.query_one(
        "SELECT id FROM categorias WHERE nombre = ?", (nombre or categorias.GENERAL,)
    )
    return fila["id"] if fila else None


def nombre_categoria(categoria_id):
    """Nombre de la categoría *categoria_id* o ``None``."""
    if not categoria_id:
        return None
    fila = db.query_one("SELECT nombre FROM categorias WHERE id = ?", (categoria_id,))
    return fila["nombre"] if fila else None


def crear_producto(nombre, proveedor, precio, costo, stock, tipo_iva,
                   categoria=None, codigo=None, margen=0.0):
    """Da de alta un producto y devuelve su id.

    El proveedor y la categoría se enlazan por nombre; si no existen, el
    enlace queda vacío (el nombre del proveedor se guarda igualmente).
    """
    fila_proveedor = db.query_one("SELECT id FROM proveedores WHERE nombre = ?", (proveedor,))
    return db.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo,"
        " stock, proveedor_id, tipo_iva, categoria_id, codigo_barras,"
        " margen_porcentaje) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            nombre, proveedor, precio, costo, stock,
            fila_proveedor["id"] if fila_proveedor else None,
            tipo_iva, _id_categoria(categoria), codigo or None, margen,
        ),
    )


def actualizar_producto(id_producto, nombre, proveedor, precio, costo, stock,
                        tipo_iva, categoria=None, codigo=None, margen=0.0):
    db.execute(
        "UPDATE inventario SET nombre=?, proveedor=?, precio=?, costo=?,"
        " stock=?, tipo_iva=?, categoria_id=?, codigo_barras=?,"
        " margen_porcentaje=? WHERE id=?",
        (
            nombre, proveedor, precio, costo, stock, tipo_iva,
            _id_categoria(categoria), codigo or None, margen, id_producto,
        ),
    )


def eliminar_producto(id_producto):
    db.execute("DELETE FROM inventario WHERE id = ?", (id_producto,))


# -------------------------------------------------------------- proveedores
def nombres_proveedores():
    return [fila["nombre"] for fila in db.query("SELECT nombre FROM proveedores ORDER BY nombre")]


def crear_proveedor(nombre, cif="", contacto="", telefono="", email=""):
    return db.execute(
        "INSERT INTO proveedores (nombre, cif, contacto, telefono, email)"
        " VALUES (?,?,?,?,?)",
        (nombre, cif, contacto, telefono, email),
    )
