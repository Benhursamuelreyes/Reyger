#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de testing para verificar que todas las funcionalidades
están correctamente implementadas e instaladas.

Ejecuta: python test_nuevas_funcionalidades.py
"""

import os
import sys
import tkinter as tk
import pytest
from datetime import datetime

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

# Plantilla incluida con la app (la que se copia en el primer arranque).
DB_PATH = os.path.join(SCRIPT_DIR, "assets", "database.db")

# Colores para output
VERDE = '\033[92m'
ROJO = '\033[91m'
AMARILLO = '\033[93m'
AZUL = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_resultado(test_nombre, success, mensaje=""):
    """Imprime el resultado de un test con color"""
    if success:
        print(f"{VERDE}✓ {test_nombre}{RESET}")
    else:
        print(f"{ROJO}✗ {test_nombre}{RESET}")
    if mensaje:
        print(f"  {AMARILLO}➜ {mensaje}{RESET}")


def test_imports():
    """Test 1: Verificar que todos los módulos nuevos se importan"""
    print(f"\n{BOLD}{AZUL}[TEST 1] Importación de módulos{RESET}")

    tests = [
        ("reyger.domain.facturas_verifactu.FacturaVeriFACTU", "Factura VeriFACTU"),
        ("reyger.ui.tickets.TicketSimplificado", "Tickets"),
        ("reyger.ui.albaranes.AlbaranEntrega", "Albaranes"),
        ("reyger.ui.presupuestos.Presupuestos", "Presupuestos"),
        ("reyger.hardware.impresoras.GestorImpresoras", "Gestor de Impresoras"),
        ("reyger.hardware.barcode_scanner.EscanerCodigoBarras", "Escáner de Código de Barras"),
        ("reyger.ui.clientes.Clientes", "Clientes"),
    ]

    fallidos = []
    for ruta, nombre in tests:
        try:
            partes = ruta.split('.')
            modulo = __import__('.'.join(partes[:-1]), fromlist=[partes[-1]])
            getattr(modulo, partes[-1])
            print_resultado(f"Importar {nombre}", True)
        except Exception as e:
            print_resultado(f"Importar {nombre}", False, str(e))
            fallidos.append(nombre)

    assert not fallidos, f"No se pudieron importar: {fallidos}"


def test_dependencias():
    """Test 2: Verificar librerías externas instaladas"""
    print(f"\n{BOLD}{AZUL}[TEST 2] Dependencias externas{RESET}")

    dependencias = [
        ("qrcode", "qrcode"),
        ("reportlab", "reportlab"),
        ("PIL", "Pillow"),
    ]

    faltan = []
    for lib, nombre in dependencias:
        try:
            __import__(lib)
            print_resultado(f"Librería {nombre}", True)
        except ImportError:
            print_resultado(f"Librería {nombre}", False, "Instala con: pip install" + " " + nombre.lower())
            faltan.append(nombre)

    # pywin32 es opcional (solo para impresoras en Windows): no bloquea.
    try:
        import win32print  # noqa: F401
        print_resultado("Librería pywin32 (Windows)", True)
    except ImportError:
        print_resultado("Librería pywin32 (Windows)", False, "Opcional - Instalada solo si necesitas impresoras")

    assert not faltan, f"Faltan dependencias: {faltan}"


def test_base_datos():
    """Test 3: La plantilla de base de datos incluida tiene las tablas clave"""
    print(f"\n{BOLD}{AZUL}[TEST 3] Base de Datos{RESET}")
    import sqlite3

    assert os.path.exists(DB_PATH), f"No existe la plantilla {DB_PATH}"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        tablas = {fila[0] for fila in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    finally:
        conn.close()
    print_resultado("Conexión a la plantilla", True, f"{len(tablas)} tablas encontradas")

    clave = ("inventario", "documentos", "lineas_documento", "presupuestos", "albaranes")
    faltan = [t for t in clave if t not in tablas]
    for tabla in clave:
        print_resultado(f"Tabla '{tabla}'", tabla not in faltan)
    assert not faltan, f"Faltan tablas en la plantilla: {faltan}"


def test_estructura_proyecto():
    """Test 4: Verificar estructura de archivos"""
    print(f"\n{BOLD}{AZUL}[TEST 4] Estructura de archivos{RESET}")

    archivos_esperados = [
        "app.py",
        "container.py",
        "config.py",
        "ui/manager.py",
        "ui/ventas.py",
        "ui/inventario.py",
        "ui/clientes.py",
        "ui/ajustes.py",
        "ui/ui.py",
        "ui/tickets.py",
        "ui/albaranes.py",
        "ui/presupuestos.py",
        "core/db.py",
        "core/migrations.py",
        "domain/facturas_verifactu.py",
        "domain/ventas.py",
        "domain/inventario.py",
        "hardware/impresoras.py",
        "hardware/barcode_scanner.py",
        "assets/database.db",
    ]

    faltan = []
    for archivo in archivos_esperados:
        existe = os.path.exists(os.path.join(SCRIPT_DIR, archivo))
        print_resultado(f"Archivo {archivo}", existe, "" if existe else "No encontrado")
        if not existe:
            faltan.append(archivo)

    assert not faltan, f"Faltan archivos: {faltan}"


@pytest.mark.orden_dependiente
def test_funcionalidad_basica():
    """Test 5: Pruebas funcionales básicas"""
    print(f"\n{BOLD}{AZUL}[TEST 5] Funcionalidad básica{RESET}")
    
    resultados = []
    
    # Test FacturaVeriFACTU
    try:
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        FacturaVeriFACTU()
        print_resultado("Instanciar FacturaVeriFACTU", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar FacturaVeriFACTU", False, str(e))
        resultados.append(False)
    
    # Test TicketSimplificado
    try:
        from reyger.ui.tickets import TicketSimplificado
        TicketSimplificado()
        print_resultado("Instanciar TicketSimplificado", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar TicketSimplificado", False, str(e))
        resultados.append(False)
    
    # Test AlbaranEntrega
    try:
        from reyger.ui.albaranes import AlbaranEntrega
        AlbaranEntrega()
        print_resultado("Instanciar AlbaranEntrega", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar AlbaranEntrega", False, str(e))
        resultados.append(False)
    
    # Test Presupuestos (Frame tkinter: necesita un parent)
    try:
        from reyger.ui.presupuestos import Presupuestos
        root = tk.Tk()
        root.withdraw()
        Presupuestos(root)
        root.destroy()
        print_resultado("Instanciar Presupuestos", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar Presupuestos", False, str(e))
        resultados.append(False)
    
    # Test EscanerCodigoBarras
    try:
        from reyger.hardware.barcode_scanner import EscanerCodigoBarras
        EscanerCodigoBarras()
        print_resultado("Instanciar EscanerCodigoBarras", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar EscanerCodigoBarras", False, str(e))
        resultados.append(False)
    
    # Test GestorImpresoras
    try:
        from reyger.hardware.impresoras import GestorImpresoras
        GestorImpresoras()
        print_resultado("Instanciar GestorImpresoras", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar GestorImpresoras", False, str(e))
        resultados.append(False)

    assert all(resultados), "Algún componente no se pudo instanciar (ver arriba)"


def test_directorios_salida():
    """Test 6: get_output_path crea los directorios de salida en los datos del usuario"""
    print(f"\n{BOLD}{AZUL}[TEST 6] Directorios de salida{RESET}")
    import tempfile
    from pathlib import Path

    import reyger.resources as resources

    directorios = [
        ("facturas", "Facturas ordinarias"),
        ("facturas_verifactu", "Facturas VeriFACTU"),
        ("tickets", "Tickets"),
        ("albaranes", "Albaranes"),
        ("presupuestos_pdf", "Presupuestos PDF"),
    ]

    original = resources.get_user_data_path
    with tempfile.TemporaryDirectory() as tmp:
        resources.get_user_data_path = lambda: Path(tmp)
        try:
            for directorio, descripcion in directorios:
                ruta = resources.get_output_path(directorio)
                creado = os.path.isdir(ruta) and ruta.startswith(tmp)
                print_resultado(f"Directorio {descripcion} (/{directorio})", creado)
                assert creado, f"No se creó {ruta}"
        finally:
            resources.get_user_data_path = original


def _superado(test):
    """Ejecuta *test* fuera de pytest: ``True`` si no falla ningún assert."""
    try:
        test()
        return True
    except AssertionError as e:
        print(f"  {ROJO}✗ {e}{RESET}")
        return False


def mostrar_resumen(tests):
    """Muestra resumen final"""
    print(f"\n{BOLD}{AZUL}{'='*60}{RESET}")
    print(f"{BOLD}{AZUL}RESUMEN FINAL{RESET}")
    print(f"{BOLD}{AZUL}{'='*60}{RESET}\n")
    
    total = len(tests)
    exitosos = sum(1 for t in tests if t)
    fallidos = total - exitosos
    
    print(f"Pruebas ejecutadas: {total}")
    print(f"{VERDE}✓ Exitosas: {exitosos}{RESET}")
    print(f"{ROJO}✗ Fallidas: {fallidos}{RESET}")
    
    if fallidos == 0:
        print(f"\n{VERDE}{BOLD}🎉 ¡TODO FUNCIONA PERFECTAMENTE!{RESET}")
        print(f"{VERDE}Tu aplicación está lista para usar todas las 7 nuevas funcionalidades.{RESET}\n")
    else:
        print(f"\n{ROJO}{BOLD}⚠️ SOLUCIONA LOS ERRORES ARRIBA{RESET}")
        print(f"{AMARILLO}Ejecuta: pip install qrcode[pil] pywin32 reportlab pillow ttkthemes{RESET}\n")
    
    return fallidos == 0


def main():
    """Función principal"""
    print(f"\n{BOLD}{AZUL}{'='*60}{RESET}")
    print(f"{BOLD}{AZUL}TEST DE NUEVAS FUNCIONALIDADES - SALES SYSTEM{RESET}")
    print(f"{BOLD}{AZUL}{'='*60}{RESET}")
    print(f"{AMARILLO}Iniciado: {datetime.now().strftime('%H:%M:%S')}{RESET}\n")
    
    # Ejecutar tests
    tests = [
        _superado(test_imports),
        _superado(test_dependencias),
        _superado(test_base_datos),
        _superado(test_estructura_proyecto),
        _superado(test_funcionalidad_basica),
        _superado(test_directorios_salida),
    ]
    
    # Mostrar resumen
    exito = mostrar_resumen(tests)
    
    # Información adicional
    print(f"{BOLD}Próximos pasos:{RESET}")
    print(f"  1. Ejecuta: {AMARILLO}python -m reyger{RESET}")
    print("  2. Abre menú Presupuestos (nuevo botón púrpura)")
    print("  3. Prueba los métodos de pago en Ventas")
    print("  4. Genera facturas y tickets\n")
    
    return 0 if exito else 1


if __name__ == "__main__":
    exit(main())
