"""Tests de devoluciones, tarjetas regalo y tickets regalo (migración 11).

Cubren: creación de tarjetas regalo, consulta de saldo, aplicación como
método de pago (total y parcial), recarga, devoluciones con reembolso en
efectivo/tarjeta/vale, reintegro de stock, rechazo de sobre-devoluciones y
validez del código de barras Code128 y del ticket regalo.
"""

import os
import shutil
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_bd(tmp_path):
    """BD temporal con esquema al día (incluye migración 11)."""
    import reyger.core.db as modulo_db
    from reyger.core import migrations

    ruta_bd = str(tmp_path / "tienda.db")
    tmp_tmpl = str(tmp_path / "plantilla.db")
    shutil.copyfile(PLANTILLA, tmp_tmpl)
    conn = sqlite3.connect(tmp_tmpl)
    migrations.run_migrations(conn)
    conn.close()
    shutil.copyfile(tmp_tmpl, ruta_bd)

    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original


def _insertar_producto(nombre, precio, stock):
    import reyger.core.db as modulo_db
    modulo_db.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        (nombre, "Proveedor", precio, precio * 0.5, stock),
    )


def _insertar_venta(factura, nombre, precio, cantidad):
    import reyger.core.db as modulo_db
    subtotal = round(precio * cantidad, 2)
    base = subtotal
    cuota = round(subtotal * 0.21, 2)
    modulo_db.execute(
        "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, cantidad, "
        "subtotal, metodo_pago, cantidad_efectivo, cantidad_tarjeta, tipo_iva, "
        "cuota_iva, base_imponible) VALUES (?, ?, ?, ?, ?, 'Efectivo', 0, 0, ?, ?, ?)",
        (factura, nombre, precio, cantidad, subtotal, 21, cuota, base),
    )


def _tr():
    from reyger.core import tarjetas_regalo as tr
    return tr


def _dev():
    from reyger.core import devoluciones as dev
    return dev


def test_crear_tarjeta_y_saldo():
    tr = _tr()
    tarjeta_id, codigo = tr.crear(50.0)
    assert codigo
    assert tr.saldo(codigo) == 50.0
    assert tr.obtener(codigo)["estado"] == "ACTIVA"


def test_aplicar_pago_total():
    tr = _tr()
    _, codigo = tr.crear(100.0)
    ok, monto, restante, msg = tr.aplicar_pago(codigo, 40.0)
    assert ok and monto == 40.0 and restante == 0.0
    assert tr.saldo(codigo) == 60.0


def test_aplicar_pago_parcial_restante():
    tr = _tr()
    _, codigo = tr.crear(30.0)
    ok, monto, restante, msg = tr.aplicar_pago(codigo, 100.0)
    assert ok and monto == 30.0 and restante == 70.0
    assert tr.saldo(codigo) == 0.0


def test_tarjeta_no_existe_y_anulada():
    tr = _tr()
    ok, monto, restante, msg = tr.aplicar_pago("NOEXISTE", 10.0)
    assert not ok
    _, codigo = tr.crear(20.0)
    tr.anular(codigo)
    ok, monto, restante, msg = tr.aplicar_pago(codigo, 5.0)
    assert not ok


def test_recargar():
    tr = _tr()
    _, codigo = tr.crear(10.0)
    ok, msg = tr.recargar(codigo, 25.0)
    assert ok
    assert tr.saldo(codigo) == 35.0


def test_productos_de_factura_y_disponible():
    _insertar_producto("Teclado", 20.0, 10)
    _insertar_venta(500, "Teclado", 20.0, 3)
    dev = _dev()
    prods = dev.productos_de_factura(500)
    assert prods[0]["nombre"] == "Teclado"
    assert prods[0]["disponible"] == 3


def test_devolucion_reembolsa_stock():
    _insertar_producto("Raton", 12.0, 8)
    _insertar_venta(501, "Raton", 12.0, 2)
    dev = _dev()
    resultado = dev.procesar_devolucion(
        501, [("Raton", 1)], metodo_reembolso="Efectivo", usuario="Ana"
    )
    assert resultado["importe_devuelto"] == 12.0
    import reyger.core.db as modulo_db
    stock = modulo_db.query_one(
        "SELECT stock FROM inventario WHERE nombre = ?", ("Raton",)
    )["stock"]
    assert stock == 9


def test_devolucion_vale_crea_tarjeta():
    _insertar_producto("Monitor", 150.0, 4)
    _insertar_venta(502, "Monitor", 150.0, 2)
    dev = _dev()
    tr = _tr()
    resultado = dev.procesar_devolucion(
        502, [("Monitor", 2)], metodo_reembolso="Vale", usuario="Ana"
    )
    assert resultado["codigo_vale"]
    assert tr.saldo(resultado["codigo_vale"]) == 300.0


def test_sobre_devolucion_rechazada():
    _insertar_producto("Webcam", 30.0, 5)
    _insertar_venta(503, "Webcam", 30.0, 3)
    dev = _dev()
    with pytest.raises(ValueError):
        dev.procesar_devolucion(503, [("Webcam", 99)])


def test_no_devuelve_ya_devuelto():
    _insertar_producto("Mic", 25.0, 10)
    _insertar_venta(504, "Mic", 25.0, 4)
    dev = _dev()
    dev.procesar_devolucion(504, [("Mic", 3)])
    # Solo queda 1 disponible
    prods = dev.productos_de_factura(504)
    assert prods[0]["disponible"] == 1


def test_devolucion_factura_inexistente():
    dev = _dev()
    with pytest.raises(ValueError):
        dev.procesar_devolucion(99999, [("Nada", 1)])


def test_code128_checksum():
    from reyger.hardware.codigos import _codigo_b128
    # 'A': 104 + 33*1 = 137 -> 137%103 = 34
    assert _codigo_b128("A") == [104, 33, 34, 106]
    # 'AB': 104 + 33*1 + 34*2 = 205 -> 205%103 = 102
    assert _codigo_b128("AB") == [104, 33, 34, 102, 106]


def test_code128_pil_y_qr():
    from reyger.hardware.codigos import generar_barcode_pil, generar_qr_pil
    b = generar_barcode_pil("TR-ABC123")
    assert b.mode in ("L", "1")
    assert b.width > 0 and b.height > 0
    q = generar_qr_pil("TR-ABC123")
    assert q.width > 0


def test_construir_ticket_regalo_sin_precios():
    from reyger.hardware import impresion_termica as it
    datos = it.construir_ticket_regalo(
        555, "01/09/2026 12:00",
        [("Producto", 10.0, 2, 20.0), ("Otro", 5.0, 1, 5.0)],
        "TR-555-ABC",
        ancho=42, letra="muy_grande",
    )
    assert isinstance(datos, bytes) and len(datos) > 0
    # No debe contener el total ni los subtotales impresos
    texto = datos.decode("latin-1", errors="replace")
    assert "TICKET REGALO" in texto
    assert "Cantidad: 2" in texto
    assert "10.00" not in texto


def test_construir_ticket_devolucion():
    from reyger.hardware import impresion_termica as it
    resumen = {
        "factura_original": 501,
        "fecha": "01/09/2026",
        "lineas": [("Raton", 1)],
        "importe_devuelto": 12.0,
        "metodo_reembolso": "Vale",
        "codigo_vale": "TR-VALE1",
        "usuario": "Ana",
    }
    datos = it.construir_ticket_devolucion(resumen, ancho=42)
    assert isinstance(datos, bytes) and len(datos) > 0
    texto = datos.decode("latin-1", errors="replace")
    assert "DEVOLUCI" in texto
    assert "Factura original: 501" in texto
