"""Capa de acceso a datos centralizada de Reyger.

Todos los módulos deberían obtener su conexión desde aquí en lugar de
abrir ``sqlite3.connect`` por su cuenta. La conexión es única (la app es
mono-hilo) y activa el cumplimiento de claves foráneas.
"""

import sqlite3
from contextlib import contextmanager

from .resources import get_db_path

_conexion = None


def get_connection():
    """Devuelve la conexión compartida, creándola si es necesario."""
    global _conexion
    if _conexion is None:
        _conexion = sqlite3.connect(get_db_path())
        _conexion.row_factory = sqlite3.Row
        _conexion.execute("PRAGMA foreign_keys = ON")
    return _conexion


def query(sql, parametros=()):
    """Ejecuta un SELECT y devuelve la lista de filas (sqlite3.Row)."""
    cursor = get_connection().execute(sql, parametros)
    filas = cursor.fetchall()
    cursor.close()
    return filas


def query_one(sql, parametros=()):
    """Como :func:`query` pero devuelve solo la primera fila o ``None``."""
    filas = query(sql, parametros)
    return filas[0] if filas else None


def execute(sql, parametros=()):
    """Ejecuta un INSERT/UPDATE/DELETE con commit y devuelve lastrowid."""
    conn = get_connection()
    cursor = conn.execute(sql, parametros)
    conn.commit()
    ultimo_id = cursor.lastrowid
    cursor.close()
    return ultimo_id


@contextmanager
def transaccion():
    """Contexto para varias operaciones atómicas.

    with transaccion() as conn:
        conn.execute(...)
        conn.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close():
    """Cierra la conexión compartida (útil en tests y al salir)."""
    global _conexion
    if _conexion is not None:
        _conexion.close()
        _conexion = None
