"""Pruebas de impresión directa (Módulo 3): presupuestos y albaranes.

Verifica que "Enviar a impresora" (presupuestos) y "Imprimir…"
(albaranes) generan/ubican el PDF A4 y lo entregan al diálogo de
selección de impresora sin enviarlo nunca a la térmica de tickets.
"""

import os
import sys
import tkinter as tk

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from reyger.hardware import impresoras as hw_impresoras


class DialogoFalso:
    """Sustituye a DialogoSeleccionImpresora para no abrir Toplevel real."""

    ultimo = None

    def __init__(self, parent, ruta_archivo, gestor_impresoras=None):
        self.parent = parent
        self.ruta_archivo = ruta_archivo
        type(self).ultimo = self


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def presupuesto(root):
    from reyger.ui.presupuestos import Presupuestos

    ventana = Presupuestos(root)
    ventana.entry_cliente.insert(0, "Cliente de prueba")
    ventana.tree.insert("", "end", values=("Producto A", 1.0, 10.0, 10.0))
    return ventana


def _limpiar(ruta):
    if ruta:
        try:
            os.remove(ruta)
        except OSError:
            pass


def test_presupuesto_genera_pdf_temporal(presupuesto):
    ruta = presupuesto._generar_pdf_temporal()
    try:
        assert ruta
        assert ruta.endswith(".pdf")
        assert os.path.exists(ruta)
    finally:
        _limpiar(ruta)


def test_presupuesto_abre_visor(presupuesto, monkeypatch):
    from reyger.ui import presupuestos as mod

    abiertos = []
    monkeypatch.setattr(mod, "open_file", lambda ruta: abiertos.append(ruta))
    presupuesto._imprimir_presupuesto()
    try:
        assert abiertos, "no se abrió el visor"
        assert os.path.exists(abiertos[0])
    finally:
        _limpiar(abiertos[0] if abiertos else None)


def test_presupuesto_envia_a_impresora(presupuesto, monkeypatch):
    monkeypatch.setattr(hw_impresoras, "DialogoSeleccionImpresora", DialogoFalso)
    monkeypatch.setattr(presupuesto, "wait_window", lambda win: None)

    presupuesto._enviar_a_impresora()

    ruta = DialogoFalso.ultimo.ruta_archivo
    try:
        assert DialogoFalso.ultimo.parent is presupuesto
        assert ruta.endswith(".pdf")
        assert os.path.exists(ruta)
    finally:
        _limpiar(ruta)


def test_albaran_imprime_seleccionado(root, tmp_path, monkeypatch):
    from reyger import resources as res
    from reyger.ui.albaranes_ui import VentanaAlbaranes

    pdf = tmp_path / "Albaran_ALB-0001_20260905_120000.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(res, "get_output_path", lambda sub: str(tmp_path))
    monkeypatch.setattr(hw_impresoras, "DialogoSeleccionImpresora", DialogoFalso)

    ventana = VentanaAlbaranes(root)
    item = ventana.tree.insert(
        "", "end", values=("ALB-0001", "05/09/2026", "Cliente", "Abierto")
    )
    ventana.tree.selection_set(item)
    monkeypatch.setattr(ventana, "wait_window", lambda win: None)

    ventana.imprimir_seleccionado()

    assert DialogoFalso.ultimo.ruta_archivo == str(pdf)


def test_albaran_sin_pdf_avisa(root, tmp_path, monkeypatch):
    from reyger import resources as res
    from reyger.ui import albaranes_ui as mod_ui

    avisos = []
    monkeypatch.setattr(res, "get_output_path", lambda sub: str(tmp_path))
    monkeypatch.setattr(
        mod_ui.messagebox, "showwarning",
        lambda *a, **k: avisos.append((a, k)),
    )

    ventana = mod_ui.VentanaAlbaranes(root)
    item = ventana.tree.insert(
        "", "end", values=("ALB-0002", "05/09/2026", "Cliente", "Abierto")
    )
    ventana.tree.selection_set(item)

    ventana.imprimir_seleccionado()

    assert avisos and "ALB-0002" in avisos[0][0][1]
    assert DialogoFalso.ultimo is None or DialogoFalso.ultimo.ruta_archivo != "ALB-0002"


def test_albaran_sin_seleccion_avisa(root, tmp_path, monkeypatch):
    from reyger import resources as res
    from reyger.ui import albaranes_ui as mod_ui

    avisos = []
    monkeypatch.setattr(res, "get_output_path", lambda sub: str(tmp_path))
    monkeypatch.setattr(
        mod_ui.messagebox, "showwarning",
        lambda *a, **k: avisos.append((a, k)),
    )

    ventana = mod_ui.VentanaAlbaranes(root)
    ventana.imprimir_seleccionado()

    assert avisos