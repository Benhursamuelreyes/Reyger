"""Tests de la Fase 6: optimización y rendimiento.

Cubre: índices de la migración 5, PRAGMA de db.py, columna Categoría
de inventario.mostrar (columnas explícitas), helper hilos.en_hilo y la
exportación de BD / impresión térmica fuera del hilo de la interfaz.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import tkinter as tk

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
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


def bombear(root, segundos):
    """Procesa eventos Tk durante *segundos* (permite madurar ``after``)."""
    fin = time.time() + segundos
    while time.time() < fin:
        root.update()
        time.sleep(0.01)


def test_indices_y_plantilla():
    print(f"\n{BOLD}{AZUL}[TEST 1] Migración 5: índices y plantilla{RESET}")
    conn = sqlite3.connect(PLANTILLA)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    chequear("Plantilla al día (user_version == LATEST)", version >= 5,
             f"obtenido {version}")
    nombres = {
        fila[0] for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
    }
    esperados = {
        "idx_inventario_codigo_barras", "idx_inventario_nombre",
        "idx_ventas_fecha", "idx_ventas_factura", "idx_clientes_nombre",
    }
    chequear("Los 5 índices existen en la plantilla",
             esperados <= nombres, str(sorted(esperados - nombres)))
    conn.close()

    # Esquema antiguo sin columnas nuevas: la migración no debe romperse
    tmpdir = tempfile.mkdtemp(prefix="reyger_f6_idx_")
    ruta = os.path.join(tmpdir, "vieja.db")
    vieja = sqlite3.connect(ruta)
    vieja.executescript(
        """
        CREATE TABLE ventas (id INTEGER PRIMARY KEY, total REAL);
        CREATE TABLE inventario (id INTEGER PRIMARY KEY, nombre TEXT);
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT);
        PRAGMA user_version = 4;
        """
    )
    vieja.commit()
    vieja.close()
    import reyger.migrations as migrations
    conn = sqlite3.connect(ruta)
    try:
        migrations.run_migrations(conn)
        chequear("Migración 5 tolera esquemas antiguos", True)
    except Exception as e:
        chequear("Migración 5 tolera esquemas antiguos", False, str(e))
    conn.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_pragmas():
    print(f"\n{BOLD}{AZUL}[TEST 2] PRAGMA de rendimiento en db.py{RESET}")
    tmpdir = tempfile.mkdtemp(prefix="reyger_f6_pragma_")
    original = None
    import reyger.db as modulo_db
    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: os.path.join(tmpdir, "prueba.db")
    modulo_db.close()
    try:
        conn = modulo_db.get_connection()
        sinc = conn.execute("PRAGMA synchronous").fetchone()[0]
        temp = conn.execute("PRAGMA temp_store").fetchone()[0]
        cache = conn.execute("PRAGMA cache_size").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        chequear("synchronous = NORMAL (1)", sinc == 1, str(sinc))
        chequear("temp_store = MEMORY (2)", temp == 2, str(temp))
        chequear("cache_size negativo (KiB)", cache < 0, str(cache))
        chequear("foreign_keys sigue activa", fk == 1, str(fk))
    finally:
        modulo_db.close()
        modulo_db.get_db_path = original
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_mostrar_categoria():
    print(f"\n{BOLD}{AZUL}[TEST 3] inventario.mostrar con columnas explícitas{RESET}")
    import reyger.db as modulo_db
    from reyger.categorias import crear as crear_categoria
    from reyger.inventario import Inventario

    tmpdir = tempfile.mkdtemp(prefix="reyger_f6_cat_")
    ruta = os.path.join(tmpdir, "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    original_db = Inventario.db_name
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    Inventario.db_name = ruta
    try:
        id_frutas = crear_categoria("Frutas")
        with sqlite3.connect(ruta) as conn:
            conn.execute(
                "INSERT INTO inventario (nombre, proveedor, precio, costo,"
                " stock, tipo_iva, categoria_id)"
                " VALUES ('Pera', 'P', 1.1, 0.5, 7, 21, ?)", (id_frutas,)
            )
            conn.commit()
        root = tk.Tk()
        root.withdraw()
        panel = Inventario(root)
        panel.mostrar()
        hijos = panel.tre.get_children()
        valores = [panel.tre.item(h)["values"] for h in hijos]
        pera = next(v for v in valores if v[1] == "Pera")
        chequear("Columna Categoría rellena", pera[7] == "Frutas", str(pera))
        chequear("IVA visible", str(pera[6]).startswith("21"), str(pera))
        panel.destroy()
        root.destroy()
    finally:
        Inventario.db_name = original_db
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_en_hilo():
    print(f"\n{BOLD}{AZUL}[TEST 4] hilos.en_hilo{RESET}")
    from reyger.hilos import en_hilo

    root = tk.Tk()
    root.withdraw()
    try:
        resultados = []
        hilo_actual = {}

        def trabajo_ok():
            hilo_actual["es_principal"] = (
                threading.current_thread() is threading.main_thread()
            )
            return 42

        en_hilo(root, trabajo_ok,
                lambda res, err: resultados.append((res, err)))
        bombear(root, 1.0)
        chequear("Resultado entregado", resultados == [(42, None)],
                 str(resultados))
        chequear("Trabajo ejecutado fuera del hilo principal",
                 hilo_actual.get("es_principal") is False)

        resultados.clear()

        def trabajo_malo():
            raise ValueError("boom")

        en_hilo(root, trabajo_malo,
                lambda res, err: resultados.append((res, err)))
        bombear(root, 1.0)
        chequear("Error entregado a la UI",
                 len(resultados) == 1 and isinstance(resultados[0][1], ValueError),
                 str(resultados))
    finally:
        root.destroy()


def test_exportacion_en_hilo():
    print(f"\n{BOLD}{AZUL}[TEST 5] Exportación de BD fuera del hilo UI{RESET}")
    from unittest.mock import patch

    import reyger.ajustes as mod_ajustes
    import reyger.db as modulo_db

    tmpdir = tempfile.mkdtemp(prefix="reyger_f6_exp_")
    ruta_bd = os.path.join(tmpdir, "tienda.db")
    shutil.copyfile(PLANTILLA, ruta_bd)
    destino = os.path.join(tmpdir, "copia.db")

    original_path = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()

    root = tk.Tk()
    root.withdraw()
    original_db_attr = getattr(mod_ajustes.Ajustes, "db_name", None)
    try:
        panel = mod_ajustes.Ajustes(root)
        panel.var_formato_bd.set("db")
        estados = []
        panel.btn_exportar_bd.config(command=lambda: estados.append("click"))

        def capturar_estado():
            estados.append(str(panel.btn_exportar_bd["state"]))

        mensajes = []
        # Los parches deben seguir activos mientras se bombean eventos:
        # el callback del hilo llega DESPUÉS de que exportar_base_datos
        # haya retornado.
        with patch.object(mod_ajustes.filedialog, "asksaveasfilename",
                          return_value=destino), \
             patch.object(mod_ajustes.messagebox, "showinfo",
                          lambda *a, **k: mensajes.append(a)), \
             patch.object(mod_ajustes.messagebox, "showerror",
                          lambda *a, **k: mensajes.append(("error",) + a)):
            panel.exportar_base_datos()
            capturar_estado()
            bombear(root, 3.0)
            capturar_estado()
        chequear("Fichero .db creado por el hilo secundario",
                 os.path.exists(destino))
        chequear("Sin errores reportados",
                 all(m[0] != "error" for m in mensajes), str(mensajes))
        chequear("Botón deshabilitado durante la tarea",
                 "disabled" in estados, str(estados))
        chequear("Botón rehabilitado al terminar",
                 estados[-1] == "normal", str(estados))
        panel.destroy()
    finally:
        root.destroy()
        modulo_db.close()
        modulo_db.get_db_path = original_path
        if original_db_attr is not None:
            mod_ajustes.Ajustes.db_name = original_db_attr
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_impresion_en_hilo():
    print(f"\n{BOLD}{AZUL}[TEST 6] Ticket térmico fuera del hilo UI{RESET}")
    from unittest.mock import patch

    import reyger.ventas as mod_ventas

    avisos = []
    raiz = tk.Tk()
    raiz.withdraw()
    try:
        ventas = object.__new__(mod_ventas.Ventas)
        ventas.master = raiz
        # ``after`` del frame no existe sin __init__; usamos la raíz como ancla
        ventas.after = raiz.after

        def impresora_lenta(*args, **kwargs):
            time.sleep(0.3)
            return False, "impresora ocupada"

        with patch.object(mod_ventas.ConfigManager, "get",
                          side_effect=lambda clave, x=None: {
                              "impresora_termica": "POS-80"}.get(clave, x)), \
             patch.object(mod_ventas, "imprimir_ticket_venta",
                          impresora_lenta), \
             patch.object(mod_ventas.messagebox, "showwarning",
                          lambda *a, **k: avisos.append(a)):
            inicio = time.time()
            ventas._imprimir_ticket_termico(
                "F-1", "hoy", [], 10.0, 8.26, 1.74, "Efectivo", None
            )
            transcurrido = time.time() - inicio
            chequear("La llamada vuelve sin esperar a la impresión",
                     transcurrido < 0.15, f"{transcurrido:.2f}s")
            bombear(raiz, 1.5)
            chequear("Aviso de fallo recibido en la UI",
                     len(avisos) == 1 and "ocupada" in avisos[0][1],
                     str(avisos))
    finally:
        raiz.destroy()


def main():
    test_indices_y_plantilla()
    test_pragmas()
    test_mostrar_categoria()
    test_en_hilo()
    test_exportacion_en_hilo()
    test_impresion_en_hilo()

    print()
    if FALLOS:
        print(f"{ROJO}{BOLD}FALLARON {len(FALLOS)} comprobaciones:{RESET}")
        for nombre in FALLOS:
            print(f"  - {nombre}")
        return 1
    print(f"{VERDE}{BOLD}Todos los tests de la fase 6 pasaron.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
