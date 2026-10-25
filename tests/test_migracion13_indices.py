"""Tests de la migración 13: índices, reconciliación de correlatividad,
respaldo coherente con WAL y primalidades de conexión.

Cada test documenta el fallo que corrige: sin la migración 13 (o sin
los arreglos de db.py) fallan; con ellos pasan.
"""

import os
import shutil
import sqlite3
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import reyger.core.db as db
from reyger.core.migrations import (
    INDICES_V13,
    LATEST_VERSION,
    run_migrations,
)

PLANTILLA = os.path.join(SRC_DIR, "reyger", "assets", "database.db")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


#: Estos tests prueban la migración 13 sobre el esquema de entonces (con la
#: tabla ``ventas``); la 14 la sustituye por ``documentos``.
HASTA = 13


@pytest.fixture
def bd_temporal(tmp_path, monkeypatch):
    """Base nueva migrada hasta el esquema 13."""
    ruta = str(tmp_path / "database.db")
    monkeypatch.setattr(db, "get_db_path", lambda: ruta)
    conn = db.get_connection()
    run_migrations(conn, hasta=HASTA)
    yield ruta
    db._conexion = None


@pytest.fixture
def bd_actual(tmp_path, monkeypatch):
    """Copia de la plantilla con todas las migraciones aplicadas."""
    ruta = str(tmp_path / "database.db")
    shutil.copy2(PLANTILLA, ruta)
    monkeypatch.setattr(db, "get_db_path", lambda: ruta)
    run_migrations(db.get_connection())
    yield ruta
    db._conexion = None


def _plan(conn, sql, parametros=()):
    return " || ".join(
        fila[3] for fila in conn.execute("EXPLAIN QUERY PLAN " + sql, parametros)
    )


# ---------------------------------------------------------------------------
# 1) La migración existe y es aditiva
# ---------------------------------------------------------------------------


def test_migracion_13_registrada():
    from reyger.core.migrations import MIGRACIONES

    assert 13 in {version for version, _ in MIGRACIONES}
    assert LATEST_VERSION >= 13


def test_migracion_13_crea_todos_sus_indices(bd_temporal):
    conn = db.get_connection()
    existentes = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }
    for _tabla, sentencia in INDICES_V13:
        nombre = sentencia.split()[5]
        assert nombre in existentes, f"falta el índice {nombre}"


def test_migracion_13_no_reescribe_una_sola_fila(bd_temporal):
    """La migración solo crea índices: ventas/facturas quedan idénticas."""
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO clientes (nombre, documento) VALUES ('Ana', '11111111X')"
    )
    conn.execute(
        "INSERT INTO facturas_verifactu (numero_factura, fecha, nif_emisor, "
        "nif_receptor, nombre_receptor, base_imponible, tipo_iva, total_iva, "
        "total, estado, huella, huella_anterior, numero_ord) "
        "VALUES ('F-0001', '2024-01-01', 'B1', 'B2', 'Cliente', 100, 21, 21, "
        "121, 'Emitida', 'AAA', '', 1)"
    )
    conn.execute(
        "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, "
        "cantidad, subtotal, numero_ticket, estado) "
        "VALUES ('T-0007', 'Lapiz', 1.0, 2, 2.0, 'T-0007', 'emitido')"
    )
    conn.commit()
    antes = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("clientes", "ventas", "facturas_verifactu")
    }
    facturas_antes = conn.execute(
        "SELECT numero_factura, huella, huella_anterior, numero_ord "
        "FROM facturas_verifactu ORDER BY numero_ord"
    ).fetchall()

    conn.execute("PRAGMA user_version = 12")
    conn.commit()
    run_migrations(conn, hasta=HASTA)

    despues = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("clientes", "ventas", "facturas_verifactu")
    }
    assert antes == despues
    assert facturas_antes == conn.execute(
        "SELECT numero_factura, huella, huella_anterior, numero_ord "
        "FROM facturas_verifactu ORDER BY numero_ord"
    ).fetchall()


