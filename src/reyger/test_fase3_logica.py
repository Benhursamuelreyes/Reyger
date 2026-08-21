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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

import reyger.db as modulo_db
import reyger.auth as modulo_auth
import reyger.sesiones as modulo_sesiones
import reyger.migrations as modulo_migrations
import reyger.container as modulo_container
import reyger.clientes as modulo_clientes
import reyger.inventario as modulo_inventario
import reyger.login as modulo_login
import reyger.ventas as modulo_ventas
from reyger.auth import autenticar, cambiar_password, crear_usuario
from reyger.clientes import Clientes
from reyger.container import Container
from reyger.fiscal import desglose_linea, desglose_total, normalizar_tipo_iva
from reyger.inventario import Inventario
from reyger.login import DialogoLogin
from reyger.sesiones import abrir_sesion, cerrar_sesion, sesion_abierta
from reyger.ventas import Ventas

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
    modulo_container.messagebox = nulo
    modulo_clientes.messagebox = nulo
    modulo_inventario.messagebox = nulo
    modulo_login.messagebox = nulo
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


def todos_widgets(widget):
    yield widget
    for hijo in widget.winfo_children():
        yield from todos_widgets(hijo)


def textos_botones(raiz):
    return [
        w.cget("text")
        for w in todos_widgets(raiz)
        if isinstance(w, tk.Button)
    ]


def raiz_viva(raiz):
    try:
        return bool(raiz.winfo_exists())
    except tk.TclError:
        return False


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


def test_auth_sesiones():
    print(f"\n{BOLD}{AZUL}[TEST 2] Autenticación y sesiones de caja{RESET}")
    tmp_dir, ruta, anterior = preparar_db()
    try:
        admin = autenticar("admin", "admin")
        chequear(
            "Login admin/admin correcto",
            admin is not None and admin["rol"] == "admin",
        )
        chequear("Password incorrecta rechazada", autenticar("admin", "mala") is None)
        chequear("Usuario inexistente rechazado", autenticar("fantasma", "x") is None)

        id_cajero = crear_usuario("cajero1", "clave123", "Cajero Uno", "cajero")
        chequear("Usuario cajero creado", isinstance(id_cajero, int))
        cajero = autenticar("cajero1", "clave123")
        chequear(
            "Login del cajero nuevo",
            cajero is not None and cajero["rol"] == "cajero",
        )
        chequear("Usuario duplicado rechazado", crear_usuario("cajero1", "otra", "Dup", "cajero") is None)

        cambiar_password(id_cajero, "nueva456")
        chequear("Password antigua invalidada", autenticar("cajero1", "clave123") is None)
        chequear("Password nueva aceptada", autenticar("cajero1", "nueva456") is not None)

        rol_invalido = False
        try:
            crear_usuario("malo", "x", "Malo", "gerente")
        except ValueError:
            rol_invalido = True
        chequear("Rol inválido lanza ValueError", rol_invalido)

        sid = abrir_sesion(admin["id"])
        chequear("Sesión abierta con id", isinstance(sid, int))
        chequear("Sesión consta como abierta", sesion_abierta(sid) is not None)
        cerrar_sesion(sid)
        chequear("Sesión cerrada", sesion_abierta(sid) is None)

        # Login gráfico (camino feliz)
        root = tk.Tk()
        root.withdraw()
        capturado = {}
        dialogo = DialogoLogin(root, al_acceder=lambda u: capturado.update(u))
        dialogo.entry_usuario.insert(0, "admin")
        dialogo.entry_password.insert(0, "admin")
        dialogo.intentar_acceder()
        chequear(
            "Diálogo de login autentica y delega",
            capturado.get("rol") == "admin",
            f"capturado={capturado}",
        )
        chequear("Diálogo se cierra tras acceder", not dialogo.winfo_exists())
        root.destroy()
    finally:
        liberar_db(anterior)
        shutil.rmtree(tmp_dir, ignore_errors=True)


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

        chequear("Base migrada a user_version 2", version == 2, f"versión {version}")
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

        admin = autenticar("admin", "admin")
        sid = abrir_sesion(admin["id"])

        root = tk.Tk()
        root.withdraw()
        ventas = Ventas(
            root,
            usuario={
                "id": admin["id"],
                "sesion_id": sid,
                "nombre": admin["nombre"],
                "rol": admin["rol"],
            },
        )

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
            SELECT tipo_iva, cuota_iva, base_imponible, usuario_id, sesion_id,
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
        chequear(
            "Venta audita usuario y sesión",
            fila is not None and fila[3] == admin["id"] and fila[4] == sid,
        )
        chequear("Venta sin cliente → NULL", fila is not None and fila[5] is None)
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


