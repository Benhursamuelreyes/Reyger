#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests del módulo business_profile: migración 6, CRUD del perfil
singleton y valores por defecto.

Ejecuta:  python -m pytest tests/test_business_profile.py -v
"""

import os
import shutil
import sqlite3
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

import reyger.core.db as modulo_db
import reyger.core.migrations as modulo_migrations

PLANTILLA = os.path.join(SCRIPT_DIR, "assets", "database.db")

VERDE = "\033[92m"
ROJO = "\033[91m"
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


def db_temporal():
    tmp_dir = tempfile.mkdtemp()
    ruta = os.path.join(tmp_dir, "perfil_test.db")
    return tmp_dir, ruta


def test_migracion6_crea_tabla():
    """La migración 6 crea la tabla business_profile con una fila por defecto."""
    print(f"\n{BOLD}{AZUL}[TEST 1] Migración 6: tabla business_profile{RESET}")
    tmp_dir, ruta = db_temporal()
    try:
        conn = sqlite3.connect(ruta)
        conn.executescript(
            """
            CREATE TABLE ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura INTEGER NOT NULL,
                nombre_articulo TEXT NOT NULL,
                valor_articulo REAL NOT NULL,
                cantidad INTEGER NOT NULL,
                subtotal REAL NOT NULL
            );
            PRAGMA user_version = 5;
            """
        )
        conn.commit()

        modulo_migrations.run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        chequear(f"user_version == {modulo_migrations.LATEST_VERSION}", version == modulo_migrations.LATEST_VERSION)

        tablas = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        chequear("tabla business_profile creada", "business_profile" in tablas)

        columnas = {r[1] for r in conn.execute("PRAGMA table_info(business_profile)")}
        for col in ("nombre", "nif", "direccion", "codigo_postal", "provincia",
                     "telefono", "email", "actividad_economica", "numero_series", "logo_path"):
            chequear(f"columna {col} existe", col in columnas)

        fila = conn.execute("SELECT * FROM business_profile WHERE id = 1").fetchone()
        chequear("fila por defecto insertada", fila is not None)
        chequear("nombre por defecto 'Mi Empresa'", fila[1] == "Mi Empresa" if fila else False)

        # Los datos existentes NO se pierden
        ventas = conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0]
        chequear("ventas originales preservadas", ventas == 0)  # tabla vacía pero existe
        conn.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_obtener_campo():
    """obtener_campo devuelve el valor de la BD o el default."""
    print(f"\n{BOLD}{AZUL}[TEST 2] obtener_campo{RESET}")
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.close()
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()

        import reyger.ui.business_profile as bp

        nombre = bp.obtener_campo("nombre")
        chequear("nombre por defecto desde plantilla", nombre == "Mi Empresa")

        nif = bp.obtener_campo("nif")
        chequear("nif vacío por defecto", nif == "")

        numero_series = bp.obtener_campo("numero_series")
        chequear("numero_series 'A' por defecto", numero_series == "A")

        try:
            bp.obtener_campo("campo_inventado")
            chequear("campo inválido lanza ValueError", False)
        except ValueError:
            chequear("campo inválido lanza ValueError", True)

    finally:
        modulo_db.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_guardar_y_obtener():
    """guardar() actualiza/crea el perfil y obtener() lo recupera."""
    print(f"\n{BOLD}{AZUL}[TEST 3] guardar() + obtener(){RESET}")
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.close()
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()

        import reyger.ui.business_profile as bp

        # Guardar datos
        resultado = bp.guardar(
            nombre="Reyger SL",
            nif="B12345678",
            direccion="Calle Mayor 1",
            codigo_postal="28001",
            provincia="Madrid",
            telefono="912345678",
            email="info@reyger.es",
            actividad_economica="Comercio al por menor",
            numero_series="B",
        )
        chequear("guardar() devuelve True", resultado is True)

        # Obtener fila completa
        perfil = bp.obtener()
        chequear("obtener() devuelve fila", perfil is not None)
        chequear("nombre guardado", perfil["nombre"] == "Reyger SL" if perfil else False)
        chequear("nif guardado", perfil["nif"] == "B12345678" if perfil else False)
        chequear("direccion guardada", perfil["direccion"] == "Calle Mayor 1" if perfil else False)
        chequear("provincia guardada", perfil["provincia"] == "Madrid" if perfil else False)
        chequear("numero_series guardado", perfil["numero_series"] == "B" if perfil else False)

        # Actualizar solo algunos campos
        bp.guardar(nombre="Reyger España SL", nif="")
        perfil2 = bp.obtener()
        chequear("nombre actualizado", perfil2["nombre"] == "Reyger España SL" if perfil2 else False)
        chequear("nif limpiado", perfil2["nif"] == "" if perfil2 else False)
        chequear("direccion sin cambios", perfil2["direccion"] == "Calle Mayor 1" if perfil2 else False)

        # Solo campos conocidos se procesan
        resultado2 = bp.guardar(campo_fantasma="no_deberia_existir")
        chequear("campo desconocido ignorado (devuelve False)", resultado2 is False)

    finally:
        modulo_db.close()
        modulo_db.get_db_path = modulo_db.get_db_path.__wrapped__ if hasattr(modulo_db.get_db_path, '__wrapped__') else modulo_db.get_db_path
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_abreviaturas():
    """nombre_empresa() y nif() son atajos convenientes."""
    print(f"\n{BOLD}{AZUL}[TEST 4] Abreviaturas nombre_empresa() y nif(){RESET}")
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.close()
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()

        import reyger.ui.business_profile as bp

        bp.guardar(nombre="Abreviaturas SA", nif="A99999999")
        chequear("nombre_empresa()", bp.nombre_empresa() == "Abreviaturas SA")
        chequear("nif()", bp.nif() == "A99999999")
    finally:
        modulo_db.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)
