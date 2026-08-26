#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de la Fase 2 (interfaz): validadores fiscales, CRUD de clientes,
selector de proveedores y ventanas redimensionables.

Ejecuta:  python src/reyger/test_fase2_ui.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

import reyger.core.db as modulo_db
import reyger.ui.clientes as modulo_clientes
import reyger.ui.inventario as modulo_inventario
import reyger.ui.ventas as modulo_ventas
from reyger.ui.clientes import Clientes, validar_documento
from reyger.container import Container
from reyger.ui.inventario import Inventario
from reyger.ui.ui import GEOMETRIA_MODULO, GEOMETRIA_PRINCIPAL, MINIMO_MODULO
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
    modulo_clientes.messagebox = nulo


def db_temporal():
    tmp_dir = tempfile.mkdtemp(prefix="reyger_f2_")
    ruta = os.path.join(tmp_dir, "prueba.db")
    shutil.copyfile(PLANTILLA, ruta)
    return tmp_dir, ruta


def test_validadores():
    print(f"\n{BOLD}{AZUL}[TEST 1] Validación NIF/NIE/CIF{RESET}")
    casos_validos = [
        ("12345678Z", "NIF"),
        ("X1234567L", "NIE"),
        ("Y1234567X", "NIE"),
        ("A12345674", "CIF"),
        ("B1234567D", "CIF"),
        ("P1234567D", "CIF"),
    ]
    for doc, tipo in casos_validos:
        valido, detectado = validar_documento(doc)
        chequear(f"{doc} es {tipo} válido", valido and detectado == tipo,
                 f"obtenido ({valido}, {detectado})")
    casos_invalidos = [
        "12345678A",   # letra NIF incorrecta
        "X1234567A",   # letra NIE incorrecta
        "A12345675",   # control CIF incorrecto
        "P12345674",   # CIF tipo P exige letra de control
        "12345",       # longitud incorrecta
        "",            # vacío
    ]
    for doc in casos_invalidos:
        valido, _ = validar_documento(doc)
        chequear(f"'{doc}' rechazado", not valido)