def test_migracion_13_es_idempotente(bd_temporal):
    conn = db.get_connection()
    conn.execute("PRAGMA user_version = 12")
    conn.commit()
    run_migrations(conn, hasta=HASTA)
    primera = conn.execute(
        "SELECT tipo, serie, ultimo_numero FROM contadores_documentos "
        "ORDER BY tipo, serie"
    ).fetchall()
    run_migrations(conn, hasta=HASTA)
    run_migrations(conn, hasta=HASTA)
    assert primera == conn.execute(
        "SELECT tipo, serie, ultimo_numero FROM contadores_documentos "
        "ORDER BY tipo, serie"
    ).fetchall()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == HASTA


# ---------------------------------------------------------------------------
# 2) Los SCAN que se corrigen
# ---------------------------------------------------------------------------


def test_clientes_por_documento_usa_indice(bd_temporal):
    """Antes: `SCAN clientes` (200 us por fila al importar)."""
    conn = db.get_connection()
    plan = _plan(conn, "SELECT id FROM clientes WHERE documento = ?", ("X",))
    assert "SEARCH clientes" in plan and "idx_clientes_documento" in plan


def test_ventas_por_cliente_usa_indice(bd_temporal):
    conn = db.get_connection()
    plan = _plan(conn, "SELECT COUNT(*) FROM ventas WHERE cliente_id = ?", (1,))
    assert "SEARCH ventas" in plan and "idx_ventas_cliente_id" in plan


def test_max_numero_ord_usa_indice_covering(bd_temporal):
    """Se ejecuta en cada factura emitida."""
    conn = db.get_connection()
    plan = _plan(conn, "SELECT IFNULL(MAX(numero_ord), 0) FROM facturas_verifactu")
    assert "idx_verifactu_numero_ord" in plan


def test_exportacion_xml_pendientes_ya_no_ordena_en_memoria(bd_temporal):
    conn = db.get_connection()
    plan = _plan(
        conn,
        "SELECT numero_factura FROM facturas_verifactu "
        "WHERE estado_envio = ? ORDER BY numero_ord",
        ("pendiente",),
    )
    assert "USE TEMP B-TREE" not in plan


def test_verificar_cadena_ya_no_ordena_en_memoria(bd_temporal):
    conn = db.get_connection()
    plan = _plan(
        conn, "SELECT * FROM facturas_verifactu ORDER BY numero_ord ASC, id ASC"
    )
    assert "USE TEMP B-TREE" not in plan


@pytest.mark.parametrize(
    "consulta",
    [
        "SELECT id FROM facturas_verifactu WHERE cliente_id = ?",
        "SELECT id FROM albaranes WHERE cliente_id = ?",
        "SELECT id FROM presupuestos WHERE cliente_id = ?",
        "SELECT id FROM inventario WHERE categoria_id = ?",
        "SELECT id FROM inventario WHERE proveedor_id = ?",
        "SELECT id FROM albaranes_productos WHERE albaran_id = ?",
        "SELECT id FROM facturas_verifactu_productos WHERE factura_id = ?",
        "SELECT id FROM presupuestos_productos WHERE presupuesto_id = ?",
        "SELECT id FROM facturas_borradores_productos WHERE borrador_id = ?",
    ],
)
def test_claves_foraneas_hijas_tienen_indice(bd_temporal, consulta):
    """Con foreign_keys=ON, borrar un padre recorre estas tablas enteras."""
    conn = db.get_connection()
    assert "SEARCH" in _plan(conn, consulta, (1,))


# ---------------------------------------------------------------------------
# 3) Reconciliación de la correlatividad (invariante: nunca retrocede)
# ---------------------------------------------------------------------------


def test_reconcilia_serie_real_de_una_siembra_rota(bd_temporal):
    """`_sembrar_contadores_documentos` siembra serie 'T' y número -2.

    Con esa fila, `siguiente_numero('ticket')` no encuentra ('ticket','T-')
    y depende del SCAN de respaldo; si la serie coincidiera, arrancaría en
    negativo y reemitiría números ya usados.
    """
    conn = db.get_connection()
    conn.execute("DELETE FROM contadores_documentos")
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('ticket', 'T', -2)"
    )
    for numero in (1, 2, 3):
        conn.execute(
            "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, "
            "cantidad, subtotal, numero_ticket, estado) "
            "VALUES (?, 'X', 1, 1, 1, ?, 'emitido')",
            (f"F-{numero:04d}", f"T-{numero:04d}"),
        )
    conn.execute("PRAGMA user_version = 12")
    conn.commit()

    run_migrations(conn, hasta=HASTA)

    assert conn.execute(
        "SELECT ultimo_numero FROM contadores_documentos "
        "WHERE tipo = 'ticket' AND serie = 'T-'"
    ).fetchone()[0] == 3
    assert conn.execute(
        "SELECT ultimo_numero FROM contadores_documentos "
        "WHERE tipo = 'factura' AND serie = 'F-'"
    ).fetchone()[0] == 3


