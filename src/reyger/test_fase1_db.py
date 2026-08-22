#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de la Fase 1 (base de datos): plantilla, migraciones y capa db.

Ejecuta:  python src/reyger/test_fase1_db.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

from reyger import db as modulo_db
from reyger.migrations import LATEST_VERSION, run_migrations

VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[93m"
AZUL = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" — {detalle}" if detalle else ""))
        FALLOS.append(nombre)


TABLAS_ESPERADAS = {
    "ventas", "inventario", "clientes", "proveedores",
    "facturas_borradores", "facturas_borradores_productos",
    "presupuestos", "presupuestos_productos",
    "albaranes", "albaranes_productos",
    "facturas_verifactu", "facturas_verifactu_productos",
}


def columnas(conn, tabla):
    return [fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")]


def test_plantilla():
    print(f"\n{BOLD}{AZUL}[TEST 1] Plantilla empaquetada (assets/database.db){RESET}")
    ruta = os.path.join(SCRIPT_DIR, "assets", "database.db")
    chequear("Plantilla existe", os.path.exists(ruta))
    conn = sqlite3.connect(ruta)
    tablas = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    faltan = TABLAS_ESPERADAS - tablas
    chequear("Tablas completas", not faltan, f"faltan: {sorted(faltan)}")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    chequear(
        f"user_version == {LATEST_VERSION}", version == LATEST_VERSION,
        f"obtenido {version}",
    )
    chequear(
        "ventas con columnas de IVA",
        all(c in columnas(conn, "ventas") for c in (
            "cliente_id", "tipo_iva", "cuota_iva", "base_imponible")),
    )
    chequear(
        "inventario con proveedor_id",
        "proveedor_id" in columnas(conn, "inventario"),
    )
    chequear(
        "Sin tablas de usuarios ni sesiones",
        not ({"usuarios", "sesiones_caja"} & tablas),
    )
    conn.close()


def test_migracion_desde_vieja():
    print(f"\n{BOLD}{AZUL}[TEST 2] Migración sobre base antigua sin perder datos{RESET}")
    tmp = os.path.join(tempfile.mkdtemp(prefix="reyger_mig_"), "vieja.db")
    conn = sqlite3.connect(tmp)
    conn.executescript(
        """
        CREATE TABLE ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura INTEGER NOT NULL,
            nombre_articulo TEXT NOT NULL,
            valor_articulo REAL NOT NULL,
            cantidad INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            metodo_pago TEXT DEFAULT 'Efectivo',
            cantidad_efectivo REAL DEFAULT 0,
            cantidad_tarjeta REAL DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            stock INTEGER NOT NULL
        );
        CREATE TABLE presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_presupuesto TEXT UNIQUE NOT NULL,
            cliente_nombre TEXT NOT NULL,
            cliente_email TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            base_imponible REAL DEFAULT 0,
            tipo_iva INTEGER DEFAULT 21,
            total_iva REAL DEFAULT 0,
            total REAL DEFAULT 0,
            estado TEXT DEFAULT 'Pendiente',
            notas TEXT
        );
        INSERT INTO ventas (factura, nombre_articulo, valor_articulo, cantidad, subtotal)
        VALUES (1, 'Producto antiguo', 10.5, 2, 21.0);
        INSERT INTO inventario (nombre, proveedor, precio, costo, stock)
        VALUES ('Tornillo', 'Ferroviejo', 0.10, 0.05, 1000);
        INSERT INTO presupuestos (numero_presupuesto, cliente_nombre, total)
        VALUES ('PRE-0001', 'Cliente histórico', 121.0);
        """
    )
    conn.commit()

    run_migrations(conn)

    tablas = {
        fila[0]
        for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    faltan = TABLAS_ESPERADAS - tablas
    chequear("Tablas nuevas creadas sobre la vieja", not faltan, f"faltan: {sorted(faltan)}")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    chequear(f"user_version actualizada a {LATEST_VERSION}", version == LATEST_VERSION)
    chequear(
        "Columnas añadidas a ventas",
        all(c in columnas(conn, "ventas") for c in (
            "cliente_id", "tipo_iva", "cuota_iva", "base_imponible")),
    )
    chequear("cliente_id añadido a presupuestos", "cliente_id" in columnas(conn, "presupuestos"))
    venta = conn.execute(
        "SELECT nombre_articulo, subtotal FROM ventas WHERE nombre_articulo='Producto antiguo'"
    ).fetchone()
    chequear("Datos de ventas preservados", venta is not None and venta[1] == 21.0)
    inv = conn.execute(
        "SELECT stock FROM inventario WHERE nombre='Tornillo'"
    ).fetchone()
    chequear("Datos de inventario preservados", inv is not None and inv[0] == 1000)
    pres = conn.execute(
        "SELECT cliente_nombre FROM presupuestos WHERE numero_presupuesto='PRE-0001'"
    ).fetchone()
    chequear("Datos de presupuestos preservados", pres is not None)
    chequear(
        "Tablas de login eliminadas en la base migrada",
        not ({"usuarios", "sesiones_caja"} & tablas),
    )
    conn.close()
    shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)


def test_capa_db():
    print(f"\n{BOLD}{AZUL}[TEST 3] Capa de acceso db.py{RESET}")
    tmp_dir = tempfile.mkdtemp(prefix="reyger_db_")
    ruta_tmp = os.path.join(tmp_dir, "prueba.db")
    shutil.copyfile(os.path.join(SCRIPT_DIR, "assets", "database.db"), ruta_tmp)

    modulo_db.close()
    modulo_db.get_db_path = lambda: ruta_tmp  # redirige la conexión compartida

    try:
        nuevo_id = modulo_db.execute(
            "INSERT INTO clientes (nombre, documento) VALUES (?, ?)",
            ("Cliente de prueba", "12345678Z"),
        )
        chequear("execute() devuelve lastrowid", nuevo_id == 1)
        fila = modulo_db.query_one(
            "SELECT nombre FROM clientes WHERE id = ?", (nuevo_id,)
        )
        chequear("query_one() recupera la fila", fila is not None and fila["nombre"] == "Cliente de prueba")
        filas = modulo_db.query("SELECT id FROM clientes")
        chequear("query() devuelve lista", isinstance(filas, list) and len(filas) == 1)

        try:
            with modulo_db.transaccion() as conn:
                conn.execute(
                    "INSERT INTO inventario (nombre, proveedor, precio, costo, stock)"
                    " VALUES ('X', 'P', 1, 0.5, 10)"
                )
                raise RuntimeError("provocado")
        except RuntimeError:
            pass
        cuenta = modulo_db.query_one("SELECT COUNT(*) AS n FROM inventario")
        chequear("transaccion() hace rollback al fallar", cuenta["n"] == 0)

        try:
            modulo_db.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
                " proveedor_id) VALUES ('Y', 'P', 1, 0.5, 1, 99999)"
            )
            fk_ok = False
        except sqlite3.IntegrityError:
            fk_ok = True
        chequear("Claves foráneas activadas", fk_ok)
    finally:
        modulo_db.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS FASE 1 - BASE DE DATOS{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    test_plantilla()
    test_migracion_desde_vieja()
    test_capa_db()

    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    if FALLOS:
        print(f"{ROJO}{BOLD}✗ FALLARON {len(FALLOS)} COMPROBACIONES:{RESET}")
        for fallo in FALLOS:
            print(f"  {ROJO}- {fallo}{RESET}")
        return 1
    print(f"{VERDE}{BOLD}🎉 TODOS LOS TESTS DE FASE 1 PASAN{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
