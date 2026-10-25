"""Tests de la migración 14: documentos y líneas en céntimos.

Cubren la conversión desde la tabla ``ventas`` antigua (totales, importes
entregados, fechas, enlaces a productos y clientes, filas inválidas), que
la migración sea atómica, las restricciones nuevas, la vista de
compatibilidad y las copias de seguridad antiguas y nuevas.
"""

import os
import shutil
import sqlite3
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import reyger.core.db as modulo_db
from reyger.core import backup, documentos, migrations

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)

COLUMNAS_LEGADO = (
    "factura, nombre_articulo, valor_articulo, cantidad, subtotal, metodo_pago,"
    " cantidad_efectivo, cantidad_tarjeta, fecha, cliente_id, tipo_iva, cuota_iva,"
    " base_imponible, tipo_documento, estado, numero_ticket"
)

#: Ventas en el formato antiguo: una fila por línea, con los datos del
#: documento repetidos en cada una.
FILAS_LEGADO = [
    # Ticket de 3 líneas: el efectivo entregado (20 €) se repite en cada línea.
    ("T-0001", "Café", 2.2, 2, 4.4, "Efectivo", 20, 0, "2026-10-05 12:00:00", None, 10, 0.4, 4.0, "ticket", "emitido", "T-0001"),
    ("T-0001", "Libro", 12.1, 1, 12.1, "Efectivo", 20, 0, "2026-10-05 12:00:00", None, 4, 0.47, 11.63, "ticket", "emitido", "T-0001"),
    # Anterior al desglose de IVA: base y cuota a 0.
    ("T-0001", "Té", 1.5, 1, 1.5, "Efectivo", 20, 0, "2026-10-05 12:00:00", None, 21, 0, 0, "ticket", "emitido", "T-0001"),
    ("F-0001", "Libro", 12.1, 2, 24.2, "Tarjeta", 0, 24.2, "2026-10-06 09:30:00", 7, 4, 0.93, 23.27, "factura", "emitido", None),
    # Cliente borrado (no había clave foránea).
    ("F-0002", "Café", 2.2, 1, 2.2, "Tarjeta", 0, 2.2, "2026-10-06 10:00:00", 99, 10, 0.2, 2.0, "factura", "emitido", None),
    # Borrador con la fecha en texto local.
    ("BORRADOR-abc", "Café", 2.2, 3, 6.6, "Pendiente", 0, 0, "05/10/2026 18:45", 7, 10, 0.6, 6.0, "factura", "borrador", None),
    # Inválida: cantidad 0.
    ("T-0002", "Basura", 1.0, 0, 0, "Efectivo", 0, 0, "2026-10-07 10:00:00", None, 21, 0, 0, "ticket", "emitido", "T-0002"),
]


