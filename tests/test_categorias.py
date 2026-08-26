#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de categorias de productos: migracion 3, CRUD con reglas de
General, reasignacion al eliminar, filtro en inventario y botones
rapidos en ventas.

Ejecuta:  python src/reyger/test_categorias.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import tkinter as tk
from types import SimpleNamespace

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

import reyger.core.db as modulo_db
import reyger.ui.categorias as modulo_categorias
import reyger.core.migrations as modulo_migrations
import reyger.ui.ajustes as modulo_ajustes
import reyger.ui.inventario as modulo_inventario
import reyger.ui.ventas as modulo_ventas
from reyger.ui.categorias import (
    GENERAL,
    categoria_de_producto,
    crear,
    crear as crear_categoria,
    eliminar,
    id_general,
    listar,
    nombres,
    productos_por_categoria,
    renombrar,
)
from reyger.ui.inventario import Inventario
from reyger.ui.ventas import Ventas

VERDE = "\033[92m"
ROJO = "\033[91m"
AZUL = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []
PLANTILLA = os.path.join(SCRIPT_DIR, "assets", "database.db")


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" — {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def silenciar_messageboxes():
    """Evita diálogos bloqueantes durante los tests."""
    nulo = SimpleNamespace(
        showinfo=lambda *a, **k: None,
        showwarning=lambda *a, **k: None,
        showerror=lambda *a, **k: None,
        askyesno=lambda *a, **k: True,
    )
    modulo_inventario.messagebox = nulo
    modulo_ventas.messagebox = nulo
    modulo_ajustes.messagebox = nulo


def db_temporal():
    tmp_dir = tempfile.mkdtemp()
    ruta = os.path.join(tmp_dir, "categorias.db")
    return tmp_dir, ruta


def test_migracion3():
    print(f"\n{BOLD}{AZUL}[TEST 1] Migracion 3: tabla categorias y reasignacion{RESET}")
    tmp_dir, ruta_vieja = db_temporal()
    try:
        # BD antigua (v2) con un producto sin categoria
        conn = sqlite3.connect(ruta_vieja)
        conn.executescript(
            """
            CREATE TABLE inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                proveedor TEXT NOT NULL,
                precio REAL NOT NULL,
                costo REAL NOT NULL,
                stock INTEGER NOT NULL,
                proveedor_id INTEGER,
                tipo_iva REAL NOT NULL DEFAULT 21
            );
            INSERT INTO inventario (nombre, proveedor, precio, costo, stock)
            VALUES ('Manzana', 'Prov', 1.5, 0.8, 10);
            PRAGMA user_version = 2;
            """
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(ruta_vieja)
        modulo_migrations.run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        chequear(
            f"user_version == {modulo_migrations.LATEST_VERSION} tras migrar",
            version == modulo_migrations.LATEST_VERSION,
        )
        tablas = {
            fila[0]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        chequear("tabla categorias creada", "categorias" in tablas)
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(inventario)")}
        chequear("inventario.categoria_id añadida", "categoria_id" in columnas)
        general = conn.execute(
            "SELECT id FROM categorias WHERE nombre = 'General'"
        ).fetchone()
        chequear("categoria General sembrada", general is not None)
        asignada = conn.execute(
            "SELECT categoria_id FROM inventario WHERE nombre = 'Manzana'"
        ).fetchone()
        chequear(
            "producto existente reasignado a General",
            asignada is not None and asignada[0] == general[0],
        )
        conn.close()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_crud_categorias():
    print(f"\n{BOLD}{AZUL}[TEST 2] CRUD de categorias y reglas de General{RESET}")
    silenciar_messageboxes()
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()

        chequear("General existe en plantilla", GENERAL in nombres())
        id_frutas = crear_categoria("Frutas")
        chequear("crear Frutas devuelve id", isinstance(id_frutas, int))
        chequear("crear duplicada devuelve None", crear_categoria("Frutas") is None)
        chequear("nombre vacio lanza ValueError", _lanza_valueerror(lambda: crear_categoria("   ")))
        chequear("nombres ordenados con General primero", nombres()[0] == GENERAL)

        chequear("renombrar Frutas -> Carnes rojas", renombrar(id_frutas, "Carnes rojas"))
        chequear("renombrar a nombre existente falla", not renombrar(id_frutas, GENERAL))
        chequear("renombrar General lanza ValueError", _lanza_valueerror(lambda: renombrar(id_general(), "Otra")))

        # Producto vinculado a la categoria que se elimina
        from reyger.ui.inventario import Inventario

        root = tk.Tk()
        root.withdraw()
        inv_db = ruta
        Inventario.db_name = inv_db
        inventario = Inventario(root)
        inventario.nombre.insert(0, "Pera")
        inventario.proveedor.set("Prov")
        inventario.precio.insert(0, "2")
        inventario.costo.insert(0, "1")
        inventario.stock.insert(0, "5")
        inventario.categoria.set("Carnes rojas")
        inventario.registrar()
        fila = modulo_db.query_one(
            "SELECT categoria_id FROM inventario WHERE nombre='Pera'"
        )
        chequear("producto guardado con su categoria", fila and fila["categoria_id"] == id_frutas)

        chequear("eliminar categoria", eliminar(id_frutas))
        fila = modulo_db.query_one(
            "SELECT categoria_id FROM inventario WHERE nombre='Pera'"
        )
        chequear(
            "producto pasa a General al eliminar categoria",
            fila and fila["categoria_id"] == id_general(),
        )
        chequear("eliminar General rechazado", not eliminar(id_general()))
        root.destroy()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _lanza_valueerror(funcion):
    try:
        funcion()
    except ValueError:
        return True
    return False


def test_mapas_y_filtro_ventas():
    print(f"\n{BOLD}{AZUL}[TEST 3] Mapas por categoria y botones de ventas{RESET}")
    silenciar_messageboxes()
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()
        Ventas.db_name = ruta

        id_frutas = crear_categoria("Frutas")
        id_info = crear_categoria("Informática")
        with sqlite3.connect(ruta) as conn:
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva, categoria_id)"
                " VALUES ('Manzana','P',1.5,0.8,10,21,?)",
                (id_frutas,),
            )
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva, categoria_id)"
                " VALUES ('Ratón','P',20,12,4,21,?)",
                (id_info,),
            )
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
                " VALUES ('SinCategoria','P',3,2,7,21)"
            )
            conn.commit()

        mapa = productos_por_categoria()
        chequear("mapa agrupa Frutas", mapa.get("Frutas") == ["Manzana"])
        chequear("mapa agrupa Informática", mapa.get("Informática") == ["Ratón"])
        chequear(
            "producto sin categoria cae en General",
            mapa.get(GENERAL) == ["SinCategoria"],
        )
        chequear("categoria_de_producto acierta", categoria_de_producto("Manzana") == "Frutas")
        chequear(
            "categoria_de_producto sin vinculo -> General",
            categoria_de_producto("SinCategoria") == GENERAL,
        )

        root = tk.Tk()
        root.withdraw()
        ventas = Ventas(root)
        chequear(
            "botones de categoria creados",
            set(ventas.botones_categoria) >= {"Todos", "Frutas", "Informática"},
        )
        ventas.filtrar_por_categoria("Frutas")
        chequear(
            "filtro Frutas deja solo Manzana",
            list(ventas.entry_nombre["values"]) == ["Manzana"],
        )
        ventas.filtrar_por_categoria("Todos")
        chequear(
            "Todos restaura el listado completo",
            len(list(ventas.entry_nombre["values"])) == 3,
        )
        btn_activo = ventas.botones_categoria["Todos"].cget("bg")
        chequear("boton activo resaltado", btn_activo != ventas.botones_categoria["Frutas"].cget("bg"))
        root.destroy()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=False)


