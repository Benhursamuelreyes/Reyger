"""Pruebas de la correlatividad fiscal de tickets y facturas (Módulo 1).

Cubre la garantía de NO retroceso de la secuencia: una vez emitido un
número oficial, borrar físicamente la venta más alta (o cualquier otra)
no vuelve a ofrecer números ya usados, porque el máximo se persiste en
``contadores_documentos``.
"""

import os
import sqlite3
import sys
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

AZUL = "\033[94m"
VERDE = "\033[92m"
ROJO = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" -> {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def bd_temporal():
    """Crea un directorio temporal aislado y devuelve (tmp, ruta)."""
    tmp = tempfile.mkdtemp(prefix="reyger_correl_")
    return tmp, os.path.join(tmp, "tienda.db")


def bd_migrada_a_v10():
    """Aplica todas las migraciones sobre una BD nueva y la devuelve."""
    import reyger.core.db as db

    tmp, ruta = bd_temporal()
    anterior = db.get_db_path
    db.close()
    db.get_db_path = lambda: ruta

    conn = sqlite3.connect(ruta)
    conn.executescript(
        """
        CREATE TABLE ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura TEXT, nombre_articulo TEXT, valor_articulo REAL,
            cantidad INTEGER, subtotal REAL, metodo_pago TEXT,
            cantidad_efectivo REAL, cantidad_tarjeta REAL, fecha TEXT,
            cliente_id INTEGER, tipo_iva REAL, cuota_iva REAL,
            base_imponible REAL
        );
        PRAGMA user_version = 0;
        """
    )
    conn.commit()

    import reyger.core.migrations as migraciones
    migraciones.run_migrations(conn)
    conn.commit()
    conn.close()
    return tmp, ruta, anterior


def test_no_retrocede_tras_borrar_venta_maxima():
    print(f"\n{BOLD}{AZUL}[TEST 1] La secuencia no retrocede al borrar la venta máxima{RESET}")
    from reyger.core import correlativos
    import reyger.core.db as db

    tmp, ruta, anterior = bd_migrada_a_v10()

    cifras = {
        "id": 1, "nombre_articulo": "A", "valor_articulo": 1.0,
        "cantidad": 1, "subtotal": 1.0, "metodo_pago": "Efectivo",
        "cantidad_efectivo": 1.0, "cantidad_tarjeta": 0.0,
        "tipo_iva": 21.0, "cuota_iva": 0.21, "base_imponible": 1.0,
    }

    conn = db.get_connection()
    # Emitir tickets 1..3 de forma manual (como haría la app) y reservarlos.
    for n in range(1, 4):
        prefijo, numero = correlativos.siguiente_numero("ticket")
        assert numero == n
        correlativos.reservar_numero("ticket", numero, prefijo)
        conn.execute(
            "INSERT INTO ventas (factura, nombre_articulo, valor_articulo, "
            "cantidad, subtotal, metodo_pago, cantidad_efectivo, "
            "cantidad_tarjeta, tipo_iva, cuota_iva, base_imponible, "
            "tipo_documento, estado, numero_ticket) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ticket', 'emitido', ?)",
            (
                prefijo + f"{numero:04d}", cifras["nombre_articulo"],
                cifras["valor_articulo"], cifras["cantidad"], cifras["subtotal"],
                cifras["metodo_pago"], cifras["cantidad_efectivo"],
                cifras["cantidad_tarjeta"], cifras["tipo_iva"],
                cifras["cuota_iva"], cifras["base_imponible"],
                prefijo + f"{numero:04d}",
            ),
        )
    conn.commit()

    # Borrar físicamente la venta más alta (T-3).
    conn.execute("DELETE FROM ventas WHERE numero_ticket = 'T-0003'")
    conn.commit()

    # Aun borrado el máximo en ventas, el contador persistente evita el retroceso.
    prefijo, numero = correlativos.siguiente_numero("ticket")
    chequear("Tras borrar T-3 el siguiente es 4 (NO 3)", numero == 4, f"obtenido {numero}")

    db.close()
    db.get_db_path = anterior
    return 0


def test_serie_configurable_arranca_desde_inicio():
    print(f"\n{BOLD}{AZUL}[TEST 2] Serie configurable (inicio embebido){RESET}")
    import reyger.core.db as db

    tmp, ruta, anterior = bd_migrada_a_v10()
    conn = db.get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO business_profile (id, numero_serie_ticket) "
        "VALUES (1, 'TK-100')"
    )
    conn.commit()

    from reyger.core import correlativos
    prefijo, numero = correlativos.siguiente_numero("ticket")
    chequear("Serie 'TK-100' arranca en 100", prefijo == "TK-" and numero == 100,
             f"{prefijo}{numero}")

    db.close()
    db.get_db_path = anterior
    return 0


def main():
    test_no_retrocede_tras_borrar_venta_maxima()
    test_serie_configurable_arranca_desde_inicio()
    print()
    if FALLOS:
        print(f"{ROJO}{BOLD}FALLARON {len(FALLOS)} comprobaciones:{RESET}")
        for nombre in FALLOS:
            print(f"  - {nombre}")
        return 1
    print(f"{VERDE}{BOLD}Todos los tests de correlatividad pasaron.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
