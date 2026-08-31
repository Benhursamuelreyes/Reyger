"""Tests de la lógica de cierre de caja (core/cierre_caja.py).

Cubren el resumen de ventas por método de pago (efectivo neto / tarjeta),
el filtrado por rango de fechas, los movimientos manuales (ingresos /
retiros), el total esperado, el cálculo del total contado por
denominaciones y la persistencia del cierre en ``cierres_caja``.
"""

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_bd(tmp_path):
    """BD temporal con esquema al día (incluye migración 10)."""
    import reyger.core.db as modulo_db
    from reyger.core import migrations

    ruta_bd = str(tmp_path / "tienda.db")
    tmp_tmpl = str(tmp_path / "plantilla.db")
    shutil.copyfile(PLANTILLA, tmp_tmpl)
    import sqlite3
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


def _conexion():
    import reyger.core.db as modulo_db
    return modulo_db.get_connection()


def _insertar_venta(factura, subtotal, metodo, efectivo=0.0, tarjeta=0.0, fecha="2026-01-01 12:00:00"):
    import reyger.core.db as modulo_db
    modulo_db.execute(
        "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, cantidad, "
        "subtotal, metodo_pago, cantidad_efectivo, cantidad_tarjeta, fecha) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (factura, "Producto", subtotal, 1, subtotal, metodo,
         efectivo, tarjeta, fecha),
    )


def _importar():
    from reyger.core import cierre_caja as cc
    return cc


def test_resumen_efectivo_tarjeta_y_mixto():
    cc = _importar()
    # Factura 1: pura efectivo (neto 100 queda en caja)
    _insertar_venta(1, 100.0, "Efectivo")
    # Factura 2: pura tarjeta (200)
    _insertar_venta(2, 200.0, "Tarjeta")
    # Factura 3: mixta (efectivo 30 + tarjeta 20 = 50), con una segunda línea
    _insertar_venta(3, 30.0, "Mixto", efectivo=30.0, tarjeta=20.0)
    _insertar_venta(3, 20.0, "Mixto", efectivo=0.0, tarjeta=20.0)

    r = cc.resumen_ventas()
    assert r["total_ventas"] == 350.0
    assert r["efectivo_neto"] == 100.0 + 30.0  # 130
    # mezcla: 20 (L1) + 20 (L2) = 40 por tarjeta en la factura mixta, + 200 tarjeta
    assert r["tarjeta"] == 200.0 + 40.0  # 240
    assert r["num_facturas_mixtas"] == 1
    assert r["num_facturas"] == 3


def test_filtro_por_rango_de_fechas():
    cc = _importar()
    _insertar_venta(1, 100.0, "Efectivo", fecha="2026-01-10 09:00:00")
    _insertar_venta(2, 50.0, "Efectivo", fecha="2026-01-20 18:00:00")

    r = cc.resumen_ventas("2026-01-01 00:00:00", "2026-01-15 23:59:59")
    assert r["total_ventas"] == 100.0
    assert r["num_facturas"] == 1


def test_total_esperado_con_ingresos_y_retiros():
    cc = _importar()
    _insertar_venta(1, 100.0, "Efectivo")
    resumen = cc.resumen_ventas()
    ingreso, retiro = 50.0, 20.0
    esperado = cc.total_esperado(resumen, ingreso, retiro)
    assert esperado == 100.0 + 50.0 - 20.0  # 130


def test_movimientos_manuales():
    cc = _importar()
    cc.registrar_movimiento("INGRESO", 100.0, "Cambio fondo")
    cc.registrar_movimiento("RETIRO", 40.0, "Retiro parcial")
    ingreso, retiro = cc.total_movimientos()
    assert ingreso == 100.0
    assert retiro == 40.0


def test_total_contado_por_denominaciones():
    cc = _importar()
    # 1 billete de 50, 2 de 20, 1 moneda de 2 y 3 de 0.50
    conteo = {50: 1, 20: 2, 2: 1, 0.5: 3}
    assert cc.calcular_total_contado(conteo) == 50 + 40 + 2 + 1.5  # 93.5


def test_diferencia_a_favor_y_en_contra():
    cc = _importar()
    assert cc.calcular_diferencia(100.0, 80.0) == 20.0  # a favor
    assert cc.calcular_diferencia(70.0, 90.0) == -20.0  # en contra
    assert cc.calcular_diferencia(80.0, 80.0) == 0.0


def test_guardar_cierre_y_leer():
    cc = _importar()
    cierre_id = cc.guardar_cierre({
        "fecha_apertura": "2026-01-01 00:00:00",
        "fecha_cierre": "2026-01-01 18:00:00",
        "usuario": "Ana",
        "notas": "Cierre diario",
        "total_ventas": 350.0,
        "total_efectivo_esperado": 130.0,
        "total_tarjeta": 220.0,
        "num_facturas_mixtas": 1,
        "ingreso_manual": 50.0,
        "retiro_manual": 20.0,
        "total_esperado": 160.0,
        "total_contado": 165.5,
        "diferencia": 5.5,
        "desglose": {50: 3, 10: 1, 5: 1, 0.5: 1},
    })
    assert isinstance(cierre_id, int)

    fila = _conexion().execute(
        "SELECT * FROM cierres_caja WHERE id = ?", (cierre_id,)
    ).fetchone()
    assert fila["usuario"] == "Ana"
    assert fila["total_ventas"] == 350.0
    assert fila["diferencia"] == 5.5
    assert "50" in fila["desglose"]  # JSON serializado


def test_movimientos_afectan_total_esperado_integrado():
    cc = _importar()
    _insertar_venta(1, 100.0, "Efectivo")
    cc.registrar_movimiento("INGRESO", 25.0, "Aporte")
    cc.registrar_movimiento("RETIRO", 10.0, "Gasto menor")

    resumen = cc.resumen_ventas()
    ingreso, retiro = cc.total_movimientos()
    esperado = cc.total_esperado(resumen, ingreso, retiro)
    total_contado = cc.calcular_total_contado({50: 2, 20: 1, 5: 1})  # 125
    diferencia = cc.calcular_diferencia(total_contado, esperado)

    assert esperado == 100.0 + 25.0 - 10.0  # 115
    assert total_contado == 125.0
    assert diferencia == 10.0  # a favor
