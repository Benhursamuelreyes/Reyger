"""Tests de la sección DATOS DEL CLIENTE en la factura PDF A4.

La plantilla ``PdfDocumento`` es común a facturas, albaranes y presupuestos.
Estos tests cubren que la factura muestre la ficha completa del cliente (NIF,
dirección, teléfono y email) y que los campos ausentes se omitan en lugar de
dejar etiquetas o valores vacíos.
"""

import os
import shutil
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_bd(tmp_path):
    """Entorno temporal con BD para los tests de datos de cliente."""
    import reyger.core.db as modulo_db

    ruta_bd = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta_bd)
    original_db = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original_db


def _crear_cliente(**campos):
    """Inserta un cliente y devuelve su id."""
    import reyger.core.db as modulo_db

    valores = {
        "nombre": "Farmacia Test SL",
        "tipo_documento": "CIF",
        "documento": "B12345678",
        "direccion": "Calle Mayor 1",
        "codigo_postal": "28001",
        "provincia": "Madrid",
        "telefono": "911223344",
        "email": "info@farmacia-test.es",
    }
    valores.update(campos)
    columnas = ", ".join(valores)
    marcadores = ", ".join("?" for _ in valores)
    return modulo_db.execute(
        f"INSERT INTO clientes ({columnas}) VALUES ({marcadores})",
        tuple(valores.values()),
    )


def _ventas_ficticias():
    """Instancia de ``Ventas`` sin Tk, con lo mínimo para generar el PDF."""
    from reyger.ui.ventas import Ventas

    ventas = object.__new__(Ventas)
    ventas.config_manager = None
    return ventas


def _filas_cliente(elementos):
    """Devuelve las filas ``[etiqueta, valor]`` de la tabla del bloque."""
    tabla = next(e for e in elementos if hasattr(e, "_cellvalues"))
    return [[str(c) for c in fila] for fila in tabla._cellvalues]


# ── Plantilla A4 ────────────────────────────────────────────────────


class TestPlantillaDatosCliente:
    """Filas que compone ``PdfDocumento._datos_cliente``."""

    def _elementos(self, *args):
        from reyger.domain.pdf_documento import PdfDocumento
        return PdfDocumento()._datos_cliente(*args)

    def test_renderiza_todos_los_campos(self):
        """Con ficha completa se muestran nombre, NIF, dirección, tel y email."""
        filas = _filas_cliente(self._elementos(
            "Farmacia Test SL",
            "Calle Mayor 1, 28001 — Madrid",
            "B12345678",
            "info@farmacia-test.es",
            "911223344",
        ))

        assert filas == [
            ["Nombre/Empresa:", "Farmacia Test SL"],
            ["NIF/VAT ID:", "B12345678"],
            ["Dirección:", "Calle Mayor 1, 28001 — Madrid"],
            ["Tel:", "911223344"],
            ["Email:", "info@farmacia-test.es"],
        ]

    def test_omite_campos_ausentes(self):
        """Sin NIF ni contacto, la dirección es el único dato opcional."""
        filas = _filas_cliente(self._elementos(
            "Consumidor Final",
            "Calle Mayor 1, 28001 — Madrid",
            None,
            None,
            None,
        ))

        assert filas == [
            ["Nombre/Empresa:", "Consumidor Final"],
            ["Dirección:", "Calle Mayor 1, 28001 — Madrid"],
        ]

    def test_solo_nombre_no_deja_etiquetas_huerfanas(self):
        """El caso reportado: sin ficha solo aparece el nombre, sin filas vacías."""
        filas = _filas_cliente(self._elementos(
            "farmacia", None, None, None, None,
        ))

        assert filas == [["Nombre/Empresa:", "farmacia"]]

    def test_telefono_sin_email_no_rompe_el_bloque(self):
        """Teléfono y email son independientes entre sí."""
        filas = _filas_cliente(self._elementos(
            "Solo Móvil", None, None, None, "600112233",
        ))

        assert filas == [["Nombre/Empresa:", "Solo Móvil"], ["Tel:", "600112233"]]

    def test_argumento_telefono_es_opcional(self):
        """La firma antigua (4 argumentos) sigue siendo válida."""
        filas = _filas_cliente(self._elementos(
            "Retrocompatible", None, "B12345678", "correo@test.es",
        ))

        assert ["NIF/VAT ID:", "B12345678"] in filas
        assert ["Email:", "correo@test.es"] in filas


# ── Lectura de la ficha del cliente ──────────────────────────────────


