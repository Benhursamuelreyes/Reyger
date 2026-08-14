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
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

DB_PATH = os.path.join(PROJECT_ROOT, "database.db")

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
        ("reyger.facturas_verifactu.FacturaVeriFACTU", "Factura VeriFACTU"),
        ("reyger.tickets.TicketSimplificado", "Tickets"),
        ("reyger.albaranes.AlbaranEntrega", "Albaranes"),
        ("reyger.presupuestos.Presupuestos", "Presupuestos"),
        ("reyger.impresoras.GestorImpresoras", "Gestor de Impresoras"),
        ("reyger.barcode_scanner.EscanerCodigoBarras", "Escáner de Código de Barras"),
    ]
    
    resultados = []
    for ruta, nombre in tests:
        try:
            partes = ruta.split('.')
            modulo = __import__('.'.join(partes[:-1]), fromlist=[partes[-1]])
            getattr(modulo, partes[-1])
            print_resultado(f"Importar {nombre}", True)
            resultados.append(True)
        except Exception as e:
            print_resultado(f"Importar {nombre}", False, str(e))
            resultados.append(False)
    
    return all(resultados)


def test_dependencias():
    """Test 2: Verificar librerías externas instaladas"""
    print(f"\n{BOLD}{AZUL}[TEST 2] Dependencias externas{RESET}")
    
    dependencias = [
        ("qrcode", "qrcode"),
        ("reportlab", "reportlab"),
        ("PIL", "Pillow"),
    ]
    
    resultados = []
    for lib, nombre in dependencias:
        try:
            __import__(lib)
            print_resultado(f"Librería {nombre}", True)
            resultados.append(True)
        except ImportError as e:
            print_resultado(f"Librería {nombre}", False, "Instala con: pip install" + " " + nombre.lower())
            resultados.append(False)
    
    # Test pywin32 con advertencia
    try:
        import win32print
        print_resultado("Librería pywin32 (Windows)", True)
        resultados.append(True)
    except ImportError:
        print_resultado("Librería pywin32 (Windows)", False, "Opcional - Instalada solo si necesitas impresoras")
        resultados.append(True)  # No es bloqueante
    
    return all(resultados)


def test_base_datos():
    """Test 3: Verificar acceso a base de datos"""
    print(f"\n{BOLD}{AZUL}[TEST 3] Base de Datos{RESET}")
    
    try:
        import sqlite3
        
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Verificar tablas existentes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tablas = [row[0] for row in cursor.fetchall()]
            
            print_resultado("Conexión a database.db", True, f"{len(tablas)} tablas encontradas")
            
            # Listar tablas
            tablas_importantes = ['inventario', 'ventas', 'presupuestos', 'albaranes']
            for tabla in tablas_importantes:
                if tabla in tablas:
                    print(f"  {VERDE}✓{RESET} Tabla '{tabla}' existe")
                else:
                    print(f"  {AMARILLO}~{RESET} Tabla '{tabla}' no existe (se creará al usar)")
            
            conn.close()
            return True
        else:
            print_resultado("Base de datos database.db", False, "Archivo no encontrado")
            return False
    
    except Exception as e:
        print_resultado("Acceso a base de datos", False, str(e))
        return False


def test_estructura_proyecto():
    """Test 4: Verificar estructura de archivos"""
    print(f"\n{BOLD}{AZUL}[TEST 4] Estructura de archivos{RESET}")
    
    archivos_esperados = [
        "app.py",
        "manager.py",
        "container.py",
        "ventas.py",
        "inventario.py",
        "ajustes.py",
        "config.py",
        "facturas_verifactu.py",
        "tickets.py",
        "albaranes.py",
        "presupuestos.py",
        "impresoras.py",
        "barcode_scanner.py",
    ]
    
    resultados = []
    for archivo in archivos_esperados:
        ruta = os.path.join(SCRIPT_DIR, archivo)
        existe = os.path.exists(ruta)
        if existe:
            print_resultado(f"Archivo {archivo}", True)
            resultados.append(True)
        else:
            print_resultado(f"Archivo {archivo}", False, "Descárgalo o créalo")
            resultados.append(False)
    
    if os.path.exists(DB_PATH):
        print_resultado("Base de datos database.db", True)
        resultados.append(True)
    else:
        print_resultado("Base de datos database.db", False, "Se crea al usar la aplicación")
        resultados.append(False)
    
    return all(resultados)