def test_inventario_filtro_y_columna():
    print(f"\n{BOLD}{AZUL}[TEST 4] Filtro y columna Categoría en inventario{RESET}")
    silenciar_messageboxes()
    tmp_dir, ruta = db_temporal()
    try:
        shutil.copyfile(PLANTILLA, ruta)
        modulo_db.get_db_path = lambda: ruta
        modulo_db.close()
        Inventario.db_name = ruta

        id_frutas = crear_categoria("Frutas")
        with sqlite3.connect(ruta) as conn:
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva, categoria_id)"
                " VALUES ('Plátano','P',1.2,0.6,9,21,?)",
                (id_frutas,),
            )
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
                " VALUES ('Tornillo','P',0.1,0.05,100,21)"
            )
            conn.commit()

        root = tk.Tk()
        root.withdraw()
        inventario = Inventario(root)
        valores_combo = list(inventario.filtro_categoria["values"])
        chequear(
            "combo filtro tiene Todas + categorias",
            valores_combo[:3] == ["Todas", GENERAL, "Frutas"],
        )

        inventario.filtro_categoria.set("Frutas")
        inventario.aplicar_filtro()
        hijos = inventario.tre.get_children()
        nombres_visibles = [inventario.tre.item(h)["values"][1] for h in hijos]
        chequear("filtro muestra solo Plátano", nombres_visibles == ["Plátano"])
        columna_cat = inventario.tre.item(hijos[0])["values"][7]
        chequear("columna Categoría rellena", columna_cat == "Frutas")

        inventario.filtro_categoria.set("Todas")
        inventario.aplicar_filtro()
        chequear("Todas muestra los dos productos", len(inventario.tre.get_children()) == 2)
        root.destroy()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS - CATEGORIAS DE PRODUCTOS{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    silenciar_messageboxes()
    test_migracion3()
    test_crud_categorias()
    test_mapas_y_filtro_ventas()
    test_inventario_filtro_y_columna()

    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    if FALLOS:
        print(f"{ROJO}{BOLD}✗ FALLARON {len(FALLOS)} COMPROBACIONES:{RESET}")
        for fallo in FALLOS:
            print(f"  {ROJO}- {fallo}{RESET}")
        return 1
    print(f"{VERDE}{BOLD}🎉 TODOS LOS TESTS DE CATEGORIAS PASAN{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
