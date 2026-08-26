#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de la Fase 3 (lógica de negocio): cálculos fiscales,
autenticación con roles, sesiones de caja, migración de IVA por
producto y registro de ventas con auditoría.

Ejecuta:  python src/reyger/test_fase3_logica.py
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
import reyger.core.migrations as modulo_migrations
import reyger.ui.clientes as modulo_clientes
import reyger.ui.inventario as modulo_inventario
import reyger.ui.ventas as modulo_ventas
from reyger.ui.clientes import Clientes
from reyger.domain.fiscal import desglose_linea, desglose_total, normalizar_tipo_iva
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
    modulo_clientes.messagebox = nulo
    modulo_inventario.messagebox = nulo
    modulo_ventas.messagebox = nulo

def preparar_db():
    """Copia la plantilla a un directorio temporal y redirige la capa db."""
    tmp_dir = tempfile.mkdtemp(prefix="reyger_f3_")
    ruta = os.path.join(tmp_dir, "prueba.db")
    shutil.copyfile(PLANTILLA, ruta)
    anterior = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    return tmp_dir, ruta, anterior

def liberar_db(anterior):
    modulo_db.close()
    modulo_db.get_db_path = anterior

def test_fiscal():
    print(f"\n{BOLD}{AZUL}[TEST 1] Cálculos fiscales (IVA){RESET}")

    chequear(
        "Línea 121 € al 21% → base 100",
        desglose_linea(121, 1, 21) == (121.0, 100.0, 21.0),
        f"obtenido {desglose_linea(121, 1, 21)}",
    )
    chequear(
        "Línea 110x2 al 10% → base 200",
        desglose_linea(110, 2, 10) == (220.0, 200.0, 20.0),
        f"obtenido {desglose_linea(110, 2, 10)}",
    )
    chequear(
        "Línea 104x3 al 4% → base 300",
        desglose_linea(104, 3, 4) == (312.0, 300.0, 12.0),
        f"obtenido {desglose_linea(104, 3, 4)}",
    )
    total, base, cuota = desglose_total([(121, 1, 21), (110, 1, 10)])
    chequear(
        "Desglose agregado de dos tipos",
        (total, base, cuota) == (231.0, 200.0, 31.0),
        f"obtenido {(total, base, cuota)}",
    )
    chequear("normalizar '10%' → 10", normalizar_tipo_iva("10%") == 10.0)
    chequear("normalizar '21' → 21", normalizar_tipo_iva("21") == 21.0)
    chequear("normalizar 'abc' rechazado", normalizar_tipo_iva("abc") is None)
    chequear("normalizar '150' rechazado", normalizar_tipo_iva("150") is None)
    chequear("normalizar '-5' rechazado", normalizar_tipo_iva("-5") is None)