def test_reconciliacion_nunca_decrementa_el_contador(bd_temporal):
    conn = db.get_connection()
    conn.execute(
        "UPDATE contadores_documentos SET ultimo_numero = 999999 "
        "WHERE tipo = 'ticket' AND serie = 'T-'"
    )
    conn.execute(
        "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, "
        "cantidad, subtotal, numero_ticket, estado) "
        "VALUES ('F-0001', 'X', 1, 1, 1, 'T-0001', 'emitido')"
    )
    conn.execute("PRAGMA user_version = 12")
    conn.commit()

    run_migrations(conn, hasta=HASTA)

    assert conn.execute(
        "SELECT ultimo_numero FROM contadores_documentos "
        "WHERE tipo = 'ticket' AND serie = 'T-'"
    ).fetchone()[0] == 999999


def test_reconciliacion_no_toca_la_fila_heredada(bd_temporal):
    """No se borra ninguna fila de contador: solo se inserta o se sube."""
    conn = db.get_connection()
    conn.execute("DELETE FROM contadores_documentos")
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('ticket', 'T', -2)"
    )
    conn.execute("PRAGMA user_version = 12")
    conn.commit()

    run_migrations(conn, hasta=HASTA)

    assert conn.execute(
        "SELECT ultimo_numero FROM contadores_documentos "
        "WHERE tipo = 'ticket' AND serie = 'T'"
    ).fetchone()[0] == -2


# ---------------------------------------------------------------------------
# 4) Conexión: WAL, busy_timeout y respaldo coherente
# ---------------------------------------------------------------------------


def test_conexion_activa_wal_y_busy_timeout(bd_temporal):
    conn = db.get_connection()
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_respaldo_incluye_lo_ultimo_committeado_en_wal(tmp_path, monkeypatch):
    """`shutil.copy2` no ve el contenido del fichero -wal: perdía ventas.

    Se deja la conexión viva (como la app) y se comprueba que el respaldo
    tiene exactamente las mismas filas.
    """
    from reyger.core.backup import respaldar_bd_actual

    ruta = str(tmp_path / "database.db")
    shutil.copy2(PLANTILLA, ruta)
    monkeypatch.setattr(db, "get_db_path", lambda: ruta)
    monkeypatch.setattr(
        "reyger.core.backup.get_db_path", lambda: ruta, raising=False
    )

    conn = db.get_connection()
    run_migrations(conn)
    conn.execute(
        "INSERT INTO clientes (nombre) VALUES ('Commitada en el WAL')"
    )
    conn.commit()
    vivos = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]

    ruta_respaldo = respaldar_bd_actual(ruta)
    assert ruta_respaldo is not None

    copia = sqlite3.connect(ruta_respaldo)
    try:
        assert copia.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == vivos
    finally:
        copia.close()
        db._conexion = None


def test_lecturas_de_inventario_no_confirman(bd_temporal):
    """Antes, un SELECT de Inventario cerraba la transacción abierta por
    otro hilo sobre la conexión compartida."""
    from reyger.domain import inventario as dominio

    conn = db.get_connection()
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO clientes (nombre) VALUES ('Pendiente de otro hilo')"
    )
    dominio.listar_productos()
    dominio.nombres_proveedores()
    dominio.codigo_en_uso("123")
    assert conn.in_transaction is True
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 5) VeriFACTu: una escritura fallida no debe quedar a medias
# ---------------------------------------------------------------------------


