"""Tests de la tanda «Ver facturas»: PDF bloqueado, historial, borradores y membrete.

* ``Permission denied`` al regenerar ``factura_<n>.pdf`` mientras el visor
  de Windows lo tenía abierto.
* Historial con un documento por fila, borrado solo de borradores y
  asignación de cliente a un borrador antiguo sin cliente.
* Membrete vertical y centrado, con WhatsApp.
"""

import os
import shutil
import sqlite3
import stat
from unittest.mock import patch

import pytest

import reyger.core.db as modulo_db
import reyger.resources as resources
from reyger.core import migrations
from reyger.domain import ventas as dv

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def bd(tmp_path, monkeypatch):
    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    conn = sqlite3.connect(ruta)
    migrations.run_migrations(conn)
    conn.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)"
        " VALUES ('Café', 'Prov', 2.20, 1.0, 10, 10)"
    )
    conn.execute(
        "INSERT INTO clientes (nombre, tipo_documento, documento) "
        "VALUES ('Farmacia Test SL', 'CIF', 'B12345678')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(modulo_db, "get_db_path", lambda: ruta)
    modulo_db.close()
    yield ruta
    modulo_db.close()


def _carrito():
    id_cafe = modulo_db.query_one("SELECT id FROM inventario WHERE nombre = 'Café'")["id"]
    return [dv.LineaVenta("Café", 2.20, 2, 10.0, id_cafe)]


def _id_cliente():
    return modulo_db.query_one("SELECT id FROM clientes")["id"]


# ── Rutas de salida ────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="chmod no bloquea aquí")
def test_ruta_escribible_esquiva_pdf_bloqueado(tmp_path):
    bloqueado = tmp_path / "factura_F-0001.pdf"
    bloqueado.write_bytes(b"%PDF")
    bloqueado.chmod(stat.S_IREAD)  # como el visor de Windows: no se puede reescribir
    try:
        assert resources.ruta_escribible(str(bloqueado)) == str(tmp_path / "factura_F-0001_1.pdf")
    finally:
        bloqueado.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_ruta_escribible_reutiliza_fichero_libre(tmp_path):
    libre = tmp_path / "factura_F-0002.pdf"
    assert resources.ruta_escribible(str(libre)) == str(libre)
    libre.write_bytes(b"%PDF")
    assert resources.ruta_escribible(str(libre)) == str(libre)


def test_get_output_path_recurre_a_otra_carpeta_sin_permisos(tmp_path, monkeypatch):
    principal = resources.get_user_data_path() / "facturas"
    monkeypatch.setattr(resources.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        resources, "_carpeta_escribible",
        lambda path: path != principal and (path.mkdir(parents=True, exist_ok=True) or True),
    )
    assert resources.get_output_path("facturas") == str(tmp_path / "Documents" / "Reyger" / "facturas")


# ── Dominio ────────────────────────────────────────────────────────


def test_listar_documentos_una_fila_por_documento():
    emitida = dv.registrar_venta(_carrito() * 2, "factura", "Efectivo", 20.0, cliente_id=_id_cliente())
    borrador = dv.guardar_borrador(_carrito(), None)

    filas = dv.listar_documentos()
    assert [f["numero"] for f in filas] == [borrador.numero, emitida.numero]
    assert filas[1]["cliente"] == "Farmacia Test SL"
    assert filas[1]["total"] == pytest.approx(8.80)
    assert filas[0]["cliente"] is None and filas[0]["estado"] == "borrador"


def test_leer_documento_incluye_fecha_tipo_y_estado():
    doc = dv.leer_documento(dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0).numero)
    assert doc.tipo == "ticket" and doc.estado == "emitido"
    assert doc.fecha and doc.fecha[4] == "-"


def test_borrar_no_oficial_respeta_las_oficiales():
    borrador = dv.guardar_borrador(_carrito(), _id_cliente())
    emitida = dv.registrar_venta(_carrito(), "factura", "Efectivo", 5.0, cliente_id=_id_cliente())
    prueba = dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0, prueba=True)

    assert dv.borrar_no_oficial(emitida.numero) is False
    assert dv.leer_documento(emitida.numero).productos
    assert dv.borrar_no_oficial(prueba.numero) is True
    assert dv.borrar_no_oficial(borrador.numero) is True
    assert not dv.leer_documento(borrador.numero).productos
    assert modulo_db.query_one(
        "SELECT COUNT(*) AS n FROM lineas_documento l "
        "LEFT JOIN documentos d ON d.id = l.documento_id WHERE d.id IS NULL"
    )["n"] == 0


