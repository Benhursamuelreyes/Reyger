"""Tests de ``domain.ventas``: cobro, borradores y documentos sin interfaz.

Incluye las regresiones de dos fallos de la 1.1.1:

* «Emitir factura (desde borrador)» fallaba siempre con
  ``no such column: ultulo_numero`` (errata en el UPSERT del contador).
* «Reimprimir documento» imprimía solo la línea seleccionada del historial
  en lugar del documento completo.
"""

import os
import shutil
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import reyger.core.db as modulo_db
from reyger.core import migrations
from reyger.domain import ventas as dv

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def bd(tmp_path, monkeypatch):
    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    conn = sqlite3.connect(ruta)
    migrations.run_migrations(conn)
    conn.executemany(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
        " VALUES (?, 'Prov', ?, 1.0, 10, ?)",
        [("Café", 2.20, 10), ("Libro", 12.10, 4)],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(modulo_db, "get_db_path", lambda: ruta)
    modulo_db.close()
    yield ruta
    modulo_db.close()


def _stock(nombre):
    return modulo_db.query_one(
        "SELECT stock FROM inventario WHERE nombre = ?", (nombre,)
    )["stock"]


def _id(nombre):
    return modulo_db.query_one(
        "SELECT id FROM inventario WHERE nombre = ?", (nombre,)
    )["id"]


def _carrito():
    return [
        dv.LineaVenta("Café", 2.20, 2, 10.0, _id("Café")),
        dv.LineaVenta("Libro", 12.10, 1, 4.0, _id("Libro")),
    ]


def _contador(tipo):
    fila = modulo_db.query_one(
        "SELECT MAX(ultimo_numero) AS n FROM contadores_documentos WHERE tipo = ?",
        (tipo,),
    )
    return fila["n"]


# --------------------------------------------------------------- validar
@pytest.mark.parametrize("metodo, efectivo, tarjeta, ok", [
    ("Efectivo", 10, 0, True),
    ("Efectivo", 9.99, 0, False),
    ("Tarjeta", 0, 10, True),
    ("Tarjeta", 0, 5, False),
    ("Mixto", 4, 6, True),
    ("Mixto", 4, 5, False),
])
def test_validar_pago(metodo, efectivo, tarjeta, ok):
    assert (dv.validar_pago(metodo, efectivo, tarjeta, 10) is None) is ok


# ----------------------------------------------------------- registrar
def test_registrar_venta_guarda_lineas_stock_y_contador():
    doc = dv.registrar_venta(_carrito(), "ticket", "Efectivo", 20.0, 0.0)

    assert doc.numero.endswith(f"{doc.correlativo:04d}")
    assert doc.total == pytest.approx(2.20 * 2 + 12.10)
    assert doc.base + doc.cuota == pytest.approx(doc.total)
    filas = modulo_db.query(
        "SELECT nombre_articulo, numero_ticket, estado, fecha FROM ventas "
        "WHERE factura = ?", (doc.numero,),
    )
    assert [f["nombre_articulo"] for f in filas] == ["Café", "Libro"]
    assert all(f["numero_ticket"] == doc.numero for f in filas)
    assert all(f["estado"] == "emitido" for f in filas)
    assert all(f["fecha"] for f in filas)  # DEFAULT CURRENT_TIMESTAMP
    assert _stock("Café") == 8 and _stock("Libro") == 9
    assert _contador("ticket") == doc.correlativo


def test_numeracion_avanza_entre_ventas():
    primero = dv.registrar_venta(_carrito(), "factura", "Tarjeta", 0.0, 30.0)
    segundo = dv.registrar_venta(_carrito(), "factura", "Tarjeta", 0.0, 30.0)
    assert segundo.correlativo == primero.correlativo + 1


def test_producto_borrado_no_registra_nada():
    lineas = _carrito() + [dv.LineaVenta("Fantasma", 1.0, 1, 21.0)]
    antes = _contador("ticket")
    with pytest.raises(LookupError, match="Fantasma"):
        dv.registrar_venta(lineas, "ticket", "Efectivo", 100.0)
    assert modulo_db.query_one("SELECT COUNT(*) AS n FROM ventas")["n"] == 0
    assert _stock("Café") == 10
    assert _contador("ticket") == antes


# ------------------------------------------------------------ borrador
def test_borrador_no_descuenta_stock_ni_numera():
    doc = dv.guardar_borrador(_carrito(), None, "25/10/2026 10:00")
    assert doc.numero.startswith("BORRADOR-")
    assert _stock("Café") == 10
    filas = modulo_db.query(
        "SELECT estado, fecha FROM ventas WHERE factura = ?", (doc.numero,)
    )
    assert [f["estado"] for f in filas] == ["borrador", "borrador"]
    # La fecha se guarda en hora local ISO, como el resto de documentos.
    assert filas[0]["fecha"] == "2026-10-25 10:00:00"


def test_emitir_borrador_emite_todas_las_lineas():
    """Regresión: fallaba siempre por la errata ``ultulo_numero``."""
    borrador = dv.guardar_borrador(_carrito(), None, "25/10/2026 10:00")
    doc = dv.emitir_borrador(borrador.numero)

    assert doc is not None
    assert len(doc.productos) == 2
    assert doc.total == pytest.approx(2.20 * 2 + 12.10)
    assert _stock("Café") == 8 and _stock("Libro") == 9
    assert _contador("factura") == doc.correlativo
    pendientes = modulo_db.query_one(
        "SELECT COUNT(*) AS n FROM ventas WHERE estado = 'borrador'"
    )["n"]
    assert pendientes == 0


def test_emitir_segundo_borrador_con_contador_existente():
    """El UPSERT con fila ya existente (rama ON CONFLICT) también funciona."""
    dv.registrar_venta(_carrito(), "factura", "Efectivo", 50.0)
    borrador = dv.guardar_borrador(_carrito(), None, "25/10/2026 10:00")
    doc = dv.emitir_borrador(borrador.numero)
    assert _contador("factura") == doc.correlativo


def test_emitir_borrador_ya_emitido_devuelve_none():
    borrador = dv.guardar_borrador(_carrito(), None, "25/10/2026 10:00")
    dv.emitir_borrador(borrador.numero)
    assert dv.emitir_borrador(borrador.numero) is None


# ---------------------------------------------------------- reimprimir
def test_documento_de_linea_devuelve_el_documento_completo():
    """Regresión: la reimpresión solo incluía la línea seleccionada."""
    doc = dv.registrar_venta(_carrito(), "ticket", "Mixto", 5.0, 20.0)
    id_segunda_linea = modulo_db.query(
        "SELECT id FROM ventas WHERE factura = ? ORDER BY id", (doc.numero,)
    )[1]["id"]

    leido = dv.documento_de_linea(id_segunda_linea)
    assert leido.numero == doc.numero
    assert [p[0] for p in leido.productos] == ["Café", "Libro"]
    assert leido.total == pytest.approx(doc.total)
    assert leido.metodo_pago == "Mixto"


def test_documento_de_linea_inexistente():
    assert dv.documento_de_linea(999) is None