def test_crud_clientes():
    print(f"\n{BOLD}{AZUL}[TEST 2] CRUD de clientes{RESET}")
    silenciar_messageboxes()
    tmp_dir, ruta = db_temporal()
    modulo_db.close()
    modulo_db.get_db_path = lambda: ruta
    try:
        root = tk.Tk()
        root.withdraw()
        clientes = Clientes(root)

        clientes.campos["nombre"].insert(0, "Ana García")
        clientes.campos["tipo_documento"].set("NIF")
        clientes.campos["documento"].insert(0, "12345678Z")
        clientes.campos["telefono"].insert(0, "600111222")
        clientes.campos["email"].insert(0, "ana@example.com")
        clientes.guardar()

        fila = modulo_db.query_one(
            "SELECT nombre, documento, telefono FROM clientes WHERE nombre='Ana García'"
        )
        chequear("Cliente insertado", fila is not None)
        if fila:
            chequear(
                "Datos fiscales guardados",
                fila["documento"] == "12345678Z" and fila["telefono"] == "600111222",
            )

        clientes.cargar_clientes()
        hijos = clientes.tree.get_children()
        chequear("Cliente listado en el Treeview", len(hijos) == 1)
        clientes.tree.selection_set(hijos[0])
        clientes.al_seleccionar()
        chequear(
            "Selección carga el formulario",
            clientes.cliente_id_actual is not None
            and clientes.campos["nombre"].get() == "Ana García",
        )

        clientes.campos["nombre"].delete(0, "end")
        clientes.campos["nombre"].insert(0, "Ana García López")
        id_editado = clientes.cliente_id_actual
        clientes.guardar()
        fila = modulo_db.query_one(
            "SELECT nombre FROM clientes WHERE id=?", (id_editado,)
        )
        chequear("Actualización del cliente", fila and fila["nombre"] == "Ana García López")

        clientes.tree.selection_set(clientes.tree.get_children()[0])
        clientes.al_seleccionar()
        clientes.eliminar()
        cuenta = modulo_db.query_one("SELECT COUNT(*) AS n FROM clientes")["n"]
        chequear("Cliente eliminado", cuenta == 0)

        # Documento inválido no se guarda
        clientes.campos["nombre"].insert(0, "Cliente Malo")
        clientes.campos["documento"].insert(0, "12345678A")
        clientes.guardar()
        cuenta = modulo_db.query_one("SELECT COUNT(*) AS n FROM clientes")["n"]
        chequear("Documento inválido bloqueado", cuenta == 0)

        root.destroy()
    finally:
        modulo_db.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_proveedores_inventario():
    print(f"\n{BOLD}{AZUL}[TEST 3] Selector de proveedores en Inventario{RESET}")
    tmp_dir, ruta = db_temporal()
    anterior_conexion = modulo_db._conexion
    modulo_db._conexion = None
    original_get_db_path = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    try:
        conn = sqlite3.connect(ruta)
        conn.execute(
            "INSERT INTO proveedores (nombre, cif) VALUES ('Ferroviejo S.L.', 'B12345674')"
        )
        conn.commit()
        conn.close()

        root = tk.Tk()
        root.withdraw()
        inventario = Inventario(root)

        chequear(
            "Combobox cargado con proveedores",
            "Ferroviejo S.L." in inventario.proveedor["values"],
        )

        inventario.nombre.insert(0, "Tornillo M8")
        inventario.proveedor.set("Ferroviejo S.L.")
        inventario.precio.insert(0, "0.10")
        inventario.costo.insert(0, "0.05")
        inventario.stock.insert(0, "500")
        inventario.registrar()

        conn = sqlite3.connect(ruta)
        fila = conn.execute(
            """
            SELECT i.proveedor_id, p.nombre FROM inventario i
            JOIN proveedores p ON p.id = i.proveedor_id
            WHERE i.nombre = 'Tornillo M8'
            """
        ).fetchone()
        conn.close()
        chequear(
            "Producto vinculado a proveedor por FK",
            fila is not None and fila[1] == "Ferroviejo S.L.",
        )

        root.destroy()
    finally:
        modulo_db._conexion = anterior_conexion
        modulo_db.get_db_path = original_get_db_path
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_ventanas_redimensionables():
    print(f"\n{BOLD}{AZUL}[TEST 4] Ventanas y diálogos redimensionables{RESET}")
    tmp_dir, ruta = db_temporal()
    anterior_conexion = modulo_db._conexion
    modulo_db._conexion = None
    original_get_db_path = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    try:
        root = tk.Tk()
        root.withdraw()
        ventas = Ventas(root)

        ventas.tree.insert("", "end", values=("Producto X", "10.00", 2, "21%", "20.00"))
        ventas.abrir_ventana_paga()
        toplevels = [
            w for w in ventas.winfo_children() if isinstance(w, tk.Toplevel)
        ]
        chequear("Diálogo de pago abierto", len(toplevels) == 1,
                 f"encontrados {len(toplevels)}")
        if toplevels:
            pago = toplevels[0]
            chequear(
                "Diálogo de pago redimensionable",
                all(int(v) for v in pago.resizable()),
            )

        # Conmutación de campos Efectivo/Tarjeta vía grid
        labels = [w for w in pago.winfo_children() if isinstance(w, tk.Label)]
        entries = [w for w in pago.winfo_children() if isinstance(w, ttk.Entry)]
        label_tarjeta = next(w for w in labels if "tarjeta" in w.cget("text").lower())
        entry_tarjeta = entries[-1]
        var_metodo = tk.StringVar(value="Tarjeta")
        label_efectivo = next(w for w in labels if "efectivo" in w.cget("text").lower())
        entry_efectivo = entries[0]
        ventas._actualizar_campos_pago(
            var_metodo, label_efectivo, entry_efectivo, label_tarjeta, entry_tarjeta
        )
        chequear(
            "Campos conmutan con grid (Tarjeta visible)",
            bool(label_tarjeta.grid_info())
            and not label_efectivo.grid_info(),
        )
        pago.destroy()

        ventas.abrir_ventana_factura()
        toplevels = [
            w for w in ventas.winfo_children() if isinstance(w, tk.Toplevel)
        ]
        chequear("Diálogo de facturas abierto", len(toplevels) == 1,
                 f"encontrados {len(toplevels)}")
        for w in toplevels:
            w.destroy()

        root.destroy()
    finally:
        modulo_db._conexion = anterior_conexion
        modulo_db.get_db_path = original_get_db_path
        shutil.rmtree(tmp_dir, ignore_errors=True)

    chequear(
        "Constantes de UI definidas",
        GEOMETRIA_PRINCIPAL == "1280x800"
        and GEOMETRIA_MODULO == "1280x800"
        and MINIMO_MODULO == (1100, 700),
    )
    chequear("Menú expone la sección Clientes", hasattr(Container, "clientes"))


def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS FASE 2 - INTERFAZ / TKINTER{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    silenciar_messageboxes()
    test_validadores()
    test_crud_clientes()
    test_proveedores_inventario()
    test_ventanas_redimensionables()

    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    if FALLOS:
        print(f"{ROJO}{BOLD}✗ FALLARON {len(FALLOS)} COMPROBACIONES:{RESET}")
        for fallo in FALLOS:
            print(f"  {ROJO}- {fallo}{RESET}")
        return 1
    print(f"{VERDE}{BOLD}🎉 TODOS LOS TESTS DE FASE 2 PASAN{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