@pytest.fixture
def madrid(monkeypatch):
    """Zona horaria fija para que la conversión UTC → local sea comprobable."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset no disponible en este sistema")
    monkeypatch.setenv("TZ", "Europe/Madrid")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def bd_v13(tmp_path, monkeypatch):
    """Base en el esquema 13 con ventas en el formato antiguo."""
    (tmp_path / "v13").mkdir()
    ruta = str(tmp_path / "v13" / "database.db")
    conn = sqlite3.connect(ruta)
    conn.execute("PRAGMA foreign_keys = ON")
    migrations.run_migrations(conn, hasta=13)
    conn.execute("INSERT INTO clientes (id, nombre) VALUES (7, 'Ana')")
    conn.execute(
        "INSERT INTO inventario (id, nombre, proveedor, precio, costo, stock)"
        " VALUES (1, 'Café', '', 2.2, 1, 10), (2, 'Libro', '', 12.1, 5, 3)"
    )
    conn.executemany(
        f"INSERT INTO ventas ({COLUMNAS_LEGADO}) VALUES ({', '.join('?' * 16)})",
        FILAS_LEGADO,
    )
    conn.commit()
    yield ruta, conn
    conn.close()


def _documentos(conn):
    return {
        fila[0]: fila[1:]
        for fila in conn.execute(
            "SELECT numero, tipo, estado, fecha, cliente_id, metodo_pago,"
            " efectivo_cent, tarjeta_cent FROM documentos"
        )
    }


def _lineas(conn, numero):
    return conn.execute(
        "SELECT l.producto_id, l.nombre, l.cantidad, l.precio_cent, l.tipo_iva,"
        " l.subtotal_cent, l.base_cent, l.cuota_cent FROM lineas_documento l"
        " JOIN documentos d ON d.id = l.documento_id WHERE d.numero = ? ORDER BY l.id",
        (numero,),
    ).fetchall()


# ---------------------------------------------------------------- conversión
def test_conserva_los_totales_emitidos(bd_v13):
    _, conn = bd_v13
    antes = conn.execute(
        "SELECT ROUND(SUM(subtotal), 2) FROM ventas WHERE estado = 'emitido' AND cantidad <> 0"
    ).fetchone()[0]
    migrations.run_migrations(conn)
    despues = conn.execute(
        "SELECT SUM(l.subtotal_cent) FROM lineas_documento l"
        " JOIN documentos d ON d.id = l.documento_id WHERE d.estado = 'emitido'"
    ).fetchone()[0]
    assert despues == round(antes * 100)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrations.LATEST_VERSION


def test_un_documento_por_numero_con_lo_entregado_una_vez(bd_v13):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    docs = _documentos(conn)
    assert set(docs) == {"T-0001", "F-0001", "F-0002", "BORRADOR-abc"}
    # 20 € en efectivo, no 60 € (3 líneas × 20).
    assert docs["T-0001"][5:] == (2000, 0)
    assert docs["F-0001"][5:] == (0, 2420)
    assert docs["BORRADOR-abc"][1] == "borrador"
    assert len(_lineas(conn, "T-0001")) == 3


def test_fechas_pasan_a_hora_local(bd_v13, madrid):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    docs = _documentos(conn)
    # CURRENT_TIMESTAMP era UTC: en octubre Madrid va dos horas por delante.
    assert docs["T-0001"][2] == "2026-10-05 14:00:00"
    assert docs["F-0001"][2] == "2026-10-06 11:30:00"
    # El borrador ya guardaba hora local en texto dd/mm/aaaa.
    assert docs["BORRADOR-abc"][2] == "2026-10-05 18:45:00"


def test_enlaza_productos_y_descarta_clientes_inexistentes(bd_v13):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    assert [l[0] for l in _lineas(conn, "T-0001")] == [1, 2, None]  # «Té» no existe
    docs = _documentos(conn)
    assert docs["F-0001"][3] == 7
    assert docs["F-0002"][3] is None  # el cliente 99 no existía
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_recalcula_el_iva_que_faltaba(bd_v13):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    te = _lineas(conn, "T-0001")[2]
    assert te[5:] == (150, 124, 26)  # 1,50 € al 21 %: base 1,24 + cuota 0,26
    cafe = _lineas(conn, "T-0001")[0]
    assert cafe[5:] == (440, 400, 40)  # el desglose existente se respeta


def test_omite_filas_invalidas_sin_impedir_el_arranque(bd_v13, caplog):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    assert "T-0002" not in _documentos(conn)
    assert "cantidad 0" in caplog.text


def test_guarda_copia_antes_de_migrar(bd_v13):
    ruta, conn = bd_v13
    migrations.run_migrations(conn)
    copias = [f for f in os.listdir(os.path.dirname(ruta)) if f.startswith("database_antes_v14_")]
    assert len(copias) == 1
    copia = sqlite3.connect(os.path.join(os.path.dirname(ruta), copias[0]))
    try:
        assert copia.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == len(FILAS_LEGADO)
    finally:
        copia.close()


def test_es_atomica_si_la_conversion_falla(bd_v13, monkeypatch):
    _, conn = bd_v13

    def romper(*_a, **_k):
        raise RuntimeError("fallo a mitad")

    monkeypatch.setattr(documentos, "convertir_ventas_legado", romper)
    with pytest.raises(RuntimeError):
        migrations.run_migrations(conn)
    tipo = conn.execute("SELECT type FROM sqlite_master WHERE name = 'ventas'").fetchone()[0]
    assert tipo == "table"
    assert conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == len(FILAS_LEGADO)
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'documentos'"
    ).fetchone() is None
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 13


def test_reejecutar_la_14_no_pierde_documentos(bd_v13):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    antes = _documentos(conn)
    conn.execute("PRAGMA user_version = 13")
    conn.commit()
    migrations.run_migrations(conn)
    assert _documentos(conn) == antes


def test_quita_las_tablas_de_borradores_sin_uso(bd_v13):
    _, conn = bd_v13
    migrations.run_migrations(conn)
    for tabla in migrations.TABLAS_SIN_USO_V14:
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = ?", (tabla,)
        ).fetchone() is None


def test_conserva_las_tablas_de_borradores_con_datos(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "database.db"))
    migrations.run_migrations(conn, hasta=13)
    conn.execute("INSERT INTO facturas_borradores (nombre) VALUES ('antiguo')")
    conn.commit()
    migrations.run_migrations(conn)
    assert conn.execute("SELECT COUNT(*) FROM facturas_borradores").fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize("valor, esperado", [
    ("05/10/2026 18:45", "2026-10-05 18:45:00"),
    ("05/10/2026", "2026-10-05 00:00:00"),
    ("2026-10-05", "2026-10-05 00:00:00"),
    ("2026-01-15 23:30:00", "2026-01-16 00:30:00"),  # invierno: UTC+1
    ("", None),
    (None, None),
    ("ayer", None),
])
def test_normalizar_fecha(valor, esperado, madrid):
    assert documentos.normalizar_fecha(valor) == esperado


# ------------------------------------------------------------ restricciones
@pytest.fixture
def bd_actual(tmp_path, monkeypatch):
    (tmp_path / "actual").mkdir()
    ruta = str(tmp_path / "actual" / "database.db")
    shutil.copyfile(PLANTILLA, ruta)
    monkeypatch.setattr(modulo_db, "get_db_path", lambda: ruta)
    modulo_db.close()
    migrations.run_migrations(modulo_db.get_connection())
    yield ruta
    modulo_db.close()


def _documento(conn, numero="T-0001", **campos):
    valores = {"tipo": "ticket", "estado": "emitido", **campos}
    columnas = ", ".join(["numero", *valores])
    return conn.execute(
        f"INSERT INTO documentos ({columnas}) VALUES ({', '.join('?' * (len(valores) + 1))})",
        (numero, *valores.values()),
    ).lastrowid


@pytest.mark.parametrize("campos", [
    {"tipo": "albaran"},
    {"estado": "anulado"},
    {"efectivo_cent": -1},
    {"cliente_id": 999},
])
def test_documento_rechaza_valores_invalidos(bd_actual, campos):
    conn = modulo_db.get_connection()
    with pytest.raises(sqlite3.IntegrityError):
        _documento(conn, **campos)
    conn.rollback()


def test_numero_de_documento_unico(bd_actual):
    conn = modulo_db.get_connection()
    _documento(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _documento(conn)
    conn.rollback()


@pytest.mark.parametrize("cantidad, precio, iva", [(0, 100, 21), (1, -1, 21), (1, 100, 150)])
def test_linea_rechaza_valores_invalidos(bd_actual, cantidad, precio, iva):
    conn = modulo_db.get_connection()
    doc = _documento(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO lineas_documento (documento_id, nombre, cantidad, precio_cent,"
            " tipo_iva, subtotal_cent, base_cent, cuota_cent) VALUES (?,?,?,?,?,0,0,0)",
            (doc, "X", cantidad, precio, iva),
        )
    conn.rollback()


def test_borrar_producto_conserva_la_linea(bd_actual):
    conn = modulo_db.get_connection()
    prod = conn.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock) VALUES ('X','',1,1,1)"
    ).lastrowid
    doc = _documento(conn)
    conn.execute(
        "INSERT INTO lineas_documento (documento_id, producto_id, nombre, cantidad,"
        " precio_cent, tipo_iva, subtotal_cent, base_cent, cuota_cent)"
        " VALUES (?, ?, 'X', 1, 100, 21, 100, 83, 17)",
        (doc, prod),
    )
    conn.execute("DELETE FROM inventario WHERE id = ?", (prod,))
    conn.commit()
    assert tuple(conn.execute("SELECT producto_id, nombre FROM lineas_documento").fetchone()) == (None, "X")


def test_cliente_con_documentos_no_se_puede_borrar(bd_actual):
    conn = modulo_db.get_connection()
    cliente = conn.execute("INSERT INTO clientes (nombre) VALUES ('Ana')").lastrowid
    _documento(conn, cliente_id=cliente)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente,))
    conn.rollback()


def test_vista_ventas_es_de_solo_lectura(bd_actual):
    conn = modulo_db.get_connection()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO ventas (factura) VALUES ('T-9')")


def test_consultas_frecuentes_usan_indices(bd_actual):
    conn = modulo_db.get_connection()

    def plan(sql):
        return " ".join(f[3] for f in conn.execute("EXPLAIN QUERY PLAN " + sql, (1,)))

    assert "idx_documentos_cliente_id" in plan("SELECT id FROM documentos WHERE cliente_id = ?")
    assert "idx_lineas_documento_documento_id" in plan(
        "SELECT id FROM lineas_documento WHERE documento_id = ?"
    )
    assert "idx_lineas_documento_producto_id" in plan(
        "SELECT id FROM lineas_documento WHERE producto_id = ?"
    )


# ---------------------------------------------------- copias de seguridad
def test_importar_copia_db_antigua_la_migra(bd_v13, bd_actual):
    ruta_v13, conn_v13 = bd_v13
    conn_v13.close()
    backup.importar_datos(ruta_v13, bd_actual)
    modulo_db.close()
    conn = modulo_db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrations.LATEST_VERSION
    assert set(_documentos(conn)) == {"T-0001", "F-0001", "F-0002", "BORRADOR-abc"}


def test_importar_copia_db_nueva(bd_actual, tmp_path):
    from reyger.domain import ventas as dv

    modulo_db.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock) VALUES ('X','',1,1,9)"
    )
    doc = dv.registrar_venta([dv.LineaVenta("X", 1.0, 2, 21.0)], "ticket", "Efectivo", 5)
    copia = str(tmp_path / "copia.db")
    backup.exportar_sqlite(copia, bd_actual)
    modulo_db.execute("DELETE FROM documentos")
    backup.importar_datos(copia, bd_actual)  # antes: «faltan las tablas ventas»
    modulo_db.close()
    assert doc.numero in _documentos(modulo_db.get_connection())


@pytest.mark.parametrize("extension", [".xlsx", ".zip"])
def test_exportar_e_importar_tablas_conserva_documentos(bd_actual, tmp_path, extension):
    from reyger.domain import ventas as dv

    modulo_db.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock) VALUES ('X','',1,1,9)"
    )
    dv.registrar_venta([dv.LineaVenta("X", 1.0, 2, 21.0)], "ticket", "Efectivo", 5)
    antes = (_documentos(modulo_db.get_connection()), _lineas(modulo_db.get_connection(), "T-0001"))
    destino = str(tmp_path / f"copia{extension}")
    backup.exportar_datos(destino, bd_actual)
    modulo_db.execute("DELETE FROM lineas_documento")
    modulo_db.execute("DELETE FROM documentos")
    backup.importar_datos(destino, bd_actual)
    modulo_db.close()
    conn = modulo_db.get_connection()
    assert (_documentos(conn), _lineas(conn, "T-0001")) == antes


def test_importar_excel_antiguo_convierte_la_hoja_ventas(bd_actual, tmp_path):
    """Las copias en Excel anteriores al esquema 14 traen una hoja «ventas»."""
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "ventas"
    hoja.append(COLUMNAS_LEGADO.replace(" ", "").split(","))
    for fila in FILAS_LEGADO[:4]:
        hoja.append(list(fila))
    clientes = libro.create_sheet("clientes")
    clientes.append(["id", "nombre"])
    clientes.append([7, "Ana"])
    ruta = str(tmp_path / "antigua.xlsx")
    libro.save(ruta)

    resultado = backup.importar_datos(ruta, bd_actual)

    assert resultado["resumen"]["documentos"] == 2
    assert "ventas" not in resultado["ignoradas"]
    modulo_db.close()
    conn = modulo_db.get_connection()
    docs = _documentos(conn)
    assert set(docs) == {"T-0001", "F-0001"}
    assert docs["F-0001"][3] == 7  # el cliente de la misma copia queda enlazado


@pytest.mark.parametrize("extension", [".xlsx", ".zip"])
def test_restaurar_copia_con_producto_del_registro_rapido(bd_actual, tmp_path, extension):
    """Regresión: el proveedor '' del registro rápido volvía como celda vacía
    (NULL) y la copia entera no se podía restaurar."""
    from reyger.hardware.barcode_scanner import registrar_producto_rapido

    registrar_producto_rapido(None, "8400000000017", "Galletas", 1.5)
    destino = str(tmp_path / f"copia{extension}")
    backup.exportar_datos(destino, bd_actual)
    backup.importar_datos(destino, bd_actual)
    modulo_db.close()
    fila = modulo_db.get_connection().execute(
        "SELECT nombre, proveedor FROM inventario WHERE codigo_barras = '8400000000017'"
    ).fetchone()
    assert tuple(fila) == ("Galletas", "")
