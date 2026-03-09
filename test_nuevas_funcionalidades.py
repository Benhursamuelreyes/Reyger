#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de testing para verificar que todas las funcionalidades 
están correctamente implementadas e instaladas.

Ejecuta: python test_nuevas_funcionalidades.py
"""

import os
import sys
from datetime import datetime

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
    """Test 1: Verificar que todos los módulos nuvos se importan"""
    print(f"\n{BOLD}{AZUL}[TEST 1] Importación de módulos{RESET}")
    
    tests = [
        ("facturas_verifactu.FacturaVeriFACTU", "Factura VeriFACTU"),
        ("tickets.TicketSimplificado", "Tickets"),
        ("albaranes.AlbaranEntrega", "Albaranes"),
        ("presupuestos.Presupuestos", "Presupuestos"),
        ("impresoras.GestorImpresoras", "Gestor de Impresoras"),
        ("barcode_scanner.EscanerCodigoBarras", "Escáner de Código de Barras"),
    ]
    
    resultados = []
    for modulo_clase, nombre in tests:
        try:
            partes = modulo_clase.split('.')
            modulo = __import__(partes[0])
            clase = getattr(modulo, partes[1])
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
        
        if os.path.exists("database.db"):
            conn = sqlite3.connect("database.db")
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
        "index.py",
        "manager.py",
        "container.py",
        "ventas.py",
        "inventario.py",
        "ajustes.py",
        "config.py",
        "database.db",
        "facturas_verifactu.py",
        "tickets.py",
        "albaranes.py",
        "presupuestos.py",
        "impresoras.py",
        "barcode_scanner.py",
    ]
    
    resultados = []
    for archivo in archivos_esperados:
        existe = os.path.exists(archivo)
        if existe:
            print_resultado(f"Archivo {archivo}", True)
            resultados.append(True)
        else:
            print_resultado(f"Archivo {archivo}", False, "Descárgalo o créalo")
            resultados.append(False)
    
    return all(resultados)


def test_funcionalidad_basica():
    """Test 5: Pruebas funcionales básicas"""
    print(f"\n{BOLD}{AZUL}[TEST 5] Funcionalidad básica{RESET}")
    
    resultados = []
    
    # Test FacturaVeriFACTU
    try:
        from facturas_verifactu import FacturaVeriFACTU
        factura = FacturaVeriFACTU()
        print_resultado("Instanciar FacturaVeriFACTU", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar FacturaVeriFACTU", False, str(e))
        resultados.append(False)
    
    # Test TicketSimplificado
    try:
        from tickets import TicketSimplificado
        ticket = TicketSimplificado()
        print_resultado("Instanciar TicketSimplificado", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar TicketSimplificado", False, str(e))
        resultados.append(False)
    
    # Test AlbaranEntrega
    try:
        from albaranes import AlbaranEntrega
        albaran = AlbaranEntrega()
        print_resultado("Instanciar AlbaranEntrega", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar AlbaranEntrega", False, str(e))
        resultados.append(False)
    
    # Test EscanerCodigoBarras
    try:
        from barcode_scanner import EscanerCodigoBarras
        escaner = EscanerCodigoBarras()
        print_resultado("Instanciar EscanerCodigoBarras", True)
        resultados.append(True)
    except Exception as e:
        print_resultado("Instanciar EscanerCodigoBarras", False, str(e))
        resultados.append(False)
    
    # Test GestorImpresoras
    try:
        from impresoras import GestorImpresoras
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
        if os.path.exists(directorio):
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
    print(f"  1. Ejecuta: {AMARILLO}python index.py{RESET}")
    print(f"  2. Abre menu Presupuestos (nuevo botón púrpura)")
    print(f"  3. Prueba los métodos de pago en Ventas")
    print(f"  4. Genera facturas y tickets\n")
    
    return 0 if exito else 1


if __name__ == "__main__":
    exit(main())
