"""Tests de ``domain.inventario`` y de las consultas VeriFactu de Ajustes,
ejecutados sin interfaz gráfica."""

import csv
import os
import shutil
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import reyger.core.db as modulo_db
from reyger.core import migrations
from reyger.domain import inventario as dominio

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def bd(tmp_path, monkeypatch):
    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    conn = sqlite3.connect(ruta)
    migrations.run_migrations(conn)
    conn.execute("INSERT INTO categorias (nombre) VALUES ('Bebidas')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(modulo_db, "get_db_path", lambda: ruta)
    modulo_db.close()
    yield ruta
    modulo_db.close()


# ------------------------------------------------------------- cálculos
def test_calculos_de_margen():
    assert dominio.calcular_precio_venta(10.0, 20.0) == pytest.approx(12.0)
    assert dominio.calcular_margen(10.0, 14.0) == pytest.approx(40.0)
    assert dominio.calcular_margen(0.0, 5.0) == 0.0
    assert dominio.parse_float("12,50") == 12.5
    assert dominio.parse_float("abc") is None


@pytest.mark.parametrize("campos, ok", [
    (("Café", "Prov", "2.2", "1", "5"), True),
    (("", "Prov", "2.2", "1", "5"), False),
    (("Café", "Prov", "-1", "1", "5"), False),
    (("Café", "Prov", "2.2", "-1", "5"), False),
    (("Café", "Prov", "2.2", "1", "-5"), False),
    (("Café", "Prov", "x", "1", "5"), False),
])
def test_validar_producto(campos, ok):
    assert dominio.validar_producto(*campos)[0] is ok


# ------------------------------------------------------------ productos
def test_crear_enlaza_proveedor_y_categoria():
    id_prov = dominio.crear_proveedor("Tostador", "B123")
    id_prod = dominio.crear_producto(
        "Café", "Tostador", 2.2, 1.0, 5, 10.0, "Bebidas", "8400000000017", 120.0
    )
    fila = modulo_db.query_one("SELECT * FROM inventario WHERE id = ?", (id_prod,))
    assert fila["proveedor_id"] == id_prov
    assert dominio.nombre_categoria(fila["categoria_id"]) == "Bebidas"
    assert fila["codigo_barras"] == "8400000000017"
    assert dominio.nombres_proveedores() == ["Tostador"]


def test_categoria_vacia_va_a_general():
    id_prod = dominio.crear_producto("Té", "", 1.5, 0.5, 3, 10.0, "")
    fila = dominio.obtener_producto(id_prod)
    assert dominio.nombre_categoria(fila["categoria_id"]) == "General"
    assert fila["codigo_barras"] is None


def test_codigo_en_uso_excluye_el_propio_producto():
    id_prod = dominio.crear_producto("Café", "", 2.2, 1, 5, 10.0, codigo="123")
    assert dominio.codigo_en_uso("123")
    assert not dominio.codigo_en_uso("123", excluir_id=id_prod)
    assert not dominio.codigo_en_uso("999")


def test_listar_filtra_por_categoria_y_ordena_recientes_primero():
    dominio.crear_producto("Café", "", 2.2, 1, 5, 10.0, "Bebidas")
    dominio.crear_producto("Pan", "", 1.0, 0.4, 9, 4.0)
    assert [f[1] for f in dominio.listar_productos()] == ["Pan", "Café"]
    assert [f[1] for f in dominio.listar_productos("Bebidas")] == ["Café"]


def test_actualizar_y_eliminar():
    id_prod = dominio.crear_producto("Café", "", 2.2, 1, 5, 10.0)
    dominio.actualizar_producto(id_prod, "Café molido", "", 3.0, 1.2, 7, 10.0, "Bebidas", "77", 150.0)
    fila = modulo_db.query_one("SELECT * FROM inventario WHERE id = ?", (id_prod,))
    assert (fila["nombre"], fila["precio"], fila["stock"], fila["codigo_barras"]) == (
        "Café molido", 3.0, 7, "77"
    )
    dominio.eliminar_producto(id_prod)
    assert dominio.obtener_producto(id_prod) is None


# ------------------------------------------------------------ VeriFactu
def _factura(numero, estado, orden):
    modulo_db.execute(
        "INSERT INTO facturas_verifactu (numero_factura, fecha, nif_emisor,"
        " nif_receptor, nombre_receptor, base_imponible, tipo_iva, total,"
        " total_iva, huella, numero_ord, estado_envio) VALUES (?, '2026-10-25',"
        " 'B1', '', 'Cliente', 10.0, 21, 12.1, 2.1, ?, ?, ?)",
        (numero, f"h{orden}", orden, estado),
    )


def test_contar_por_estado():
    from reyger.domain.facturas_verifactu import contar_por_estado

    assert contar_por_estado() == {"pendiente": 0, "enviado": 0, "error": 0}
    _factura("F-1", "pendiente", 1)
    _factura("F-2", "pendiente", 2)
    _factura("F-3", "error", 3)
    assert contar_por_estado() == {"pendiente": 2, "enviado": 0, "error": 1}


def test_exportar_csv_verificacion_en_orden_de_cadena(tmp_path):
    from reyger.domain.verifactu_xml import exportar_csv_verificacion

    _factura("F-2", "enviado", 2)
    _factura("F-1", "pendiente", 1)
    ruta = tmp_path / "cadena.csv"
    assert exportar_csv_verificacion(str(ruta)) == 2
    with open(ruta, encoding="utf-8") as f:
        filas = list(csv.reader(f))
    assert filas[0][:5] == ["numero_factura", "fecha", "nif_emisor", "cuota_iva", "importe_total"]
    assert [fila[0] for fila in filas[1:]] == ["F-1", "F-2"]
