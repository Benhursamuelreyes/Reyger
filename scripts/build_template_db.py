#!/usr/bin/env python
"""Regenera las plantillas database.db aplicando todas las migraciones.

Genera dos copias idénticas del esquema final (con ``PRAGMA user_version``
al día y el usuario admin sembrado por las migraciones):

  * ``database.db``            (raíz del repositorio, usada en desarrollo/tests)
  * ``src/reyger/assets/database.db``  (plantilla empaquetada con la app)

Uso:  python scripts/build_template_db.py
"""

import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from reyger.migrations import LATEST_VERSION, run_migrations  # noqa: E402


def construir(ruta):
    if os.path.exists(ruta):
        os.remove(ruta)
    conn = sqlite3.connect(ruta)
    try:
        run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()
    if version != LATEST_VERSION:
        raise SystemExit(
            f"ERROR: {ruta} quedó en user_version={version}, "
            f"se esperaba {LATEST_VERSION}"
        )
    print(f"OK  {ruta}  (user_version={version})")


if __name__ == "__main__":
    construir(os.path.join(PROJECT_ROOT, "database.db"))
    construir(os.path.join(PROJECT_ROOT, "src", "reyger", "assets", "database.db"))
