#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de la Fase 4 (hardware): generación y envío de tickets
térmicos ESC/POS e integración con el flujo de ventas.

Ejecuta:  python src/reyger/test_fase4_impresion.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

import reyger.db as modulo_db
import reyger.container as modulo_container
import reyger.clientes as modulo_clientes
import reyger.inventario as modulo_inventario
import reyger.ventas as modulo_ventas
from reyger.impresion_termica import (
    ANCHO_58MM,
    ANCHO_80MM,
    CORTE_PARCIAL,
    INICIO,
    TicketTermico,
    construir_ticket_venta,
    enviar_bytes,
    listar_impresoras_termicas,
)
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
    nulo = SimpleNamespace(
        showinfo=lambda *a, **k: None,
        showwarning=lambda *a, **k: None,
        showerror=lambda *a, **k: None,
        askyesno=lambda *a, **k: True,
    )
    modulo_container.messagebox = nulo
    modulo_clientes.messagebox = nulo
    modulo_inventario.messagebox = nulo
    modulo_ventas.messagebox = nulo


def preparar_db():
    tmp_dir = tempfile.mkdtemp(prefix="reyger_f4_")
    ruta = os.path.join(tmp_dir, "prueba.db")
    shutil.copyfile(PLANTILLA, ruta)
    anterior_db = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    return tmp_dir, ruta, anterior_db


def liberar_db(anterior):
    modulo_db.close()
    modulo_db.get_db_path = anterior


_COMANDOS = (
    b"\x1b@", b"\x1ba\x00", b"\x1ba\x01",
    b"\x1bE\x01", b"\x1bE\x00",
    b"\x1d!\x11", b"\x1d!\x00",
)


def decodificar_lineas(datos):
    """Decodifica el ticket a líneas de texto legibles."""
    limpio = datos
    for comando in _COMANDOS:
        limpio = limpio.replace(comando, b"")
    texto = limpio.decode("cp858", errors="replace")
    return [l for l in texto.split("\n")]


def test_constructor_ticket():
    print(f"\n{BOLD}{AZUL}[TEST 1] Constructor de tickets ESC/POS{RESET}")

    productos = [
        ("Vino Tinto", 11.00, 2, 22.00),
        ("Pan", 0.50, 3, 1.50),
    ]
    datos = construir_ticket_venta(
        numero_factura=7,
        fecha="21/08/2026 13:45",
        productos=productos,
        total=23.50,
        base=21.20,
        cuota=2.30,
        metodo_pago="Mixto",
        cliente="Ana García",
        empresa="Bar Los Robles",
        ancho=ANCHO_80MM,
    )

    chequear("El ticket son bytes", isinstance(datos, bytes))
    chequear("Comienza con init ESC/POS", datos.startswith(INICIO))
    chequear("Termina con corte parcial", datos.endswith(CORTE_PARCIAL))

    lineas = decodificar_lineas(datos)
    texto = "\n".join(lineas)
    chequear("Empresa en el encabezado", "BAR LOS ROBLES" in texto)
    chequear("Número de recibo presente", "Recibo: 7" in texto)
    chequear("Cliente presente", "Cliente: Ana García" in texto)
    chequear("Productos listados", "Vino Tinto" in texto and "Pan" in texto)
    chequear("Total presente", "TOTAL" in texto and "23.50" in texto)
    chequear("Desglose de base presente", "Base imponible" in texto and "21.20" in texto)
    chequear("Cuota de IVA presente", "Cuota IVA" in texto and "2.30" in texto)
    chequear("Método de pago presente", "Pago: Mixto" in texto)

    # Todas las líneas de texto caben en el ancho del papel
    excedidas = [
        l for l in lineas
        if l.strip() and not l.startswith("\x1b") and len(l) > ANCHO_80MM
    ]
    chequear(
        f"Ninguna línea supera {ANCHO_80MM} columnas",
        not excedidas,
        f"excedidas={excedidas[:3]}",
    )

    # Nombre larguísimo: se recorta sin romper el ancho
    nombre_largo = "Producto con un nombre extraordinariamente largo para el papel"
    datos_largos = construir_ticket_venta(
        numero_factura=1, fecha="hoy", productos=[(nombre_largo, 1.0, 1, 1.0)],
        total=1.0, ancho=ANCHO_58MM,
    )
    lineas_largas = decodificar_lineas(datos_largos)
    excedidas = [
        l for l in lineas_largas
        if l.strip() and len(l) > ANCHO_58MM
    ]
    chequear(
        f"Nombres largos recortados a {ANCHO_58MM} columnas",
        not excedidas,
        f"excedidas={excedidas[:3]}",
    )
    chequear(
        "Nombre recortado sigue reconocible",
        nombre_largo[:20] in "\n".join(lineas_largas),
    )

    # Caracteres españoles y símbolo del euro
    datos_es = construir_ticket_venta(
        numero_factura=2, fecha="hoy",
        productos=[("Caña Ñoño €", 2.00, 1, 2.00)], total=2.00,
    )
    texto_es = datos_es.decode("cp858")
    chequear("Codificación CP858 conserva ñ y €", "Ñoño" in texto_es)

    # Encadenado manual del builder
    t = TicketTermico(empresa="X")
    t.encabezado().info(1, "hoy").separador().linea_producto("A", 1, 2.0, 2.0)
    t.totales(2.0, 1.65, 0.35).metodo_pago("Tarjeta").pie().cortar()
    chequear("Builder encadenable produce bytes", isinstance(t.construir(), bytes))


