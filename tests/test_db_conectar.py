"""Tests de ``db.conectar``: conexiones independientes a la base de la app.

Exportaciones, importaciones y respaldos abren su propia conexión; deben
llevar el mismo ``busy_timeout`` y claves foráneas que la compartida para
no fallar con "database is locked" mientras la interfaz escribe.
"""

import os
import sqlite3
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import reyger.core.db as db


@pytest.fixture
def ruta_bd(tmp_path):
    ruta = tmp_path / "tienda.db"
    conn = sqlite3.connect(ruta)
    conn.execute("CREATE TABLE padre (id INTEGER PRIMARY KEY)")
    conn.execute(
        "CREATE TABLE hijo (id INTEGER PRIMARY KEY,"
        " padre_id INTEGER REFERENCES padre(id))"
    )
    conn.commit()
    conn.close()
    return str(ruta)


def test_aplica_busy_timeout_y_claves_foraneas(ruta_bd):
    conn = db.conectar(ruta_bd)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO hijo (padre_id) VALUES (99)")
    finally:
        conn.close()


def test_por_defecto_usa_la_base_de_la_app(ruta_bd, monkeypatch):
    monkeypatch.setattr(db, "get_db_path", lambda: ruta_bd)
    conn = db.conectar()
    try:
        tablas = {f[0] for f in conn.execute("SELECT name FROM sqlite_master")}
        assert {"padre", "hijo"} <= tablas
    finally:
        conn.close()


def test_solo_lectura_no_escribe_ni_crea(ruta_bd, tmp_path):
    conn = db.conectar(ruta_bd, solo_lectura=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO padre DEFAULT VALUES")
    finally:
        conn.close()
    with pytest.raises(sqlite3.OperationalError):
        db.conectar(tmp_path / "no_existe.db", solo_lectura=True)
    assert not (tmp_path / "no_existe.db").exists()


def test_espera_al_bloqueo_de_otra_conexion_en_vez_de_fallar(ruta_bd):
    """Una importación no falla si la interfaz está a mitad de escritura."""
    interfaz = sqlite3.connect(ruta_bd, check_same_thread=False)
    interfaz.execute("BEGIN IMMEDIATE")
    interfaz.execute("INSERT INTO padre DEFAULT VALUES")

    def terminar_escritura():
        time.sleep(0.4)
        interfaz.commit()

    hilo = threading.Thread(target=terminar_escritura)
    hilo.start()
    importacion = db.conectar(ruta_bd)
    try:
        importacion.execute("INSERT INTO padre DEFAULT VALUES")
        importacion.commit()
        assert importacion.execute("SELECT COUNT(*) FROM padre").fetchone()[0] == 2
    finally:
        hilo.join()
        importacion.close()
        interfaz.close()