def test_asignar_cliente_borrador():
    borrador = dv.guardar_borrador(_carrito(), None)
    assert dv.asignar_cliente_borrador(borrador.numero, _id_cliente()) is True
    assert dv.leer_documento(borrador.numero).cliente_id == _id_cliente()
    emitida = dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0)
    assert dv.asignar_cliente_borrador(emitida.numero, _id_cliente()) is False


# ── Interfaz ───────────────────────────────────────────────────────


def _ventas():
    from reyger.ui.ventas import Ventas

    ventas = object.__new__(Ventas)
    ventas.config_manager = None
    return ventas


class _TreeFalso:
    def __init__(self, numero):
        self._numero = numero

    def selection(self):
        return (self._numero,)


def test_borrar_documento_emitido_se_rechaza():
    emitida = dv.registrar_venta(_carrito(), "factura", "Efectivo", 5.0, cliente_id=_id_cliente())
    with patch("reyger.ui.ventas.messagebox") as mb:
        _ventas().borrar_documento(_TreeFalso(emitida.numero))
    mb.showwarning.assert_called_once()
    mb.askyesno.assert_not_called()
    assert dv.leer_documento(emitida.numero).productos


def test_borrar_documento_borrador_confirmado():
    borrador = dv.guardar_borrador(_carrito(), _id_cliente())
    recargado = []
    with patch("reyger.ui.ventas.messagebox") as mb:
        mb.askyesno.return_value = True
        _ventas().borrar_documento(_TreeFalso(borrador.numero), lambda: recargado.append(1))
    assert not dv.leer_documento(borrador.numero).productos
    assert recargado == [1]


def test_pdf_de_borrador_lleva_cliente_y_subtitulo_de_borrador(tmp_path):
    borrador = dv.leer_documento(dv.guardar_borrador(_carrito(), _id_cliente()).numero)
    with patch("reyger.ui.ventas.get_output_path", return_value=str(tmp_path)), patch(
        "reyger.domain.pdf_documento.PdfDocumento.generar", return_value="x.pdf"
    ) as generar:
        assert _ventas()._pdf_documento(borrador, abrir=False) == "x.pdf"
    kwargs = generar.call_args.kwargs
    assert kwargs["subtitulo_documento"] == "BORRADOR DE FACTURA — SIN VALIDEZ FISCAL"
    assert kwargs["marca_agua"] == "BORRADOR"
    assert kwargs["cliente_nombre"] == "Farmacia Test SL"
    assert kwargs["cliente_nif"] == "B12345678"


def test_pdf_existente_elige_la_variante_mas_reciente(tmp_path):
    from reyger.ui.ventas import _pdf_existente

    viejo = tmp_path / "factura_F-0001.pdf"
    nuevo = tmp_path / "factura_F-0001_1.pdf"
    (tmp_path / "factura_F-00011.pdf").write_bytes(b"otra factura")
    viejo.write_bytes(b"%PDF")
    nuevo.write_bytes(b"%PDF")
    os.utime(viejo, (1, 1))
    assert _pdf_existente(str(tmp_path), "F-0001") == str(nuevo)
    assert _pdf_existente(str(tmp_path), "F-0099") is None


# ── Membrete ───────────────────────────────────────────────────────


def test_membrete_vertical_centrado_con_whatsapp():
    from reyger.domain.pdf_documento import PdfDocumento
    from reyger.ui import business_profile as bp

    bp.guardar(nombre="Reyger SL", nif="B11111111", telefono="912345678",
               whatsapp="+34 600 111 222", email="info@reyger.es")
    elementos = PdfDocumento()._membrete("Reyger SL")
    textos = [e.text for e in elementos if hasattr(e, "text")]

    # Un dato por línea, en este orden, y todos centrados.
    assert textos[1:] == [
        "NIF: B11111111", "Tel: 912345678",
        "WhatsApp: +34 600 111 222", "Email: info@reyger.es",
    ]
    assert all(e.style.alignment == 1 for e in elementos if hasattr(e, "style"))


