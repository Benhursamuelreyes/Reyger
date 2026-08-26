#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de la Fase 5 (hardware): captura HID, barra manual y alta automática.

Ejecuta:  python src/reyger/test_fase5_escaner.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

import tkinter as tk

from reyger.ui import ventas as mod_ventas
from reyger.ui import inventario as mod_inventario
from reyger.hardware.barcode_scanner import (
    CapturaEscanero,
    EscanerCodigoBarras,
    registrar_producto_rapido,
)
from reyger.config import ConfigManager

VERDE = "\033[92m"
ROJO = "\033[91m"
AZUL = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []
CODIGO_EXISTENTE = "840000000001"


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" — {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def preparar_bd(tmpdir):
    """Copia la plantilla completa y siembra un producto con código."""
    ruta = os.path.join(tmpdir, "database.db")
    shutil.copyfile(
        os.path.join(SCRIPT_DIR, "assets", "database.db"), ruta
    )
    conn = sqlite3.connect(ruta)
    # El propio escáner crea la columna + índice único (dogfood del fix)
    EscanerCodigoBarras(ruta)
    conn.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
        " tipo_iva, categoria_id, codigo_barras) VALUES (?,?,?,?,?,?,?,?)",
        ("Coca Cola", "", 1.50, 0.90, 25, 21, None, CODIGO_EXISTENTE),
    )
    conn.commit()
    conn.close()
    return ruta


def evento_tecla(caracter):
    teclas_especiales = {"\n": "Return", "\r": "Return"}
    return SimpleNamespace(
        char=caracter,
        keysym=teclas_especiales.get(caracter, caracter),
        state=0,
    )


def test_captura_escanero(root):
    print(f"\n{BOLD}{AZUL}[TEST 1] CapturaEscanero: ráfagas HID{RESET}")
    recibidos = []
    marco = tk.Frame(root)
    marco.pack()
    marco.focus_set()
    captura = CapturaEscanero(marco, recibidos.append)
    captura.iniciar()

    # Ráfaga rápida válida terminada en Enter
    for c in "777850":
        captura._on_tecla(evento_tecla(c))
        time.sleep(0.002)
    captura._on_tecla(evento_tecla("\n"))
    chequear("Ráfaga rápida entrega el código completo",
             recibidos == ["777850"], str(recibidos))

    # Pausa larga entre teclas: el buffer se descarta y el fragmento que
    # llega después no alcanza la longitud mínima -> nada se procesa
    captura._on_tecla(evento_tecla("9"))
    time.sleep(0.09)  # > pausa_maxima_ms (60 ms por defecto)
    captura._on_tecla(evento_tecla("8"))
    captura._on_tecla(evento_tecla("\n"))
    chequear("Pausa larga descarta el buffer (anti-tecleo)",
             recibidos == ["777850"], str(recibidos))

    # Código demasiado corto
    for c in "123":
        captura._on_tecla(evento_tecla(c))
    captura._on_tecla(evento_tecla("\n"))
    chequear("Códigos cortos (<4) ignorados", recibidos == ["777850"])

    # Con foco en un Entry las teclas no se consideran del escáner
    entrada = tk.Entry(root)
    entrada.pack()
    entrada.focus_set()
    root.update()  # materializa el foco antes de simular teclas
    chequear("El Entry tiene el foco", root.focus_get() is entrada)
    antes = len(recibidos)
    for c in "4567":
        captura._on_tecla(evento_tecla(c))
    captura._on_tecla(evento_tecla("\n"))
    chequear("Foco en campo editable ignora las teclas",
             len(recibidos) == antes)

    captura.detener()
    chequear("detener() desactiva la captura", not captura.activo)


def test_registro_rapido(bd):
    print(f"\n{BOLD}{AZUL}[TEST 2] registrar_producto_rapido{RESET}")
    creado = registrar_producto_rapido(
        bd, "999900001", "Pilaa AA", "1,25", precio_costo="0,60", stock="4"
    )
    chequear("Alta con decimales con coma", creado["precio"] == 1.25)
    fila = sqlite3.connect(bd).execute(
        "SELECT nombre, precio, costo, stock, codigo_barras FROM inventario"
        " WHERE id = ?", (creado["id"],),
    ).fetchone()
    chequear("Fila persistida con código asignado",
             fila == ("Pilaa AA", 1.25, 0.6, 4, "999900001"), str(fila))

    for argumentos, motivo in (
        (dict(nombre="", precio_venta="1"), "nombre vacío"),
        (dict(nombre="X", precio_venta="abc"), "precio no numérico"),
        (dict(nombre="X", precio_venta="1", stock="dos"), "stock no entero"),
    ):
        try:
            registrar_producto_rapido(bd, f"8888{motivo[:2]}1", **argumentos)
            fallo = False
        except ValueError:
            fallo = True
        chequear(f"Validación rechaza {motivo}", fallo)

    try:
        registrar_producto_rapido(bd, CODIGO_EXISTENTE, "Dup", "1")
        fallo_dup = False
    except ValueError:
        fallo_dup = True
    chequear("Código duplicado rechazado", fallo_dup)


