"""Tests del campo "Porcentaje de margen / ganancia (%)" (migración 12).

Cubren las fórmulas de cálculo (precio de venta partiendo de coste y margen,
y margen partiendo de coste y precio de venta), el parseo de decimales con
coma o punto, y la persistencia de ``margen_porcentaje`` en ``inventario``.
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
    """BD temporal con esquema al día (incluye migración 12)."""
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


def _inventario_clase():
    from reyger.ui import inventario as mod_inventario
    return mod_inventario.Inventario


class TestFormulasMargen:
    def test_precio_venta_con_margen(self):
        cls = _inventario_clase()
        resultado = cls._calcular_precio_venta(10.0, 20.0)
        assert resultado == pytest.approx(12.0)

    def test_precio_venta_margen_decimal(self):
        cls = _inventario_clase()
        resultado = cls._calcular_precio_venta(50.0, 12.5)
        assert resultado == pytest.approx(56.25)

    def test_margen_desde_precio_venta(self):
        cls = _inventario_clase()
        resultado = cls._calcular_margen(10.0, 14.0)
        assert resultado == pytest.approx(40.0)

    def test_margen_cero_si_mismo_precio(self):
        cls = _inventario_clase()
        resultado = cls._calcular_margen(8.0, 8.0)
        assert resultado == pytest.approx(0.0)

    def test_margen_no_divide_por_cero(self):
        cls = _inventario_clase()
        assert cls._calcular_margen(0.0, 5.0) == 0.0

    def test_parse_float_con_coma(self):
        cls = _inventario_clase()
        assert cls._parse_float("12,50") == 12.5

    def test_parse_float_con_punto(self):
        cls = _inventario_clase()
        assert cls._parse_float("12.50") == 12.5

    def test_parse_float_invalido(self):
        cls = _inventario_clase()
        assert cls._parse_float("abc") is None


class TestPersistenciaMargen:
    def test_columna_margen_porcentaje_existe(self):
        import reyger.core.db as modulo_db
        cols = [r[1] for r in modulo_db.query("PRAGMA table_info(inventario)")]
        assert "margen_porcentaje" in cols

    def test_insertar_y_leer_margen(self):
        import reyger.core.db as modulo_db
        modulo_db.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
            " margen_porcentaje) VALUES (?, ?, ?, ?, ?, ?)",
            ("Producto M", "Prov", 12.0, 10.0, 5, 20.0),
        )
        fila = modulo_db.query_one(
            "SELECT precio, costo, margen_porcentaje FROM inventario"
            " WHERE nombre = ?",
            ("Producto M",),
        )
        assert fila is not None
        assert fila[2] == pytest.approx(20.0)

    def test_margen_por_defecto_es_null(self):
        import reyger.core.db as modulo_db
        modulo_db.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock)"
            " VALUES (?, ?, ?, ?, ?)",
            ("Producto Sin Margen", "Prov", 11.0, 10.0, 3),
        )
        fila = modulo_db.query_one(
            "SELECT margen_porcentaje FROM inventario WHERE nombre = ?",
            ("Producto Sin Margen",),
        )
        assert fila[0] is None