def test_funcionalidad_basica():
    """Test 5: Pruebas funcionales básicas"""
    print(f"\n{BOLD}{AZUL}[TEST 5] Funcionalidad básica{RESET}")
    
    resultados = []
    
    # Test FacturaVeriFACTU
    try:
        from reyger.facturas_verifactu import FacturaVeriFACTU
        factura = FacturaVeriFACTU()
        print_resultado("Instanciar FacturaVeriFACTU", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar FacturaVeriFACTU", False, str(e))
        resultados.append(False)
    
    # Test TicketSimplificado
    try:
        from reyger.tickets import TicketSimplificado
        ticket = TicketSimplificado()
        print_resultado("Instanciar TicketSimplificado", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar TicketSimplificado", False, str(e))
        resultados.append(False)
    
    # Test AlbaranEntrega
    try:
        from reyger.albaranes import AlbaranEntrega
        albaran = AlbaranEntrega()
        print_resultado("Instanciar AlbaranEntrega", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar AlbaranEntrega", False, str(e))
        resultados.append(False)
    
    # Test Presupuestos (Frame tkinter: necesita un parent)
    try:
        from reyger.presupuestos import Presupuestos
        root = tk.Tk()
        root.withdraw()
        presupuestos = Presupuestos(root)
        root.destroy()
        print_resultado("Instanciar Presupuestos", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar Presupuestos", False, str(e))
        resultados.append(False)
    
    # Test EscanerCodigoBarras
    try:
        from reyger.barcode_scanner import EscanerCodigoBarras
        escaner = EscanerCodigoBarras()
        print_resultado("Instanciar EscanerCodigoBarras", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar EscanerCodigoBarras", False, str(e))
        resultados.append(False)
    
    # Test GestorImpresoras
    try:
        from reyger.impresoras import GestorImpresoras
        gestor = GestorImpresoras()
        print_resultado("Instanciar GestorImpresoras", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar GestorImpresoras", False, str(e))
        resultados.append(False)
    
    return all(resultados)


def test_directorios_salida():
    """Test 6: Verificar directorios de salida"""
    print(f"\n{BOLD}{AZUL}[TEST 6] Directorios de salida{RESET}")
    
    directorios = [
        ("facturas", "Facturas ordinarias"),
        ("facturas_verifactu", "Facturas VeriFACTU"),
        ("tickets", "Tickets"),
        ("albaranes", "Albaranes"),
        ("presupuestos_pdf", "Presupuestos PDF"),
    ]
    
    resultados = []
    for directorio, descripcion in directorios:
        if os.path.exists(os.path.join(PROJECT_ROOT, directorio)):
            print_resultado(f"Directorio {descripcion} (/{directorio})", True)
            resultados.append(True)
        else:
            print(f"  {AMARILLO}→ Se creará automáticamente al generar{RESET}")
            resultados.append(True)  # No es bloqueante
    
    return True


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
        test_imports(),
        test_dependencias(),
        test_base_datos(),
        test_estructura_proyecto(),
        test_funcionalidad_basica(),
        test_directorios_salida(),
    ]
    
    # Mostrar resumen
    exito = mostrar_resumen(tests)
    
    # Información adicional
    print(f"{BOLD}Próximos pasos:{RESET}")
    print(f"  1. Ejecuta: {AMARILLO}python -m reyger{RESET}")
    print(f"  2. Abre menú Presupuestos (nuevo botón púrpura)")
    print(f"  3. Prueba los métodos de pago en Ventas")
    print(f"  4. Genera facturas y tickets\n")
    
    return 0 if exito else 1


if __name__ == "__main__":
    exit(main())