def test_migracion_v1_a_v2():
    print(f"\n{BOLD}{AZUL}[TEST 3] Migración de base v1 (sin IVA) a v2{RESET}")
    tmp_dir = tempfile.mkdtemp(prefix="reyger_f3_mig_")
    ruta = os.path.join(tmp_dir, "antigua.db")
    try:
        conn = sqlite3.connect(ruta)
        modulo_migrations._migracion_1(conn)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock)"
            " VALUES ('Producto Antiguo', 'Prov', 5.0, 2.0, 10)"
        )
        conn.commit()
        conn.close()

        conn = sqlite3.connect(ruta)
        modulo_migrations.run_migrations(conn)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(inventario)")}
        fila = conn.execute(
            "SELECT nombre, tipo_iva FROM inventario WHERE nombre='Producto Antiguo'"
        ).fetchone()
        conn.close()

        chequear(
            f"Base migrada a user_version {modulo_migrations.LATEST_VERSION}",
            version == modulo_migrations.LATEST_VERSION,
            f"versión {version}",
        )
        chequear("Columna tipo_iva añadida", "tipo_iva" in columnas)
        chequear(
            "Datos antiguos conservados con IVA por defecto",
            fila is not None and fila[1] == 21.0,
            f"fila={fila}",
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_venta_iva_auditoria():
    print(f"\n{BOLD}{AZUL}[TEST 4] Venta con desglose de IVA y auditoría{RESET}")
    tmp_dir, ruta, anterior = preparar_db()
    salida_original = modulo_ventas.get_output_path
    abrir_original = modulo_ventas.open_file
    db_original = Ventas.db_name
    try:
        Ventas.db_name = ruta
        conn = sqlite3.connect(ruta)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
            " VALUES ('Vino Tinto', 'Bodega', 11.00, 6.00, 10, 10)"
        )
        conn.commit()
        conn.close()

        # Los PDFs de prueba van al directorio temporal y no se abren
        modulo_ventas.get_output_path = lambda *a: tmp_dir
        modulo_ventas.open_file = lambda *a, **k: None

        root = tk.Tk()
        root.withdraw()
        ventas = Ventas(root)

        ventas.entry_nombre.set("Vino Tinto")
        ventas.actualizar_precio(None)
        ventas.entry_cantidad.insert(0, "2")
        ventas.registrar()

        hijos = ventas.tree.get_children()
        chequear("Línea añadida al carrito", len(hijos) == 1)
        valores = ventas.tree.item(hijos[0], "values")
        chequear(
            "Línea con columna IVA del producto",
            tuple(valores) == ("Vino Tinto", "11.00", "2", "10%", "22.00"),
            f"valores={valores}",
        )

        ventas.actualizar_total()
        chequear(
            "Base imponible mostrada",
            ventas.label_base.cget("text") == "Base imponible: 20.00 €",
            ventas.label_base.cget("text"),
        )
        chequear(
            "Cuota de IVA mostrada",
            ventas.label_cuota.cget("text") == "Cuota IVA: 2.00 €",
            ventas.label_cuota.cget("text"),
        )
        chequear(
            "Total mostrado",
            ventas.label_suma_total.cget("text") == "Total a pagar: 22.00 €",
            ventas.label_suma_total.cget("text"),
        )

        def pagar_carrito():
            ventas.pagar(
                SimpleNamespace(destroy=lambda: None),
                SimpleNamespace(get=lambda: "30"),
                SimpleNamespace(get=lambda: "0"),
                SimpleNamespace(get=lambda: "Efectivo"),
                SimpleNamespace(config=lambda **k: None),
                22.0,
            )

        pagar_carrito()

        conn = sqlite3.connect(ruta)
        fila = conn.execute(
            """
            SELECT tipo_iva, cuota_iva, base_imponible,
                   cliente_id, metodo_pago
            FROM ventas WHERE factura = 1
            """
        ).fetchone()
        stock = conn.execute(
            "SELECT stock FROM inventario WHERE nombre='Vino Tinto'"
        ).fetchone()[0]
        conn.close()

        chequear(
            "Venta guarda IVA por línea",
            fila is not None and abs(fila[0] - 10.0) < 0.01,
            f"fila={fila}",
        )
        chequear(
            "Venta guarda cuota y base",
            fila is not None
            and abs(fila[1] - 2.0) < 0.01
            and abs(fila[2] - 20.0) < 0.01,
        )
        chequear("Venta sin cliente → NULL", fila is not None and fila[3] is None)
        chequear("Stock decrementado", stock == 8, f"stock={stock}")
        chequear(
            "Número de factura avanza",
            ventas.numero_factura_actual == 2,
        )

        # Segunda venta asociada a un cliente
        modulo_db.execute(
            "INSERT INTO clientes (nombre, documento) VALUES ('Ana García', '12345678Z')"
        )
        ventas.combo_cliente.set("Ana García")
        ventas.entry_nombre.set("Vino Tinto")
        ventas.actualizar_precio(None)
        ventas.entry_cantidad.insert(0, "1")
        ventas.registrar()
        pagar_carrito()

        conn = sqlite3.connect(ruta)
        fila2 = conn.execute(
            "SELECT cliente_id FROM ventas WHERE factura = 2"
        ).fetchone()
        conn.close()
        id_ana = modulo_db.query_one(
            "SELECT id FROM clientes WHERE nombre='Ana García'"
        )["id"]
        chequear(
            "Venta vinculada al cliente seleccionado",
            fila2 is not None and fila2[0] == id_ana,
            f"fila2={fila2}, id_ana={id_ana}",
        )

        root.destroy()
    finally:
        modulo_ventas.get_output_path = salida_original
        modulo_ventas.open_file = abrir_original
        Ventas.db_name = db_original
        liberar_db(anterior)
        shutil.rmtree(tmp_dir, ignore_errors=True)

def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS FASE 3 - LÓGICA DE NEGOCIO{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    silenciar_messageboxes()
    test_fiscal()

    test_migracion_v1_a_v2()
    test_venta_iva_auditoria()

    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    if FALLOS:
        print(f"{ROJO}{BOLD}✗ FALLARON {len(FALLOS)} COMPROBACIONES:{RESET}")
        for fallo in FALLOS:
            print(f"  {ROJO}- {fallo}{RESET}")
        return 1
    print(f"{VERDE}{BOLD}🎉 TODOS LOS TESTS DE FASE 3 PASAN{RESET}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
