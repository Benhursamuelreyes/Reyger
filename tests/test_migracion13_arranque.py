"""Tests de ARRANQUE: ``ensure_database()`` no puede fallar por la migración 13.

Fallo que cubren (B2): una instalación heredada puede tener
``contadores_documentos`` con ``UNIQUE(tipo)`` en vez de la restricción
compuesta ``UNIQUE(tipo, serie)``. La migración 13 reconciliaba los
contadores con ``INSERT ... ON CONFLICT(tipo, serie)``, una cláusula que
exige que exista la restricción a la que referencia. Al no existir,
SQLite lanzaba ``OperationalError: ON CONFLICT clause does not match any
PRIMARY KEY or UNIQUE constraint``, ``run_migrations`` revertía,
``ensure_database()`` propagaba el error y el proceso de la app moría al
arrancar (silencioso con ``console=false``).

Cada test documenta el fallo que corrige: sin el arreglo falla; con él pasa.
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
    LATEST_VERSION,
    _asegurar_esquema_correlatividad,
    _reconciliar_contadores_documentos,
    ensure_database,
    run_migrations,
)

PLANTILLA = os.path.join(SRC_DIR, "reyger", "assets", "database.db")

# Contador deliberadamente alto e irrecoverable desde 'ventas': si una
# migración lo pierde, la secuencia retrocede y la app reemite números de
# factura ya emitidos (duplicado fiscal silencioso).
ULTIMO_EMITIDO = 4210


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _crear_bd_heredada(ruta, ultimo_numero=ULTIMO_EMITIDO):
    """BD en la versión 12 con el esquema legado ``UNIQUE(tipo)``.

    Replica una instalación real: la tabla de contadores existe pero con la
    unicidad no compuesta, que es exactamente lo que rompe el ``ON CONFLICT``.
    """
    conn = sqlite3.connect(ruta)
    conn.execute(
        "CREATE TABLE ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "factura TEXT, estado TEXT, numero_ticket TEXT)"
    )
    conn.execute(
        "CREATE TABLE business_profile (id INTEGER PRIMARY KEY AUTOINCREMENT, nif TEXT)"
    )
    conn.execute(
        "CREATE TABLE contadores_documentos ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  tipo TEXT NOT NULL,"
        "  serie TEXT NOT NULL,"
        "  ultimo_numero INTEGER NOT NULL DEFAULT 0,"
        "  UNIQUE(tipo))"
    )
    if ultimo_numero:
        conn.execute(
            "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
            "VALUES ('factura', 'F-', ?)",
            (ultimo_numero,),
        )
    # Facturas ya emitidas: dan un máximo en 'ventas' que la reconciliación
    # debe poder subir, pero muy por debajo del contador real.
    for numero in ("F-0001", "F-0002", "F-0003"):
        conn.execute(
            "INSERT INTO ventas (factura, estado) VALUES (?, 'emitido')", (numero,)
        )
    conn.execute("PRAGMA user_version = 12")
    conn.commit()
    conn.close()
    return ruta


@pytest.fixture
def bd_temporal(tmp_path, monkeypatch):
    """Ruta de BD temporal y ``db.get_db_path`` redirigido a ella."""
    ruta = str(tmp_path / "database.db")
    monkeypatch.setattr(db, "get_db_path", lambda: ruta)
    yield ruta
    db._conexion = None


def _ddl_contadores(conn):
    fila = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'contadores_documentos'"
    ).fetchone()
    return (fila[0] if fila and fila[0] else "").replace(" ", "").upper()


def _contadores(conn):
    # Índices posicionales: funcionan tanto con sqlite3.Row (get_connection)
    # como con una conexión cruda de sqlite3, sin depender de row_factory.
    return {
        (f[0], f[1]): f[2]
        for f in conn.execute(
            "SELECT tipo, serie, ultimo_numero FROM contadores_documentos"
        )
    }


# ---------------------------------------------------------------------------
# 1) El fallo: ensure_database() NO debe lanzar OperationalError
# ---------------------------------------------------------------------------


def test_arranque_bd_heredada_no_lanza_operationalerror(bd_temporal):
    """La instalación heredada arranca: sin ``OperationalError``."""
    _crear_bd_heredada(bd_temporal)

    ensure_database()  # antes: OperationalError y proceso muerto

    conn = db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION


def test_la_migracion_13_avanza_el_version_tras_reconciliar(bd_temporal):
    """La migración 13 se marca aplicada: no se queda reintentando en cada arranque."""
    _crear_bd_heredada(bd_temporal)
    conn = db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 12

    run_migrations(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 13


def test_reconciliar_contadores_no_depende_del_esquema_heredado(bd_temporal):
    """La reconciliación no usa ``ON CONFLICT``: aguanta ``UNIQUE(tipo)``.

    Este test ata el arreglo de raíz aunque nadie llame a la reparación de
    esquema: la reconciliación se ejecuta sobre la tabla tal cual está.
    """
    _crear_bd_heredada(bd_temporal, ultimo_numero=0)
    conn = db.get_connection()

    _reconciliar_contadores_documentos(conn)  # antes: OperationalError

    assert _contadores(conn)[("factura", "F-")] == 3


def test_arranque_bd_limpia_no_lanza_error(bd_temporal):
    """Base recién creada (version 0) migra entera sin error."""
    sqlite3.connect(bd_temporal).close()

    ensure_database()

    conn = db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION


def test_arranque_bd_de_la_plantilla_no_lanza_error(bd_temporal):
    """La BD que se distribuye (versión 12) migra a 13 sin error."""
    shutil.copy2(PLANTILLA, bd_temporal)

    ensure_database()

    conn = db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION


def test_arranque_sin_tabla_contadores_no_lanza_error(bd_temporal):
    """Esquema mínimo sin ``contadores_documentos``: la migración no revienta."""
    conn = sqlite3.connect(bd_temporal)
    conn.execute(
        "CREATE TABLE ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "factura TEXT, estado TEXT)"
    )
    conn.execute("INSERT INTO ventas (factura, estado) VALUES ('F-0001', 'emitido')")
    conn.execute("PRAGMA user_version = 12")
    conn.commit()
    conn.close()

    ensure_database()  # antes: "no such table: contadores_documentos"

    conn = db.get_connection()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION


# ---------------------------------------------------------------------------
# 2) Lo que NO puede pasar: perder el contador ya emitido
# ---------------------------------------------------------------------------


def test_el_contador_ya_emitido_no_se_pierde(bd_temporal):
    """El máximo realmente emitido sobrevive a la migración.

    Si la reparación de esquema destruye la tabla sin preservar, el contador
    cae al máximo reconstruido desde 'ventas' (3) y la app reemite F-0004,
    F-0005... duplicando las ya emitidas. Esto es el riesgo real del arreglo.
    """
    _crear_bd_heredada(bd_temporal)
    assert _contadores(db.get_connection())[("factura", "F-")] == ULTIMO_EMITIDO

    ensure_database()

    assert _contadores(db.get_connection())[("factura", "F-")] == ULTIMO_EMITIDO


def test_la_reparacion_de_esquema_conserva_los_contadores(bd_temporal):
    """``_asegurar_esquema_correlatividad`` reconstruye sin perder datos."""
    _crear_bd_heredada(bd_temporal)
    conn = db.get_connection()

    _asegurar_esquema_correlatividad(conn)

    assert _contadores(conn)[("factura", "F-")] == ULTIMO_EMITIDO


def test_reconstruir_colapsa_duplicados_con_el_maximo_mayor(bd_temporal):
    """Si el UNIQUE(tipo) previo dejó filas raras, gana el máximo: nunca baja."""
    conn = sqlite3.connect(bd_temporal)
    conn.execute(
        "CREATE TABLE contadores_documentos ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, serie TEXT,"
        "  ultimo_numero INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('factura','F-',7)"
    )
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('factura','F-',90)"
    )
    conn.commit()

    _asegurar_esquema_correlatividad(conn)

    assert _contadores(conn)[("factura", "F-")] == 90


def test_la_reconciliacion_sube_el_contador_nunca_lo_baja(bd_temporal):
    """Invariante del módulo: la secuencia correlativa no retrocede."""
    _crear_bd_heredada(bd_temporal, ultimo_numero=9999)
    conn = db.get_connection()

    run_migrations(conn)

    assert _contadores(conn)[("factura", "F-")] == 9999


# ---------------------------------------------------------------------------
# 3) El esquema queda utilizable
# ---------------------------------------------------------------------------


def test_el_esquema_se_repara_a_unicidad_compuesta(bd_temporal):
    """Tras migrar, la unicidad es ``(tipo, serie)`` y admite dos series."""
    _crear_bd_heredada(bd_temporal)

    ensure_database()

    conn = db.get_connection()
    assert "UNIQUE(TIPO,SERIE)" in _ddl_contadores(conn)
    # Dos series del mismo tipo: imposible con el UNIQUE(tipo) legado.
    conn.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) "
        "VALUES ('factura', 'FA-', 5)"
    )
    conn.commit()
    assert _contadores(conn)[("factura", "FA-")] == 5


def test_la_reparacion_es_idempotente(bd_temporal):
    """Llamarla dos veces no cambia nada ni duplica filas."""
    _crear_bd_heredada(bd_temporal)
    conn = db.get_connection()

    _asegurar_esquema_correlatividad(conn)
    _asegurar_esquema_correlatividad(conn)

    assert _contadores(conn)[("factura", "F-")] == ULTIMO_EMITIDO


def test_no_queda_la_tabla_de_respaldo(bd_temporal):
    """La tabla temporal de la reconstrucción se limpia."""
    _crear_bd_heredada(bd_temporal)
    conn = db.get_connection()

    _asegurar_esquema_correlatividad(conn)

    sobrantes = [
        f[0]
        for f in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name LIKE '%respaldo%'"
        )
    ]
    assert not sobrantes, f"Tablas de respaldo abandonadas: {sobrantes}"
