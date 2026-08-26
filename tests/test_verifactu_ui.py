"""Tests de la sección VeriFactu en la UI de Ajustes."""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _bd_temporal(tmp_path):
    """Redirige la capa de datos a una BD temporal."""
    import reyger.core.db as modulo_db

    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original


def _silenciar_messageboxes():
    """Evita que messagebox.showinfo/showerror bloqueen la UI en tests."""
    from unittest.mock import patch
    from tkinter import messagebox
    patcher_info = patch.object(messagebox, "showinfo", lambda *a, **k: None)
    patcher_error = patch.object(messagebox, "showerror", lambda *a, **k: None)
    patcher_warn = patch.object(messagebox, "showwarning", lambda *a, **k: None)
    patcher_info.start()
    patcher_error.start()
    patcher_warn.start()
    return patcher_info, patcher_error, patcher_warn


def test_seccion_verifactu_crea_widgets():
    """La sección VeriFactu crea las etiquetas de estado y botones."""
    import tkinter as tk
    from reyger.ui.ajustes import Ajustes

    patchers = _silenciar_messageboxes()
    try:
        root = tk.Tk()
        root.withdraw()
        panel = Ajustes(root)

        assert hasattr(panel, "_verifactu_estado_labels")
        assert "pendientes" in panel._verifactu_estado_labels
        assert "enviadas" in panel._verifactu_estado_labels
        assert "errores" in panel._verifactu_estado_labels
        assert hasattr(panel, "_verifactu_label_resultado")
        panel.destroy()
    finally:
        for p in patchers:
            p.stop()


def test_estado_inicial_cero():
    """Las etiquetas muestran 0 al inicio."""
    import tkinter as tk
    from reyger.ui.ajustes import Ajustes

    patchers = _silenciar_messageboxes()
    try:
        root = tk.Tk()
        root.withdraw()
        panel = Ajustes(root)

        for clave in ("pendientes", "enviadas", "errores"):
            texto = panel._verifactu_estado_labels[clave].cget("text")
            assert texto == "0", f"Esperaba '0' en {clave}, obtuve '{texto}'"
        panel.destroy()
    finally:
        for p in patchers:
            p.stop()


def test_verificar_cadena_vacia():
    """Verificar cadena sin facturas muestra mensaje informativo."""
    import tkinter as tk
    from reyger.ui.ajustes import Ajustes

    patchers = _silenciar_messageboxes()
    try:
        root = tk.Tk()
        root.withdraw()
        panel = Ajustes(root)

        panel._verifactu_verificar_cadena()
        texto = panel._verifactu_label_resultado.cget("text")
        assert "No hay facturas" in texto
        panel.destroy()
    finally:
        for p in patchers:
            p.stop()


def test_verificar_cadena_integra():
    """Verificar cadena con facturas correctas muestra OK."""
    import tkinter as tk
    import reyger.core.db as modulo_db
    from reyger.ui.ajustes import Ajustes
    from reyger.domain.verifactu_hash import calcular_huella

    patchers = _silenciar_messageboxes()
    try:
        root = tk.Tk()
        root.withdraw()
        panel = Ajustes(root)

        conn = modulo_db.get_connection()
        h1 = calcular_huella(
            nif="B12345678", num_serie="V-1", fecha="01-01-2024",
            tipo_comprobante="F1", cuota_total=21.0, importe_total=121.0,
            huella_anterior="", fecha_hora_gen="2024-01-01T10:00:00+01:00",
        )
        conn.execute(
            "INSERT INTO facturas_verifactu "
            "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
            "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
            "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion, "
            "estado_envio) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("V-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente",
             100.0, 21, 21.0, 121.0, h1, "", 1, "F1", "cadena1",
             "2024-01-01T10:00:00+01:00", "pendiente"),
        )
        conn.commit()

        panel._verifactu_verificar_cadena()
        texto = panel._verifactu_label_resultado.cget("text")
        assert "íntegra" in texto or "correctamente" in texto
        panel.destroy()
    finally:
        for p in patchers:
            p.stop()


def test_refrescar_estado():
    """refrescar_estado actualiza las etiquetas desde la BD."""
    import tkinter as tk
    import reyger.core.db as modulo_db
    from reyger.ui.ajustes import Ajustes
    from reyger.domain.verifactu_hash import calcular_huella

    patchers = _silenciar_messageboxes()
    try:
        root = tk.Tk()
        root.withdraw()
        panel = Ajustes(root)

        conn = modulo_db.get_connection()
        h1 = calcular_huella(
            nif="B12345678", num_serie="W-1", fecha="01-01-2024",
            tipo_comprobante="F1", cuota_total=0.0, importe_total=50.0,
            huella_anterior="", fecha_hora_gen="2024-01-01T10:00:00+01:00",
        )
        conn.execute(
            "INSERT INTO facturas_verifactu "
            "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
            "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
            "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion, "
            "estado_envio) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("W-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente",
             50.0, 21, 0.0, 50.0, h1, "", 1, "F1", "cadena1",
             "2024-01-01T10:00:00+01:00", "pendiente"),
        )
        conn.commit()

        panel._verifactu_refrescar_estado()
        assert panel._verifactu_estado_labels["pendientes"].cget("text") == "1"
        assert panel._verifactu_estado_labels["enviadas"].cget("text") == "0"
        panel.destroy()
    finally:
        for p in patchers:
            p.stop()