def test_factura_fallida_no_deja_transaccion_abierta(bd_temporal):
    """Antes devolvía False dejando el INSERT pendiente: el siguiente
    `db.execute()` de cualquier módulo lo commiteaba."""
    from reyger.domain.facturas_verifactu import FacturaVeriFACTU

    conn = db.get_connection()
    factura = FacturaVeriFACTU()
    comun = dict(
        numero_factura="F-0001",
        fecha="2024-01-01",
        nif_emisor="B12345678",
        nif_receptor="",
        nombre_receptor="Cliente",
        base_imponible=100.0,
        tipo_iva=21,
        total_iva=21.0,
        total=121.0,
    )
    assert factura.guardar_datos_factura_db(
        productos=[
            {"nombre_articulo": "Lapiz", "valor_articulo": 100.0,
             "cantidad": 1, "subtotal": 100.0}
        ],
        **comun,
    ) is True
    assert conn.in_transaction is False

    # Un producto inválido hace fallar el segundo INSERT.
    assert factura.guardar_datos_factura_db(
        productos=[
            {"nombre_articulo": None, "valor_articulo": 1.0,
             "cantidad": 1, "subtotal": 1.0}
        ],
        **dict(comun, numero_factura="F-0002"),
    ) is False

    assert conn.in_transaction is False, "quedó una transacción abierta"
    db.execute("INSERT INTO clientes (nombre) VALUES ('otro modulo')")

    assert conn.execute(
        "SELECT COUNT(*) FROM facturas_verifactu WHERE numero_factura = 'F-0002'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM facturas_verifactu WHERE numero_factura = 'F-0001'"
    ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# 6) Borrado de cliente con documentos fiscales
# ---------------------------------------------------------------------------


def test_borrar_cliente_con_documentos_no_lanza_integrity_error(bd_temporal):
    """El borrado directo lanzaba sqlite3.IntegrityError sin capturar."""
    conn = db.get_connection()
    conn.execute("INSERT INTO clientes (nombre, documento) VALUES ('Con docs','1X')")
    cliente_id = conn.execute(
        "SELECT id FROM clientes WHERE documento = '1X'"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO albaranes (numero_albaran, fecha, cliente_nombre, "
        "cliente_direccion, cliente_id) "
        "VALUES ('A-0001', '2024-01-01', 'Con docs', 'Calle 1', ?)",
        (cliente_id,),
    )
    conn.execute(
        "INSERT INTO presupuestos (numero_presupuesto, fecha, cliente_nombre, "
        "cliente_id) VALUES ('PRE-1', '2024-01-01', 'Con docs', ?)",
        (cliente_id,),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    conn.rollback()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_conteo_de_documentos_detecta_los_bloqueos(bd_actual):
    """La misma consulta que ``ui.clientes`` antes de borrar un cliente."""
    conn = db.get_connection()
    conn.execute("INSERT INTO clientes (nombre) VALUES ('Con ventas')")
    cliente_id = conn.execute(
        "SELECT id FROM clientes WHERE nombre = 'Con ventas'"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO documentos (numero, tipo, estado, cliente_id) "
        "VALUES ('F-1', 'factura', 'emitido', ?)",
        (cliente_id,),
    )
    conn.commit()

    total = db.query_one(
        "SELECT "
        "(SELECT COUNT(*) FROM facturas_verifactu WHERE cliente_id = ?) + "
        "(SELECT COUNT(*) FROM albaranes WHERE cliente_id = ?) + "
        "(SELECT COUNT(*) FROM presupuestos WHERE cliente_id = ?) + "
        "(SELECT COUNT(*) FROM documentos WHERE cliente_id = ?) AS total",
        (cliente_id,) * 4,
    )["total"]
    assert total == 1


# ---------------------------------------------------------------------------
# 7) contadores_documentos: unicidad compuesta
# ---------------------------------------------------------------------------


def test_contadores_tienen_unica_compuesta_tipo_serie(bd_temporal):
    """`ventas.pagar()` usa ON CONFLICT(tipo, serie); con UNIQUE(tipo)
    SQLite lanzaba «ON CONFLICT clause does not match any ... constraint»."""
    conn = db.get_connection()
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'contadores_documentos'"
    ).fetchone()[0]
    assert "unique(tipo,serie)" in ddl.replace(" ", "").lower()

    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('ticket', 'A', 1)"
    )
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('ticket', 'B', 1)"
    )
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('ticket', 'A', 5) "
        "ON CONFLICT(tipo, serie) DO UPDATE SET "
        "ultimo_numero = MAX(ultimo_numero, excluded.ultimo_numero)"
    )
    assert conn.execute(
        "SELECT ultimo_numero FROM contadores_documentos WHERE serie = 'A'"
    ).fetchone()[0] == 5