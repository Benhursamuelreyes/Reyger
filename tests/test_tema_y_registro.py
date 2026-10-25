"""Tests del tema oscuro aplicado por defecto y del registro en fichero.

Cubren la base de opciones de Tk (los widgets sin color propio toman el del
tema), el logotipo aclarado para fondo oscuro, el fichero ``reyger.log`` y
que los errores de hilos y de eventos de Tk queden registrados.
"""

import logging
import os
import sys
import threading
import tkinter as tk

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reyger.config import ConfigManager
from reyger.core import registro
from reyger.ui.ui import aplicar_colores_por_defecto


def _colores(tema):
    gestor = ConfigManager.__new__(ConfigManager)
    gestor.config_data = {"tema": tema}
    return gestor.get_colors()


@pytest.fixture
def raiz():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("sin display para Tk")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def registro_temporal(tmp_path, monkeypatch):
    """Logger ``reyger`` limpio que escribe en *tmp_path*."""
    monkeypatch.setattr(registro, "get_user_data_path", lambda: tmp_path)
    log = logging.getLogger("reyger")
    handlers, nivel = list(log.handlers), log.level
    gancho_hilos = threading.excepthook
    for h in handlers:
        log.removeHandler(h)
    log.__dict__.pop("_reyger_configurado", None)
    yield tmp_path / registro.NOMBRE_FICHERO
    for h in list(log.handlers):
        h.close()
        log.removeHandler(h)
    for h in handlers:
        log.addHandler(h)
    log.setLevel(nivel)
    log.__dict__.pop("_reyger_configurado", None)
    threading.excepthook = gancho_hilos


# ------------------------------------------------------------------ tema
def test_ambos_temas_definen_las_mismas_claves():
    assert set(_colores("claro")) == set(_colores("oscuro"))


def test_tema_claro_conserva_los_colores_historicos():
    colores = _colores("claro")
    assert colores["bg_principal"] == "#C6D9E3"
    assert colores["bg_cabecera"] == "#dddddd"


def test_widgets_sin_color_propio_toman_el_del_tema(raiz):
    colores = _colores("oscuro")
    aplicar_colores_por_defecto(raiz, colores)
    etiqueta = tk.Label(raiz, text="x", bg=colores["bg_principal"])
    marco = tk.LabelFrame(raiz, text="x")
    entrada = tk.Entry(raiz)
    assert etiqueta.cget("fg") == colores["fg_texto"]
    assert marco.cget("fg") == colores["fg_texto"]
    assert entrada.cget("bg") == colores["entry_bg"]
    assert entrada.cget("insertbackground") == colores["entry_fg"]


def test_color_explicito_prevalece_sobre_el_tema(raiz):
    aplicar_colores_por_defecto(raiz, _colores("oscuro"))
    etiqueta = tk.Label(raiz, text="x", fg="#123456")
    assert etiqueta.cget("fg") == "#123456"


def test_logo_oscuro_aclara_el_texto_y_conserva_el_resto():
    from reyger.container import Container

    imagen = Image.new("RGBA", (2, 1))
    imagen.putpixel((0, 0), (10, 10, 10, 128))   # texto negro, borde suave
    imagen.putpixel((1, 0), (240, 150, 20, 255))  # naranja del isotipo
    resultado = Container._aclarar_trazos_oscuros(imagen, "#FFFFFF")
    assert resultado.getpixel((0, 0)) == (255, 255, 255, 128)
    assert resultado.getpixel((1, 0)) == (240, 150, 20, 255)


# -------------------------------------------------------------- registro
def test_registro_escribe_en_fichero(registro_temporal):
    log = registro.configurar_registro()
    logging.getLogger("reyger.prueba").warning("mensaje de prueba")
    for h in log.handlers:
        h.flush()
    contenido = registro_temporal.read_text(encoding="utf-8")
    assert "mensaje de prueba" in contenido
    assert "reyger.prueba" in contenido


def test_configurar_registro_es_idempotente(registro_temporal):
    registro.configurar_registro()
    n = len(logging.getLogger("reyger").handlers)
    registro.configurar_registro()
    assert len(logging.getLogger("reyger").handlers) == n


def test_excepcion_en_hilo_queda_registrada(registro_temporal):
    log = registro.configurar_registro()

    def fallar():
        raise RuntimeError("fallo en hilo")

    hilo = threading.Thread(target=fallar, name="hilo-prueba")
    hilo.start()
    hilo.join()
    for h in log.handlers:
        h.flush()
    contenido = registro_temporal.read_text(encoding="utf-8")
    assert "hilo-prueba" in contenido
    assert "RuntimeError: fallo en hilo" in contenido


def test_error_en_evento_tk_se_registra_y_avisa(registro_temporal, monkeypatch):
    from reyger.ui import manager as modulo_manager

    registro.configurar_registro()
    avisos = []
    monkeypatch.setattr(
        modulo_manager.messagebox, "showerror", lambda *a, **k: avisos.append(a)
    )
    try:
        raise ValueError("clic roto")
    except ValueError:
        modulo_manager.Manager.report_callback_exception(None, *sys.exc_info())
    for h in logging.getLogger("reyger").handlers:
        h.flush()
    assert "ValueError: clic roto" in registro_temporal.read_text(encoding="utf-8")
    assert avisos and "clic roto" in avisos[0][1]