class TestDatosFacturacionCliente:
    """``Ventas._datos_facturacion_cliente`` adapta la fila de ``clientes``."""

    def test_lee_ficha_completa(self):
        """Mapea ``documento``/``telefono``/``email`` y compone la dirección."""
        cliente_id = _crear_cliente()
        ventas = _ventas_ficticias()

        assert ventas._datos_facturacion_cliente(cliente_id) == (
            "B12345678",
            "Calle Mayor 1, 28001 — Madrid",
            "911223344",
            "info@farmacia-test.es",
        )

    def test_compone_direccion_con_calle_y_provincia(self):
        """Calle + CP + provincia se unen con el formato del membrete emisor."""
        cliente_id = _crear_cliente(
            direccion="Avda. del Mar 5", codigo_postal="46002",
            provincia="Valencia",
        )

        _, direccion, _, _ = _ventas_ficticias()._datos_facturacion_cliente(
            cliente_id
        )

        assert direccion == "Avda. del Mar 5, 46002 — Valencia"

    def test_direccion_sin_cp_no_inventa_separadores(self):
        """Sin código postal no queda una coma colgante."""
        cliente_id = _crear_cliente(direccion="Sin Postal", codigo_postal=None)

        _, direccion, _, _ = _ventas_ficticias()._datos_facturacion_cliente(
            cliente_id
        )

        assert direccion == "Sin Postal — Madrid"

    def test_direccion_sin_calle_usa_provincia(self):
        """Si no hay calle, la provincia es el único dato postal disponible."""
        cliente_id = _crear_cliente(direccion=None)

        _, direccion, _, _ = _ventas_ficticias()._datos_facturacion_cliente(
            cliente_id
        )

        assert direccion == "Madrid"

    def test_ficha_vacia_devuelve_none_en_todo(self):
        """Una ficha sin datos no produce cadenas vacías."""
        cliente_id = _crear_cliente(
            documento=None, direccion=None, codigo_postal=None,
            provincia=None, telefono=None, email=None,
        )

        assert _ventas_ficticias()._datos_facturacion_cliente(cliente_id) == (
            None, None, None, None,
        )

    def test_sin_cliente_devuelve_none_en_todo(self):
        """Venta sin cliente (ticket) no consulta ni rompe nada."""
        ventas = _ventas_ficticias()

        assert ventas._datos_facturacion_cliente(None) == (None, None, None, None)

    def test_cliente_inexistente_no_rompe(self):
        """Un id borrado de la ficha degrada a bloque sin datos."""
        assert _ventas_ficticias()._datos_facturacion_cliente(999999) == (
            None, None, None, None,
        )


# ── Factura completa ────────────────────────────────────────────────


class TestGenerarFacturaPdf:
    """``Ventas.generar_factura_pdf`` propaga la ficha a la plantilla A4."""

    def _generar(self, ventas, salida, **kwargs):
        with patch(
            "reyger.ui.ventas.get_output_path", return_value=str(salida)
        ), patch("reyger.ui.ventas.open_file"), patch(
            "reyger.ui.ventas.messagebox"
        ):
            return ventas.generar_factura_pdf(
                productos=[("Paracetamol", 5.0, 2, 10.0)],
                total=12.1,
                factura_numero="F20260001",
                fecha="02/10/2026 10:00",
                base_imponible=10.0,
                cuota_iva=2.1,
                **kwargs,
            )

    def test_propaga_la_ficha_completa_a_la_plantilla(self, tmp_path):
        """El PDF recibe NIF, dirección, teléfono y email del cliente."""
        cliente_id = _crear_cliente()

        with patch(
            "reyger.domain.pdf_documento.PdfDocumento.generar"
        ) as mock_generar:
            self._generar(
                _ventas_ficticias(), tmp_path,
                cliente_nombre="Farmacia Test SL", cliente_id=cliente_id,
            )

        kwargs = mock_generar.call_args.kwargs
        assert kwargs["cliente_nombre"] == "Farmacia Test SL"
        assert kwargs["cliente_nif"] == "B12345678"
        assert kwargs["cliente_direccion"] == "Calle Mayor 1, 28001 — Madrid"
        assert kwargs["cliente_telefono"] == "911223344"
        assert kwargs["cliente_email"] == "info@farmacia-test.es"

    def test_genera_pdf_real_con_la_ficha_completa(self, tmp_path):
        """El render con todos los campos produce un PDF con contenido real."""
        cliente_id = _crear_cliente()

        self._generar(
            _ventas_ficticias(), tmp_path,
            cliente_nombre="Farmacia Test SL", cliente_id=cliente_id,
        )

        pdfs = list(tmp_path.glob("factura_*.pdf"))
        assert len(pdfs) == 1, "Debería generarse exactamente un PDF"
        assert pdfs[0].stat().st_size > 500, "El PDF debe tener contenido real"

    def test_consumidor_final_no_falla_sin_cliente(self, tmp_path):
        """Factura sin cliente seleccionado se genera con solo el nombre."""
        with patch(
            "reyger.domain.pdf_documento.PdfDocumento.generar"
        ) as mock_generar:
            self._generar(_ventas_ficticias(), tmp_path, cliente_nombre=None)

        kwargs = mock_generar.call_args.kwargs
        assert kwargs["cliente_nombre"] == "(Consumidor final)"
        assert kwargs["cliente_nif"] is None
        assert kwargs["cliente_direccion"] is None
        assert kwargs["cliente_telefono"] is None
        assert kwargs["cliente_email"] is None
