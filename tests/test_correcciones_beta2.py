"""Tests de las correcciones tras la beta.2 (reporte de campo).

Cubre los cuatro arreglos: código de barras en el formulario de
productos, selector de categorías con creación en caliente, logo y
tamaños del ticket térmico, y la ventana de albaranes conectada a BD.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

AZUL = "\033[94m"
VERDE = "\033[92m"
ROJO = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []
PLANTILLA = os.path.join(SCRIPT_DIR, "assets", "database.db")


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" -> {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def bombear_hasta(root, condicion, segundos=30):
    """Bombea eventos hasta que se cumpla la condición o venza el plazo."""
    fin = time.time() + segundos
    while time.time() < fin:
        root.update()
        if condicion():
            return True
        time.sleep(0.02)
    return False


def preparar_bd(prefijo):
    tmpdir = tempfile.mkdtemp(prefix=prefijo)
    bd = os.path.join(tmpdir, "database.db")
    shutil.copyfile(PLANTILLA, bd)
    return tmpdir, bd


def test_formulario_producto_codigo_barras():
    print(f"\n{BOLD}{AZUL}[TEST 1] Código de barras en el alta de productos{RESET}")
    from tkinter import messagebox

    tmpdir, bd = preparar_bd("reyger_fix_prod_")
    from reyger import inventario as mod_inventario
    from reyger import db as mod_db

    mod_db.get_db_path = lambda: bd
    mod_db._conexion = None
    mod_inventario.Inventario.db_name = bd

    with patch.object(messagebox, "showinfo"), patch.object(messagebox, "showwarning"):
        root = tk.Tk()
        root.withdraw()
        marco = mod_inventario.Inventario(root)
        root.update()

        chequear("El alta tiene Entry «Código de barras»",
                 hasattr(marco, "codigo_barras"))

        marco.nombre.insert(0, "Coca Cola 600ml")
        marco.proveedor.set("Distribuidora Central")
        marco.precio.insert(0, "18.50")
        marco.costo.insert(0, "12.00")
        marco.stock.insert(0, "10")
        marco.codigo_barras.insert(0, "7501234567890")
        marco.registrar()
        root.update()

        con = sqlite3.connect(bd)
        fila = con.execute(
            "SELECT codigo_barras FROM inventario WHERE nombre = ?",
            ("Coca Cola 600ml",),
        ).fetchone()
        con.close()
        chequear("El código se guarda en la BD",
                 fila is not None and fila[0] == "7501234567890", str(fila))
        chequear("El campo se limpia tras registrar",
                 marco.codigo_barras.get() == "")

        # Duplicado: no debe insertarse un segundo producto
        marco.nombre.insert(0, "Otro producto")
        marco.proveedor.set("Distribuidora Central")
        marco.precio.insert(0, "1")
        marco.costo.insert(0, "0.5")
        marco.stock.insert(0, "1")
        marco.codigo_barras.insert(0, "7501234567890")
        marco.registrar()
        root.update()
        con = sqlite3.connect(bd)
        total = con.execute(
            "SELECT COUNT(*) FROM inventario WHERE codigo_barras = ?",
            ("7501234567890",),
        ).fetchone()[0]
        con.close()
        chequear("Un código duplicado es rechazado", total == 1, f"total={total}")

        root.destroy()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_crear_categoria_en_caliente():
    print(f"\n{BOLD}{AZUL}[TEST 2] Selector de categorías y creación en caliente{RESET}")
    from tkinter import messagebox
    from reyger import inventario as mod_inventario
    from reyger import categorias as gestor_categorias
    from reyger import db as mod_db

    tmpdir, bd = preparar_bd("reyger_fix_cat_")
    mod_db.get_db_path = lambda: bd
    mod_db._conexion = None
    mod_inventario.Inventario.db_name = bd

    with patch.object(messagebox, "showinfo"), patch.object(messagebox, "showwarning"):
        root = tk.Tk()
        root.withdraw()
        marco = mod_inventario.Inventario(root)
        root.update()

        chequear("Combobox de categoría es readonly",
                 str(marco.categoria.cget("state")) == "readonly")

        hijos = marco.nametowidget(marco.categoria.winfo_parent()).winfo_children()
        hay_boton = any(
            isinstance(h, tk.Button) and h.cget("text") == "➕" for h in hijos
        )
        chequear("Hay botón ➕ junto al selector de categorías", hay_boton)

        nueva_id = gestor_categorias.crear("Bebidas")
        chequear("gestor_categorias.crear devuelve id", bool(nueva_id))
        marco.cargar_categorias()
        marco.categoria.set("Bebidas")
        chequear("La categoría nueva aparece en el selector",
                 "Bebidas" in list(marco.categoria["values"]))

        # La categoría elegida queda asignada al producto registrado
        marco.nombre.insert(0, "Agua mineral")
        marco.proveedor.set("Distribuidora Central")
        marco.precio.insert(0, "0.60")
        marco.costo.insert(0, "0.30")
        marco.stock.insert(0, "50")
        marco.registrar()
        root.update()
        con = sqlite3.connect(bd)
        categoria = con.execute(
            "SELECT c.nombre FROM inventario i"
            " JOIN categorias c ON c.id = i.categoria_id"
            " WHERE i.nombre = 'Agua mineral'"
        ).fetchone()
        con.close()
        chequear("El producto se registra con su categoría",
                 categoria is not None and categoria[0] == "Bebidas",
                 str(categoria))

        root.destroy()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_ticket_logo_y_tamanos():
    print(f"\n{BOLD}{AZUL}[TEST 3] Ticket térmico: tamaños y logo rasterizado{RESET}")
    from reyger.impresion_termica import (
        construir_ticket_venta,
        _rasterizar_logo,
    )

    datos = construir_ticket_venta(
        "F-1", "24/08/2026", [("Tornillo", 0.5, 2, 1.0)], 1.0,
        empresa="Ferretería Reyger",
        logo=os.path.join(SCRIPT_DIR, "assets", "img", "logo.png"),
    )
    chequear("Encabezado más grande que el cuerpo", b"\x1d!\x22" in datos)
    chequear("Cuerpo por defecto «muy grande»", b"\x1d!\x11" in datos)
    idx = datos.find(b"\x1dv\x00")
    chequear("El ticket incluye el logo rasterizado (GS v 0)", idx != -1)
    if idx != -1:
        ancho_bytes = datos[idx + 3] | (datos[idx + 4] << 8)
        alto = datos[idx + 5] | (datos[idx + 6] << 8)
        chequear("El raster cabe en el cabezal de 576 puntos",
                 ancho_bytes * 8 <= 576 and alto <= 192,
                 f"{ancho_bytes * 8}x{alto}")

    datos58 = construir_ticket_venta(
        "F-2", "hoy", [("X", 1, 1, 1)], 1, ancho=32,
        logo=os.path.join(SCRIPT_DIR, "assets", "img", "logo.png"),
    )
    i58 = datos58.find(b"\x1dv\x00")
    ancho58 = datos58[i58 + 3] | (datos58[i58 + 4] << 8)
    chequear("En papel de 58 mm el logo cabe en 384 puntos", ancho58 * 8 <= 384)

    raster = _rasterizar_logo(
        os.path.join(SCRIPT_DIR, "assets", "img", "logo.png"), 576
    )
    chequear("Rasterizar sin Pillow o con ruta inválida no lanza excepción",
             _rasterizar_logo("no_existe.png", 576) is None or isinstance(raster, bytes))


def test_ventana_albaranes():
    print(f"\n{BOLD}{AZUL}[TEST 4] Ventana de albaranes conectada a BD{RESET}")
    from tkinter import messagebox
    from reyger import db as mod_db
    from reyger import albaranes as mod_albaranes

    tmpdir, bd = preparar_bd("reyger_fix_alb_")
    mod_db.get_db_path = lambda: bd
    mod_db._conexion = None
    mod_albaranes.get_db_path = lambda: bd
    mod_albaranes.get_output_path = lambda sub: tmpdir

    con = sqlite3.connect(bd)
    con.execute(
        "INSERT INTO clientes (nombre, direccion) VALUES (?, ?)",
        ("Juan Pérez", "C/ Falsa 123"),
    )
    con.commit()
    con.close()

    with patch.object(messagebox, "showinfo"), \
         patch.object(messagebox, "showwarning"), \
         patch.object(messagebox, "askyesno", return_value=True):
        root = tk.Tk()
        root.withdraw()
        from reyger.albaranes_ui import VentanaAlbaranes

        ventana = VentanaAlbaranes(root, db_path=bd)
        root.update()

        chequear("Número correlativo propuesto (ALB-0001)",
                 ventana.entry_numero.get() == "ALB-0001")
        chequear("Clientes cargados desde la BD",
                 "Juan Pérez" in list(ventana.combo_cliente["values"]))

        ventana.combo_cliente.set("Juan Pérez")
        ventana._cliente_elegido()
        chequear("Dirección autocompletada al elegir cliente",
                 ventana.entry_direccion.get() == "C/ Falsa 123")

        ventana.entry_producto.insert(0, "Martillo")
        ventana.entry_cantidad.insert(0, "3")
        ventana.entry_descripcion.insert(0, "Mango de madera")
        ventana.agregar_linea()
        chequear("Línea añadida al listado", len(ventana.lineas) == 1)

        ventana.entry_producto.insert(0, "Inválido")
        ventana.entry_cantidad.insert(0, "abc")
        ventana.agregar_linea()
        chequear("Cantidad no numérica rechazada", len(ventana.lineas) == 1)

        ventana.generar_albaran()
        listo = bombear_hasta(
            root, lambda: len(ventana.tree.get_children()) == 1
        )
        chequear("Albarán generado y listado actualizado", listo)

        con = sqlite3.connect(bd)
        fila = con.execute(
            "SELECT numero_albaran, cliente_nombre, estado FROM albaranes"
        ).fetchone()
        productos_bd = con.execute(
            "SELECT nombre_producto, cantidad FROM albaranes_productos"
        ).fetchall()
        con.close()
        chequear("Registro guardado en la tabla albaranes",
                 fila is not None and fila[0] == "ALB-0001", str(fila))
        chequear("Productos persistidos en albaranes_productos",
                 productos_bd == [("Martillo", 3)], str(productos_bd))
        pdfs = [f for f in os.listdir(tmpdir) if f.endswith(".pdf")]
        chequear("PDF del albarán generado", len(pdfs) == 1, str(pdfs))

        item = ventana.tree.get_children()[0]
        ventana.tree.selection_set(item)
        ventana.cambiar_estado("Entregado")
        root.update()
        item = ventana.tree.get_children()[0]
        valores = ventana.tree.item(item)["values"]
        chequear("Estado cambiado a Entregado", valores[3] == "Entregado")

        chequear("Correlativo incrementado a ALB-0002",
                 "ALB-0002" in ventana.entry_numero.get())

        ventana.destroy()
        root.destroy()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_exportar_bd_desde_inventario():
    print(f"\n{BOLD}{AZUL}[TEST 5] Exportar BD desde Inventario{RESET}")
    from tkinter import messagebox
    from reyger import inventario as mod_inventario
    from reyger import db as mod_db

    tmpdir, bd = preparar_bd("reyger_fix_expbd_")
    destino = os.path.join(tmpdir, "copia.db")
    mod_db.get_db_path = lambda: bd
    mod_db._conexion = None
    mod_inventario.Inventario.db_name = bd

    with patch.object(messagebox, "showinfo"), \
         patch.object(messagebox, "showwarning"), \
         patch.object(mod_inventario.filedialog, "asksaveasfilename",
                      return_value=destino), \
         patch.object(messagebox, "showerror") as mock_error:
        root = tk.Tk()
        root.withdraw()
        marco = mod_inventario.Inventario(root)
        root.update()

        chequear("Botones Exportar/Importar presentes en Inventario",
                 hasattr(marco, "btn_exportar_bd")
                 and hasattr(marco, "btn_importar_bd"))

        marco.exportar_bd_rapido()
        listo = bombear_hasta(
            root,
            lambda: os.path.exists(destino)
            and str(marco.btn_exportar_bd["state"]) == "normal",
        )
        chequear("Copia .db creada por el hilo secundario", os.path.exists(destino))
        chequear("Botón rehabilitado tras exportar",
                 str(marco.btn_exportar_bd["state"]) == "normal")
        chequear("Sin errores reportados", not mock_error.called)

        # Cancelar el diálogo no debe bloquear ni deshabilitar nada
        with patch.object(mod_inventario.filedialog, "asksaveasfilename",
                          return_value=""):
            marco.exportar_bd_rapido()
            root.update()
        chequear("Cancelar la exportación es inofensivo",
                 str(marco.btn_exportar_bd["state"]) == "normal")

        root.destroy()
    shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    test_formulario_producto_codigo_barras()
    test_crear_categoria_en_caliente()
    test_ticket_logo_y_tamanos()
    test_ventana_albaranes()
    test_exportar_bd_desde_inventario()

    print()
    if FALLOS:
        print(f"{ROJO}{BOLD}FALLARON {len(FALLOS)} comprobaciones:{RESET}")
        for nombre in FALLOS:
            print(f"  - {nombre}")
        return 1
    print(f"{VERDE}{BOLD}Todos los tests de las correcciones pasaron.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