def test_restricciones_roles():
    print(f"\n{BOLD}{AZUL}[TEST 5] Restricciones por rol{RESET}")
    tmp_dir, ruta, anterior = preparar_db()
    inv_original = Inventario.db_name
    try:
        Inventario.db_name = ruta
        root = tk.Tk()
        root.withdraw()

        cont_cajero = Container(
            root, None, usuario={"nombre": "Cajero", "rol": "cajero"}
        )
        botones = textos_botones(cont_cajero)
        chequear(
            "Cajero no ve el botón Ajustes",
            all("Ajustes" not in t for t in botones),
            f"botones={botones}",
        )
        chequear(
            "Cajero ve el botón Cerrar sesión",
            any("Cerrar sesión" in t for t in botones),
        )

        cont_admin = Container(
            root, None, usuario={"nombre": "Admin", "rol": "admin"}
        )
        botones_admin = textos_botones(cont_admin)
        chequear(
            "Admin ve el botón Ajustes",
            any(t == "Ajustes" for t in botones_admin),
        )

        inv_cajero = Inventario(root, usuario={"nombre": "C", "rol": "cajero"})
        botones_inv = textos_botones(inv_cajero)
        chequear(
            "Cajero no puede eliminar productos",
            all("Eliminar" not in t for t in botones_inv),
            f"botones={botones_inv}",
        )

        modulo_db.execute(
            "INSERT INTO clientes (nombre) VALUES ('Cliente Protegido')"
        )
        cli_cajero = Clientes(root, usuario={"nombre": "C", "rol": "cajero"})
        cli_cajero.eliminar()
        cuenta = modulo_db.query_one("SELECT COUNT(*) AS n FROM clientes")["n"]
        chequear("eliminar() de clientes bloqueado para cajero", cuenta == 1)

        cli_admin = Clientes(
            root, usuario={"nombre": "A", "rol": "admin"}
        )
        cli_admin.tree.selection_set(cli_admin.tree.get_children()[0])
        cli_admin.eliminar()
        cuenta = modulo_db.query_one("SELECT COUNT(*) AS n FROM clientes")["n"]
        chequear("Admin sí puede eliminar clientes", cuenta == 0)

        root.destroy()
    finally:
        Inventario.db_name = inv_original
        liberar_db(anterior)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_login_agota_intentos():
    print(f"\n{BOLD}{AZUL}[TEST 6] Login agota intentos y cierra la app{RESET}")
    tmp_dir, ruta, anterior = preparar_db()
    try:
        root = tk.Tk()
        root.withdraw()
        dialogo = DialogoLogin(root, al_acceder=lambda u: None)
        for _ in range(3):
            if not raiz_viva(root):
                break
            dialogo.entry_usuario.insert(0, "admin")
            dialogo.entry_password.insert(0, "malisima")
            dialogo.intentar_acceder()
            if not raiz_viva(root):
                break
            dialogo.entry_usuario.delete(0, "end")
            dialogo.entry_password.delete(0, "end")
        chequear(
            "Tras 3 fallos la aplicación se cierra",
            not raiz_viva(root),
        )
    finally:
        liberar_db(anterior)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS FASE 3 - LÓGICA DE NEGOCIO{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    silenciar_messageboxes()
    test_fiscal()
    test_auth_sesiones()
    test_migracion_v1_a_v2()
    test_venta_iva_auditoria()
    test_restricciones_roles()
    test_login_agota_intentos()

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