def test_ventas_por_codigo(root, bd):
    print(f"\n{BOLD}{AZUL}[TEST 3] Ventas: barra manual, carrito y toggle{RESET}")
    original_db = mod_ventas.Ventas.db_name
    mod_ventas.Ventas.db_name = bd
    try:
        ventana = mod_ventas.Ventas(root)
        root.update()

        # Código registrado -> línea en carrito
        ventana.entry_codigo_barras.insert(0, CODIGO_EXISTENTE)
        ventana._desde_barra()
        filas = ventana.tree.get_children()
        chequear("Código conocido añade una línea al carrito", len(filas) == 1)
        valores = ventana.tree.item(filas[0])["values"] if filas else ()
        chequear("Línea correcta (producto, precio, cantidad, IVA)",
                 valores[:4] == ["Coca Cola", "1.50", 1, "21%"], str(valores))

        # Anti-doble-disparo inmediato
        ventana.entry_codigo_barras.insert(0, CODIGO_EXISTENTE)
        ventana._desde_barra()
        chequear("Anti-doble-disparo evita duplicado inmediato",
                 len(ventana.tree.get_children()) == 1)

        # Código desconocido con usuario declinando el alta
        with patch.object(mod_ventas.messagebox, "askyesno", return_value=False):
            ventana.entry_codigo_barras.insert(0, "00000X")
            ventana._desde_barra()
        chequear("Desconocido sin alta no toca el carrito",
                 len(ventana.tree.get_children()) == 1)

        # Código desconocido aceptando el alta (diálogo simulado)
        class DialogoFalso:
            def __init__(self, parent, codigo, db_path):
                self.resultado = registrar_producto_rapido(
                    db_path, codigo, "Teclado USB", "12,90", stock="7"
                )

        with patch.object(mod_ventas.messagebox, "askyesno",
                          return_value=True), \
             patch.object(mod_ventas, "DialogoRegistroRapido", DialogoFalso):
            ventana.entry_codigo_barras.insert(0, "55550001")
            ventana._desde_barra()
        filas = ventana.tree.get_children()
        ultima = ventana.tree.item(filas[-1])["values"]
        chequear("Desconocido + aceptar -> alta automática y al carrito",
                 ultima[0] == "Teclado USB" and ultima[1] == "12.90", str(ultima))
        chequear("Producto nuevo disponible en el selector",
                 "Teclado USB" in ventana.productos_info)

        # Persistencia del interruptor
        ventana.var_escaner.set(True)
        ventana._alternar_escaner()
        chequear("Toggle ON arranca la captura", ventana.captura.activo)
        guardado = ConfigManager().get("escaner_activo")
        chequear("Preferencia del toggle persistida", guardado is True)
        ventana.var_escaner.set(False)
        ventana._alternar_escaner()
        chequear("Toggle OFF detiene la captura", not ventana.captura.activo)

        ventana.destroy()
    finally:
        mod_ventas.Ventas.db_name = original_db
        ConfigManager().set("escaner_activo", False)


def test_inventario_por_codigo(root, bd):
    print(f"\n{BOLD}{AZUL}[TEST 4] Inventario: búsqueda y alta desde la barra{RESET}")
    original_db = mod_inventario.Inventario.db_name
    mod_inventario.Inventario.db_name = bd
    try:
        panel = mod_inventario.Inventario(root)
        root.update()

        # Código conocido -> selecciona la fila correspondiente
        panel.entry_busca_codigo.insert(0, CODIGO_EXISTENTE)
        panel.buscar_por_codigo()
        seleccion = panel.tre.selection()
        chequear("Código conocido selecciona su fila",
                 len(seleccion) == 1
                 and panel.tre.item(seleccion[0])["values"][1] == "Coca Cola")

        # Desconocido sin alta: no cambia el listado
        antes = len(panel.tre.get_children())
        with patch.object(mod_inventario.messagebox, "askyesno",
                          return_value=False):
            panel.entry_busca_codigo.insert(0, "44440004")
            panel.buscar_por_codigo()
        chequear("Desconocido sin alta deja el listado intacto",
                 len(panel.tre.get_children()) == antes)

        # Desconocido con alta: aparece registrado y seleccionado
        class DialogoFalso:
            def __init__(self, parent, codigo, db_path):
                self.resultado = registrar_producto_rapido(
                    db_path, codigo, "Monitor 24\"", "129.99", stock="5"
                )

        with patch.object(mod_inventario.messagebox, "askyesno",
                          return_value=True), \
             patch.object(mod_inventario.messagebox, "showinfo",
                          return_value="ok"), \
             patch.object(mod_inventario, "DialogoRegistroRapido",
                          DialogoFalso):
            panel.entry_busca_codigo.insert(0, "44440004")
            panel.buscar_por_codigo()
        seleccion = panel.tre.selection()
        nombres = [
            panel.tre.item(i)["values"][1] for i in panel.tre.get_children()
        ]
        chequear("Alta automática visible en el listado",
                 "Monitor 24\"" in nombres, str(nombres))
        chequear("Nuevo producto queda seleccionado",
                 len(seleccion) == 1
                 and panel.tre.item(seleccion[0])["values"][1] == "Monitor 24\"")

        panel.destroy()
    finally:
        mod_inventario.Inventario.db_name = original_db


def main():
    tmpdir = tempfile.mkdtemp(prefix="reyger_fase5_")
    bd = preparar_bd(tmpdir)

    root = tk.Tk()
    # Visible y mínima (no withdraw): con la ventana retirada X11 no
    # mantiene foco y el chequeo de campo editable sería irreal.
    root.geometry("160x100+5+5")

    try:
        test_captura_escanero(root)
        test_registro_rapido(bd)
        test_ventas_por_codigo(root, bd)
        test_inventario_por_codigo(root, bd)
    finally:
        root.destroy()

    print()
    if FALLOS:
        print(f"{ROJO}{BOLD}FALLARON {len(FALLOS)} comprobaciones:{RESET}")
        for nombre in FALLOS:
            print(f"  - {nombre}")
        return 1
    print(f"{VERDE}{BOLD}Todos los tests de la fase 5 pasaron.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