def test_abrir_pdf_de_borrador_genera_y_abre(tmp_path):
    """«Abrir» un borrador no hacía nada: ahora genera su PDF y lo abre."""
    borrador = dv.guardar_borrador(_carrito(), _id_cliente())
    with patch("reyger.ui.ventas.get_output_path", return_value=str(tmp_path)), patch(
        "reyger.ui.ventas.open_file"
    ) as abrir, patch("reyger.ui.ventas.messagebox") as mb:
        _ventas().abrir_documento_pdf(_TreeFalso(borrador.numero))
    mb.showerror.assert_not_called()
    ruta = abrir.call_args.args[0]
    assert ruta == str(tmp_path / f"factura_{borrador.numero}.pdf")
    assert os.path.getsize(ruta) > 0


# ── Modo pruebas ───────────────────────────────────────────────────


def _stock_cafe():
    return modulo_db.query_one("SELECT stock FROM inventario WHERE nombre = 'Café'")["stock"]


def test_venta_de_prueba_no_toca_stock_ni_serie_oficial():
    from reyger.core import correlativos

    antes = correlativos.siguiente_numero("factura")
    primera = dv.registrar_venta(_carrito(), "factura", "Efectivo", 5.0, prueba=True)
    segunda = dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0, prueba=True)

    assert (primera.numero, segunda.numero) == ("PRUEBA-0001", "PRUEBA-0002")
    assert primera.correlativo is None
    assert _stock_cafe() == 10
    assert correlativos.siguiente_numero("factura") == antes
    oficial = dv.registrar_venta(_carrito(), "factura", "Efectivo", 5.0)
    assert oficial.correlativo == antes[1]


def test_borrador_emitido_en_pruebas():
    borrador = dv.guardar_borrador(_carrito(), _id_cliente())
    doc = dv.emitir_borrador(borrador.numero, prueba=True)
    assert doc.numero == "PRUEBA-0001" and doc.estado == "emitido"
    assert _stock_cafe() == 10


def test_informes_excluyen_pruebas():
    from datetime import date

    from reyger.domain import informes

    dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0, prueba=True)
    dv.registrar_venta(_carrito(), "ticket", "Efectivo", 5.0)
    informe = informes.informe_ventas(date(2000, 1, 1), date(2100, 1, 1))
    assert informe.documentos == 1


@pytest.mark.parametrize("estado, numero, subtitulo, marca", [
    ("borrador", "BORRADOR-x", "BORRADOR DE FACTURA — SIN VALIDEZ FISCAL", "BORRADOR"),
    ("emitido", "PRUEBA-0001", "FACTURA DE PRUEBA — SIN VALIDEZ FISCAL", "PRUEBA"),
    ("emitido", "F-0001", "FACTURA", None),
])
def test_presentacion_distingue_borrador_prueba_y_oficial(estado, numero, subtitulo, marca):
    from reyger.ui.ventas import _estado_visible, _presentacion

    assert _presentacion(estado, "factura", numero) == {"subtitulo": subtitulo, "marca_agua": marca}
    assert _estado_visible(estado, numero) == {
        "BORRADOR": "Borrador", "PRUEBA": "Prueba", None: "Oficial"}[marca]


def test_pdf_con_marca_de_agua(tmp_path):
    from reyger.domain.pdf_documento import PdfDocumento

    with patch.object(PdfDocumento, "_marca_agua") as marca:
        PdfDocumento().generar(str(tmp_path / "p.pdf"), "X", "FACTURA", "PRUEBA-0001",
                               "2026-10-28", "Y", marca_agua="PRUEBA")
        PdfDocumento().generar(str(tmp_path / "o.pdf"), "X", "FACTURA", "F-0001",
                               "2026-10-28", "Y")
    assert [c.args[1] for c in marca.call_args_list] == ["PRUEBA"]


def test_ticket_termico_de_prueba():
    from reyger.hardware.impresion_termica import construir_ticket_venta

    datos = construir_ticket_venta(
        "PRUEBA-0001", "28/10/2026 10:00", [("Café", 2.2, 1, 2.2, 10, 2.0, 0.2)],
        2.2, tipo_documento="prueba",
    )
    assert b"TICKET DE PRUEBA" in datos and b"SIN VALIDEZ FISCAL" in datos
