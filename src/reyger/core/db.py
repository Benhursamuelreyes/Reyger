"""Capa de acceso a datos centralizada de Reyger.

Todos los módulos deberían obtener su conexión desde aquí en lugar de
abrir ``sqlite3.connect`` por su cuenta. La conexión es única y se
comparte entre la interfaz y los hilos de trabajo que lanza
``core.hilos.en_hilo``; por eso se crea con ``check_same_thread=False``.
El acceso concurrente a la misma conexión no es seguro en SQLite: cada
transacción debe ser corta y no cruzarse con la de otro hilo. WAL y
``busy_timeout`` evitan además los bloqueos entre esta conexión y las
que abren ``datos.py`` y ``backup.py`` sobre el mismo fichero.

Las operaciones que necesitan una conexión propia sobre la base de la app
(exportaciones, importaciones, respaldos) la abren con :func:`conectar`, que
aplica el mismo ``busy_timeout`` y las mismas claves foráneas. Solo los
ficheros auxiliares (destinos de respaldo, copias temporales) se abren con
``sqlite3.connect`` directamente.

AVISO — copia manual de la base: con WAL activo los datos comprometidos
viven también en ``database.db-wal``, así que copiar solo ``database.db``
(a mano, por correo o con una nube sincronizada) produce una copia
**incompleta** que, al restaurarse, aparece con tablas vacías o con errores
de integridad. El modo WAL se activa solo si el sistema de ficheros lo
admite y **degrada en silencio** a ``delete`` cuando no (unidades de red,
determinados USB), de modo que no puede suponerse: consúltalo con
``db.wal_activo()``. La copia fiable la hace ``core.backup``, que usa
``sqlite3.Connection.backup()`` e incluye el WAL en el destino.
"""

import os
import sqlite3
from contextlib import contextmanager
from urllib.parse import quote

from ..resources import get_db_path

_conexion = None
_conexion_configurada = False

#: Espera máxima (ms) ante un bloqueo de otra conexión al mismo fichero.
BUSY_TIMEOUT_MS = 5000


def get_connection():
    """Devuelve la conexión compartida, creándola si es necesario."""
    global _conexion
    if _conexion is None:
        _conexion = sqlite3.connect(get_db_path(), check_same_thread=False)
        _conexion.row_factory = sqlite3.Row
        # Rendimiento en terminales modestos: la integridad ante cortes
        # de luz la cubre el respaldo automático previo a importaciones.
        _conexion.execute("PRAGMA foreign_keys = ON")
        _conexion.execute("PRAGMA synchronous = NORMAL")
        _conexion.execute("PRAGMA temp_store = MEMORY")
        _conexion.execute("PRAGMA cache_size = -2000")  # ~2 MB de página caché

        # ``datos.py`` y ``backup.py`` abren su propia conexión al mismo
        # fichero. Sin este margen, un lector en segundo plano puede dejar
        # la escritura de la interfaz esperando el bloqueo hasta el límite
        # por defecto de la compilación de SQLite y fallar con
        # "database is locked". 5 s es suficiente para el uso real de la app.
        _conexion.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")

        # WAL permite que los lectores en segundo plano (exportaciones,
        # respaldos) no bloqueen a la escritura de la interfaz. Necesita
        # ``shm`` compartido: si el sistema de ficheros no lo soporta
        # (por ejemplo, algunas unidades de red) se conserva el modo
        # rollback anterior.
        try:
            if _conexion.execute("PRAGMA journal_mode = WAL").fetchone()[0] != "wal":
                raise sqlite3.OperationalError("WAL no disponible")
        except sqlite3.Error:
            pass  # se mantiene el journal_mode por defecto (delete)
    return _conexion


def conectar(ruta=None, solo_lectura=False):
    """Abre una conexión **independiente** (no la compartida).

    Para trabajos que necesitan su propia transacción sobre la base de la
    app: exportar, importar o respaldar. Aplica ``busy_timeout`` (espera en
    vez de fallar con "database is locked" si la interfaz está escribiendo)
    y activa las claves foráneas, igual que :func:`get_connection`. El
    llamador es dueño de la conexión y debe cerrarla.

    Args:
        ruta: Fichero de base de datos. Por defecto, la base de la app.
        solo_lectura: Abre en modo ``ro`` vía URI: no crea el fichero si no
            existe ni lo modifica.
    """
    ruta = str(ruta or get_db_path())
    if solo_lectura:
        uri = "file:" + quote(os.path.abspath(ruta)) + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(ruta)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def journal_mode(conn=None):
    """Devuelve el modo de journal real de la base de datos.

    WAL se activa *si el sistema de ficheros lo permite* (necesita ``shm``
    compartido; fallan algunas unidades de red y determinados USB). Si no,
    ``get_connection()`` degrada en silencio al modo ``delete``. Por eso el
    modo activo no puede suponerse: hay que consultarlo.

    Args:
        conn: Conexión sobre la que consultar. Por defecto, la conexión
            compartida de la aplicación. Acepta una conexión propia para
            consultar bases ajenas (``backup.py``, tests).
    """
    try:
        objetivo = conn if conn is not None else get_connection()
        return (objetivo.execute("PRAGMA journal_mode").fetchone()[0] or "").lower()
    except sqlite3.Error:
        return ""


def wal_activo(conn=None):
    """``True`` si la base está en modo WAL.

    Con WAL activo, los datos comprometidos viven también en
    ``database.db-wal``. Copiar solo ``database.db`` (a mano, por un
    explorador o una nube sincronizada) se lleva un fichero incompleto, y al
    restaurarlo aparecen tablas vacías o errores de integridad. La única copia
    fiable la hace ``core.backup`` con ``Connection.backup()``, que incluye el
    WAL en el destino.
    """
    return journal_mode(conn) == "wal"


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


def optimizar():
    """``PRAGMA optimize`` sobre la conexión compartida (si está abierta).

    Actualiza las estadísticas que usa el planificador de consultas; SQLite
    recomienda ejecutarlo al cerrar conexiones de larga duración.
    """
    if _conexion is not None:
        _conexion.execute("PRAGMA optimize")


def close():
    """Cierra la conexión compartida (útil en tests y al salir)."""
    global _conexion
    if _conexion is not None:
        _conexion.close()
        _conexion = None