def test_envio():
    print(f"\n{BOLD}{AZUL}[TEST 2] Envío al sistema de impresión{RESET}")

    try:
        nombres = listar_impresoras_termicas()
        chequear(
            "listar_impresoras_termicas() devuelve lista",
            isinstance(nombres, list),
            f"tipo={type(nombres)}",
        )
    except Exception as e:
        chequear("listar_impresoras_termicas() devuelve lista", False, str(e))

    try:
        resultado = enviar_bytes(b"prueba", "impresora_que_no_existe")
        chequear(
            "Envío a impresora inexistente falla sin excepción",
            resultado is False,
            f"resultado={resultado}",
        )
    except Exception as e:
        chequear("Envío a impresora inexistente falla sin excepción", False, str(e))


def test_integracion_ventas():
    print(f"\n{BOLD}{AZUL}[TEST 3] Impresión automática al cobrar{RESET}")
    tmp_dir, ruta, anterior_db = preparar_db()
    salida_original = modulo_ventas.get_output_path
    abrir_original = modulo_ventas.open_file
    config_original = modulo_ventas.ConfigManager
    ticket_original = modulo_ventas.imprimir_ticket_venta
    db_original = Ventas.db_name
    try:
        Ventas.db_name = ruta
        conn = sqlite3.connect(ruta)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
            " VALUES ('Café', 'Tostador', 2.20, 1.00, 50, 10)"
        )
        conn.commit()
        conn.close()

        modulo_ventas.get_output_path = lambda *a: tmp_dir
        modulo_ventas.open_file = lambda *a, **k: None

        configuracion = {
            "impresora_termica": "Termica-Test",
            "ancho_ticket": 80,
            "nombre_empresa": "Bar Los Robles",
        }

        class ConfigFalsa:
            def get(self, clave, defecto=None):
                return configuracion.get(clave, defecto)

        capturas = {}

        def ticket_falso(numero_factura, fecha, productos, total, base=None,
                         cuota=None, metodo_pago="Efectivo", cliente=None,
                         empresa="Mi Empresa", ancho=ANCHO_80MM, letra="grande",
                         impresora=None):
            capturas.update({
                "numero": numero_factura, "total": total, "base": base,
                "cuota": cuota, "metodo": metodo_pago, "cliente": cliente,
                "empresa": empresa, "ancho": ancho, "letra": letra,
                "impresora": impresora,
                "productos": list(productos),
            })
            return True, "ok"

        modulo_ventas.ConfigManager = ConfigFalsa
        modulo_ventas.imprimir_ticket_venta = ticket_falso

        root = tk.Tk()
        root.withdraw()
        ventas = Ventas(root)

        ventas.entry_nombre.set("Café")
        ventas.actualizar_precio(None)
        ventas.entry_cantidad.insert(0, "2")
        ventas.registrar()
        ventas.pagar(
            SimpleNamespace(destroy=lambda: None),
            SimpleNamespace(get=lambda: "10"),
            SimpleNamespace(get=lambda: "0"),
            SimpleNamespace(get=lambda: "Efectivo"),
            SimpleNamespace(config=lambda **k: None),
            4.40,
        )

        # Desde la Fase 6 el ticket se imprime en hilo secundario y el
        # aviso vuelve por el bucle de eventos: bombear hasta que llegue.
        limite = time.time() + 5
        while not capturas and time.time() < limite:
            root.update()
            time.sleep(0.02)

        chequear("Ticket enviado al cobrar", bool(capturas))
        if capturas:
            chequear("Número de factura correcto", capturas["numero"] == 1)
            chequear("Total correcto", abs(capturas["total"] - 4.40) < 0.01)
            chequear("Base correcta", abs(capturas["base"] - 4.00) < 0.01)
            chequear("Cuota correcta", abs(capturas["cuota"] - 0.40) < 0.01)
            chequear("Impresora configurada usada", capturas["impresora"] == "Termica-Test")
            chequear("Empresa del ticket correcta", capturas["empresa"] == "Bar Los Robles")
            chequear(
                "Producto incluido",
                any(p[0] == "Café" for p in capturas["productos"]),
            )

        # Sin impresora configurada no se intenta imprimir
        capturas.clear()
        configuracion["impresora_termica"] = None
        ventas.entry_nombre.set("Café")
        ventas.actualizar_precio(None)
        ventas.entry_cantidad.insert(0, "1")
        ventas.registrar()
        ventas.pagar(
            SimpleNamespace(destroy=lambda: None),
            SimpleNamespace(get=lambda: "5"),
            SimpleNamespace(get=lambda: "0"),
            SimpleNamespace(get=lambda: "Efectivo"),
            SimpleNamespace(config=lambda **k: None),
            2.20,
        )
        chequear(
            "Sin impresora configurada no se imprime",
            not capturas,
        )

        root.destroy()
    finally:
        modulo_ventas.get_output_path = salida_original
        modulo_ventas.open_file = abrir_original
        modulo_ventas.ConfigManager = config_original
        modulo_ventas.imprimir_ticket_venta = ticket_original
        Ventas.db_name = db_original
        liberar_db(anterior_db)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    print(f"{BOLD}{AZUL}TESTS FASE 4 - IMPRESIÓN TÉRMICA{RESET}")
    print(f"{BOLD}{AZUL}{'=' * 60}{RESET}")

    silenciar_messageboxes()
    test_constructor_ticket()
    test_envio()
    test_integracion_ventas()

    print(f"\n{BOLD}{AZUL}{'=' * 60}{RESET}")
    if FALLOS:
        print(f"{ROJO}{BOLD}✗ FALLARON {len(FALLOS)} COMPROBACIONES:{RESET}")
        for fallo in FALLOS:
            print(f"  {ROJO}- {fallo}{RESET}")
        return 1
    print(f"{VERDE}{BOLD}🎉 TODOS LOS TESTS DE FASE 4 PASAN{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
