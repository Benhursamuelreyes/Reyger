#!/usr/bin/env python
"""Regenera la plantilla database.db aplicando todas las migraciones.

Genera ``src/reyger/assets/database.db`` (la plantilla empaquetada con la
app, que se copia en el primer arranque) con ``PRAGMA user_version`` al día.
Hay que ejecutarlo tras añadir una migración; ``tests/test_fase1_db.py``
falla si la plantilla queda atrasada.

Uso:  python scripts/build_template_db.py [ruta_destino]
"""

import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from reyger.core.migrations import LATEST_VERSION, run_migrations  # noqa: E402


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
    construir(
        sys.argv[1] if len(sys.argv) > 1
        else os.path.join(PROJECT_ROOT, "src", "reyger", "assets", "database.db")
    )
