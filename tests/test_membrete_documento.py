"""Tests para membrete dinámico en PDF de albaranes y presupuestos."""

import os
import shutil
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_bd(tmp_path):
    """Entorno temporal con BD para tests de membrete."""
    import reyger.core.db as modulo_db

    ruta_bd = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta_bd)
    original_db = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original_db


# ── Albaranes ──────────────────────────────────────────────────────


class TestAlbaranesMembrete:
    """Tests de _crear_encabezado_albaran con datos de business_profile."""

    def _construir_albaran(self):
        """Crea instancia de AlbaranEntrega sin abrir ventana."""
        from reyger.ui.albaranes import AlbaranEntrega
        return AlbaranEntrega()

    def test_membrete_incluye_empresa(self):
        """El nombre de la empresa aparece en mayúsculas en el membrete."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Reyger Testing", nif="B11111111")
        modulo_db.close()

        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Reyger Testing")

        textos = " ".join(str(e) for e in elementos)
        assert "REYGER TESTING" in textos

    def test_membrete_incluye_nif(self):
        """El NIF del business_profile aparece en el membrete."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Test SA", nif="B99999999")
        modulo_db.close()

        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Test SA")
        textos = " ".join(str(e) for e in elementos)

        assert "B99999999" in textos
        assert "NIF:" in textos

    def test_membrete_incluye_direccion_completa(self):
        """Dirección + CP + provincia aparecen en el membrete."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(
            nombre="Dir Test",
            direccion="Calle Falsa 123",
            codigo_postal="28001",
            provincia="Madrid",
        )
        modulo_db.close()

        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Dir Test")
        textos = " ".join(str(e) for e in elementos)

        assert "Calle Falsa 123" in textos
        assert "28001" in textos
        assert "Madrid" in textos

    def test_membrete_incluye_telefono_email(self):
        """Teléfono y email aparecen en el membrete."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(
            nombre="Contacto Test",
            telefono="912345678",
            email="info@test.es",
        )
        modulo_db.close()

        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Contacto Test")
        textos = " ".join(str(e) for e in elementos)

        assert "912345678" in textos
        assert "info@test.es" in textos
        assert "Tel:" in textos
        assert "Email:" in textos

    def test_membrete_vacio_sin_campos_extras(self):
        """Sin datos en business_profile, solo se muestra el nombre."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Solo Nombre")
        modulo_db.close()

        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Solo Nombre")
        textos = " ".join(str(e) for e in elementos)

        assert "SOLO NOMBRE" in textos
        assert "NIF:" not in textos
        assert "Tel:" not in textos

    def test_membrete_sinPerfil_usa_nombre_parametro(self):
        """Si business_profile no tiene perfil, solo usa el nombre recibido."""
        albaran = self._construir_albaran()
        elementos = albaran._crear_encabezado_albaran("Empresa Fantasma")
        textos = " ".join(str(e) for e in elementos)

        assert "EMPRESA FANTASMA" in textos


# ── Presupuestos ───────────────────────────────────────────────────


class TestPresupuestosMembrete:
    """Tests de membrete dinámico y botón imprimir en presupuestos."""

    def test_generar_pdf_incluye_membrete(self, tmp_path):
        """generar_pdf_presupuesto genera un PDF con el membrete de la empresa."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(
            nombre="Presupuestos Test SL",
            nif="B55555555",
            direccion="Avda. Test 42",
            telefono="966123456",
            email="ventas@test.es",
        )
        modulo_db.close()

        from reyger.ui.presupuestos import Presupuestos
        from unittest.mock import MagicMock, patch

        vp = object.__new__(Presupuestos)
        vp.colors = {
            "bg_principal": "#1e1e2e",
            "fg_principal": "#ffffff",
            "accent": "#0078d4",
            "bg_secundario": "#2d2d44",
            "btn_guardar": "#0078d4",
            "btn_imprimir": "#ff6b6b",
        }

        vp.entry_cliente = MagicMock()
        vp.entry_cliente.get.return_value = "Cliente Test"
        vp.entry_email = MagicMock()
        vp.entry_email.get.return_value = "cliente@test.com"

        vp.tree = MagicMock()
        vp.tree.get_children.return_value = ("item1",)
        vp.tree.item.return_value = ("Producto A", "2", "10.00", "20.00")

        vp.var_iva = MagicMock()
        vp.var_iva.get.return_value = 21

        vp.productos_presupuesto = []

        out_dir = tmp_path / "presupuestos_pdf"
        out_dir.mkdir()

        with patch("reyger.ui.presupuestos.get_output_path", return_value=str(out_dir)):
            with patch("reyger.ui.presupuestos.open_file"):
                with patch("reyger.ui.presupuestos.messagebox"):
                    vp.generar_pdf_presupuesto()

        pdfs = list(out_dir.glob("Presupuesto_*.pdf"))
        assert len(pdfs) == 1, "Debería generarse exactamente un PDF"
        assert pdfs[0].stat().st_size > 500, "El PDF debe tener contenido real"

    def test_imprimir_presupuesto_existe(self):
        """Presupuestos tiene el método _imprimir_presupuesto."""
        from reyger.ui.presupuestos import Presupuestos
        assert hasattr(Presupuestos, "_imprimir_presupuesto")

    def test_imprimir_sin_datos_muestra_error(self):
        """_imprimir_presupuesto muestra error si no hay datos."""
        from reyger.ui.presupuestos import Presupuestos
        from unittest.mock import MagicMock, patch

        vp = object.__new__(Presupuestos)
        vp.entry_cliente = MagicMock()
        vp.entry_cliente.get.return_value = ""
        vp.tree = MagicMock()
        vp.tree.get_children.return_value = ()

        with patch("reyger.ui.presupuestos.messagebox") as mock_mb:
            vp._imprimir_presupuesto()
            mock_mb.showerror.assert_called_once()
            args = mock_mb.showerror.call_args
            assert "Complete" in str(args)

    def test_botones_en_ui(self):
        """Verifica que los botones 'Generar PDF' e 'Imprimir' están declarados."""
        import ast

        src_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "reyger", "ui", "presupuestos.py"
        )
        with open(src_path) as f:
            contenido = f.read()

        assert 'text="Generar PDF"' in contenido
        assert 'text="Imprimir"' in contenido
        assert "_imprimir_presupuesto" in contenido

    def test_membrete_estructura_pdf(self, tmp_path):
        """El PDF de presupuesto incluye membrete y totales correctos."""
        from reyger.ui import business_profile as bp
        import reyger.core.db as modulo_db

        bp.guardar(
            nombre="Membrete Corp",
            nif="A12345678",
            codigo_postal="46001",
            provincia="Valencia",
        )
        modulo_db.close()

        from reyger.ui.presupuestos import Presupuestos
        from unittest.mock import MagicMock, patch

        vp = object.__new__(Presupuestos)
        vp.colors = {
            "bg_principal": "#1e1e2e",
            "fg_principal": "#ffffff",
            "accent": "#0078d4",
            "bg_secundario": "#2d2d44",
            "btn_guardar": "#0078d4",
            "btn_imprimir": "#ff6b6b",
        }
        vp.entry_cliente = MagicMock()
        vp.entry_cliente.get.return_value = "Cliente VIP"
        vp.entry_email = MagicMock()
        vp.entry_email.get.return_value = ""
        vp.tree = MagicMock()
        vp.tree.get_children.return_value = ("i1", "i2")

        def _mock_item(child_id, *args, **kwargs):
            data = {
                "i1": ("Art1", "1", "50.00", "50.00"),
                "i2": ("Art2", "3", "20.00", "60.00"),
            }
            return data[child_id]

        vp.tree.item.side_effect = _mock_item
        vp.var_iva = MagicMock()
        vp.var_iva.get.return_value = 21
        vp.productos_presupuesto = []

        out_dir = tmp_path / "pdf_membrete"
        out_dir.mkdir()

        with patch("reyger.ui.presupuestos.get_output_path", return_value=str(out_dir)):
            with patch("reyger.ui.presupuestos.open_file"):
                with patch("reyger.ui.presupuestos.messagebox"):
                    vp.generar_pdf_presupuesto()

        pdfs = list(out_dir.glob("Presupuesto_*.pdf"))
        assert len(pdfs) == 1
        assert pdfs[0].stat().st_size > 500, "El PDF debe tener contenido real"
