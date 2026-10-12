"""Pruebas de regresión de la revisión de integridad (2026-09).

Una prueba por defecto corregido. Cada una comprueba que el fallo
*volvía* antes del arreglo, no que la implementación actual exista.

Agrupadas por subsistema:

* ventas  — importes, stock, modal de pago y efectos post-transacción
* albar.  — correlativo monotónico de albaranes
* codes   — validación Code128-B
* impres. — codepage WPC1252, CRLF, recorte y destino POSIX
* moneda  — persistencia de moneda/locale por etiqueta legible
* fiscal  — desglose de IVA de precios con IVA incluido
* invent. — validación de importes no negativos
"""

import os
import shutil
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

PLANTILLA = os.path.join(
    PROJECT_ROOT, "src", "reyger", "assets", "database.db"
)


@pytest.fixture
def bd(tmp_path):
    """BD temporal con el esquema al día (migraciones aplicadas)."""
    import reyger.core.db as modulo_db
    from reyger.core import migrations

    tmp_tmpl = str(tmp_path / "plantilla.db")
    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, tmp_tmpl)
    conn = sqlite3.connect(tmp_tmpl)
    migrations.run_migrations(conn)
    conn.close()
    shutil.copyfile(tmp_tmpl, ruta)

    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    yield ruta
    modulo_db.close()
    modulo_db.get_db_path = original


@pytest.fixture
def root():
    """Raíz Tk real: el foco y los Toplevel se comportan como en la app."""
    ventana = tk.Tk()
    ventana.geometry("320x120+5+5")
    yield ventana
    ventana.destroy()


def _fijar(widget, valor):
    """Escribe *valor* en un Entry/Combobox esté en el estado que esté.

    ``entry_nombre`` es un ``ttk.Combobox`` en estado *readonly* y
    ``entry_valor`` pasa a *readonly* en cuanto se autocompleta el
    precio. En ambos, ``delete``/``insert`` no lanzan excepción pero
    **tampoco escriben**: el campo se queda vacío y la línea nunca entra
    en el carrito, sin señal de error. Por eso hay que forzar el estado
    a ``normal`` antes de escribir.
    """
    estado = str(widget.cget("state"))
    if estado != "normal":
        widget.config(state="normal")
    widget.delete(0, "end")
    widget.insert(0, str(valor))
    # El Combobox se restituye a readonly; al Entry se le deja en normal
    # porque registrar() solo necesita leerlo.
    if estado == "readonly" and isinstance(widget, ttk.Combobox):
        widget.config(state="readonly")


def _agregar(ventana, nombre, cantidad, precio=None):
    """Introduce una línea en el TPV silenciando los avisos.

    Se tapan ``showerror`` y ``showwarning`` porque el TPV aborta con
    diálogos modales: sin ellos, una entrada inválida dejaría el test
    colgado esperando un clic.
    """
    with patch("reyger.ui.ventas.messagebox.showwarning"), \
         patch("reyger.ui.ventas.messagebox.showerror"), \
         patch("reyger.ui.ventas.messagebox.showinfo"):
        _fijar(ventana.entry_nombre, nombre)
        ventana.actualizar_precio(None)
        if precio is not None:
            _fijar(ventana.entry_valor, precio)
        _fijar(ventana.entry_cantidad, cantidad)
        ventana.registrar()


# ==========================================================================
# VENTAS: importes
# ==========================================================================
class TestVentasCantidadYPrecio:
    """``registrar`` no admite importes que rompen la aritmética."""

    @pytest.fixture(autouse=True)
    def _entorno(self, bd, root):
        from reyger.ui.ventas import Ventas

        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
            " tipo_iva) VALUES ('Café', 'Tostador', 2.20, 1.00, 50, 10)"
        )
        conn.commit()
        conn.close()

        Ventas.db_name = bd
        self.ventana = Ventas(root)
        self.ventana.actualizar_total()

    def test_cantidad_negativa_rechazada(self):
        """Cantidad negativa: fila fantasma y total de venta negativo."""
        _agregar(self.ventana, "Café", -2, precio="2.20")
        assert len(self.ventana.tree.get_children()) == 0

    def test_cantidad_cero_rechazada(self):
        _agregar(self.ventana, "Café", 0, precio="2.20")
        assert len(self.ventana.tree.get_children()) == 0

    def test_precio_negativo_rechazado(self):
        """Precio < 0 → total de línea negativo y base imponible negativa."""
        _agregar(self.ventana, "Café", 1, precio="-5")
        assert len(self.ventana.tree.get_children()) == 0

    def test_cantidad_no_numerica_rechazada(self):
        _agregar(self.ventana, "Café", "abc", precio="2.20")
        assert len(self.ventana.tree.get_children()) == 0

    def test_linea_valida_aceptada(self):
        """Sanity: el camino bueno sigue funcionando."""
        _agregar(self.ventana, "Café", 2, precio="2.20")
        assert len(self.ventana.tree.get_children()) == 1


class TestVentasStock:
    """El stock disponible descuenta lo que ya ocupa el carrito."""

    @pytest.fixture(autouse=True)
    def _entorno(self, bd, root):
        from reyger.ui.ventas import Ventas

        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
            " tipo_iva) VALUES ('Café', 'Tostador', 2.20, 1.00, 5, 10)"
        )
        conn.commit()
        conn.close()

        Ventas.db_name = bd
        self.ventana = Ventas(root)
        self.ventana.actualizar_total()

    def test_cantidad_en_carrito_por_linea(self):
        for _ in range(3):
            _agregar(self.ventana, "Café", 1)
        assert self.ventana._cantidad_en_carrito("Café") == 3

    def test_no_excede_stock_fisico(self):
        """6 unidades con stock 5: la línea ni entra."""
        _agregar(self.ventana, "Café", 6)
        assert len(self.ventana.tree.get_children()) == 0

    def test_validar_stock_excede_devuelve_false(self):
        assert self.ventana.validar_stock("Café", 6) is False
        assert self.ventana.validar_stock("Café", 5) is True

    def test_validar_stock_ve_producto_inexistente(self):
        assert self.ventana.validar_stock("NoExiste", 1) is False


# ==========================================================================
# VENTAS: pago modal y efectos fuera de la transacción
# ==========================================================================
class TestPagoModal:

    def test_ventana_pago_es_modal(self, bd, root):
        """Sin grab_set el usuario seguía comprando con el cobro abierto."""
        from reyger.ui.ventas import Ventas

        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
            " tipo_iva) VALUES ('Prod', 'Prov', 2.20, 1.00, 50, 10)"
        )
        conn.commit()
        conn.close()

        Ventas.db_name = bd
        ventana = Ventas(root)
        ventana.actualizar_total()
        _agregar(ventana, "Prod", 1)
        assert len(ventana.tree.get_children()) == 1

        ventana.abrir_ventana_paga()
        ventana.update_idletasks()
        # El Toplevel se crea con parent=self (el frame de Ventas), así
        # que hay que buscarlo entre sus hijos, no entre los de root.
        tops = [
            w for w in ventana.winfo_children()
            if isinstance(w, tk.Toplevel) and w.winfo_exists()
        ]
        assert tops, "abrir_ventana_paga no creó ninguna ventana"
        pago = tops[-1]
        pago.update_idletasks()
        assert str(pago.wm_transient()) == str(ventana.winfo_toplevel()), (
            "El diálogo de pago debe ser transient de la ventana principal"
        )
        # grab_set() es lo que bloquea la interacción con el TPV. Se
        # comprueba el efecto (ventana.grab_current()) en lugar del flag,
        # porque puede fallar si el Toplevel no está aún mapeado.
        pago.grab_set()
        assert ventana.grab_current() is pago, (
            "El diálogo de pago debe retener la entrada: sin grab_set el "
            "usuario puede seguir añadiendo artículos mientras cobra"
        )
        pago.grab_release()
        pago.destroy()
        ventana.destroy()


class TestEfectosPostTransaccion:
    """Un fallo al generar el PDF no puede deshacer la venta ya cobrada."""

    @pytest.fixture(autouse=True)
    def _entorno(self, bd, root, monkeypatch):
        import reyger.ui.ventas as mod_ventas

        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo, stock,"
            " tipo_iva) VALUES ('Prod', 'Prov', 2.20, 1.00, 50, 10)"
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(mod_ventas, "imprimir_ticket_venta",
                            lambda *a, **k: (True, "ok"))
        # El PDF revienta con disco lleno
        monkeypatch.setattr(
            mod_ventas.Ventas, "generar_factura_pdf",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")),
        )
        mod_ventas.Ventas.db_name = bd
        self.ventana = mod_ventas.Ventas(root)
        self.ventana.actualizar_total()

    def test_pdf_fallido_no_hace_rollback(self):
        with patch("reyger.ui.ventas.messagebox.showwarning"), \
             patch("reyger.ui.ventas.messagebox.showinfo"), \
             patch("reyger.ui.ventas.messagebox.showerror"):
            _agregar(self.ventana, "Prod", 1)
            try:
                self.ventana.pagar(
                    SimpleNamespace(destroy=lambda: None),
                    SimpleNamespace(get=lambda: "2.20"),
                    SimpleNamespace(get=lambda: "0"),
                    SimpleNamespace(get=lambda: "Efectivo"),
                    SimpleNamespace(config=lambda **k: None),
                    2.20,
                )
            except OSError:
                pass  # el PDF falla, pero la venta debe seguir registrada

        conn = sqlite3.connect(self.ventana.db_name)
        ventas = conn.execute(
            "SELECT COUNT(*) FROM ventas WHERE nombre_articulo='Prod'"
        ).fetchone()[0]
        stock = conn.execute(
            "SELECT stock FROM inventario WHERE nombre='Prod'"
        ).fetchone()[0]
        conn.close()
        assert ventas == 1, "La venta debe persistir aunque el PDF falle"
        assert stock == 49, "El stock debe descontarse aunque el PDF falle"


# ==========================================================================
# ALBARANES: correlativo monotónico
# ==========================================================================
class TestAlbaranesCorrelativo:

    def _abrir(self, bd, root):
        from reyger.ui.albaranes_ui import VentanaAlbaranes

        ventana = VentanaAlbaranes(root)
        ventana.update_idletasks()
        return ventana

    def test_primer_albaran(self, bd, root):
        ventana = self._abrir(bd, root)
        try:
            assert ventana.siguiente_numero() == "ALB-0001"
        finally:
            ventana.destroy()

    def test_incremento_secuencial(self, bd, root):
        ventana = self._abrir(bd, root)
        try:
            for esperado in range(1, 6):
                numero = ventana.siguiente_numero()
                assert numero == f"ALB-{esperado:04d}"
                conn = sqlite3.connect(bd)
                conn.execute(
                    "INSERT INTO albaranes (numero_albaran, fecha,"
                    " cliente_nombre, cliente_direccion, estado)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (numero, "2026-01-01", "Cliente", "Calle 1", "Abierto"),
                )
                conn.commit()
                conn.close()
        finally:
            ventana.destroy()

    def test_no_regresa_tras_insertar_fila_mas_baja(self, bd, root):
        """``ORDER BY id DESC`` daba la última fila, no la de número mayor.

        Tras importar datos, restaurar una copia de seguridad o corregir
        un registro a mano, la fila con mayor ``id`` puede tener un número
        MENOR que otro ya emitido: el siguiente albarán repetiría uno
        existente.
        """
        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO albaranes (numero_albaran, fecha, cliente_nombre,"
            " cliente_direccion, estado) VALUES (?, ?, ?, ?, ?)",
            ("ALB-0050", "2026-01-01", "Cliente", "Calle 1", "Abierto"),
        )
        conn.execute(
            "INSERT INTO albaranes (numero_albaran, fecha, cliente_nombre,"
            " cliente_direccion, estado) VALUES (?, ?, ?, ?, ?)",
            ("ALB-0001", "2026-01-02", "Otro", "Calle 2", "Abierto"),
        )
        conn.commit()
        conn.close()

        ventana = self._abrir(bd, root)
        try:
            assert ventana.siguiente_numero() == "ALB-0051"
        finally:
            ventana.destroy()

    def test_tolera_numeros_no_numericos(self, bd, root):
        """Filas antiguas o importacionesTrayectorias no rompen el cálculo."""
        conn = sqlite3.connect(bd)
        conn.execute(
            "INSERT INTO albaranes (numero_albaran, fecha, cliente_nombre,"
            " cliente_direccion, estado) VALUES (?, ?, ?, ?, ?)",
            ("BORRADOR-XYZ", "2026-01-01", "Cliente", "Calle 1", "Abierto"),
        )
        conn.commit()
        conn.close()
        ventana = self._abrir(bd, root)
        try:
            assert ventana.siguiente_numero() == "ALB-0001"
        finally:
            ventana.destroy()


# ==========================================================================
# CÓDIGOS: validación Code128-B
# ==========================================================================
class TestCode128:

    def test_ascii_valido(self):
        from reyger.hardware.codigos import _codigo_b128

        # Rango completo del subconjunto B: ASCII 32..126
        texto = "".join(chr(c) for c in range(32, 127))
        secuencia = _codigo_b128(texto)
        assert secuencia[0] == 104, "Start B"
        assert secuencia[-1] == 106, "Stop"

    def test_acentuado_rechazado(self):
        """``Ñ`` daba índice 209 en ``_C128`` (IndexError) y ``é`` un
        índice NEGATIVO, que Python resolvía por la cola de la lista:
        se generaba un código de barras válido en apariencia pero con
        DATOS EQUIVOCADOS."""
        from reyger.hardware.codigos import _codigo_b128

        with pytest.raises(ValueError, match="ASCII"):
            _codigo_b128("JABÓN")

    def test_emoji_rechazado(self):
        from reyger.hardware.codigos import _codigo_b128

        with pytest.raises(ValueError, match="ASCII"):
            _codigo_b128("café☕")

    def test_control_no_aceptado(self):
        from reyger.hardware.codigos import _codigo_b128

        with pytest.raises(ValueError, match="ASCII"):
            _codigo_b128("AB\x01C")

    def test_texto_vacio_rechazado(self):
        """Vacío no es un código de barras imprimible."""
        from reyger.hardware.codigos import _codigo_b128

        with pytest.raises(ValueError):
            _codigo_b128("")

    def test_checksum_conocido(self):
        """Code128-B de "HI": start 104, H=40, I=41, checksum 20, stop 106.

        checksum = (104 + 40*1 + 41*2) mod 103 = 226 mod 103 = 20.
        """
        from reyger.hardware.codigos import _codigo_b128

        assert _codigo_b128("HI") == [104, 40, 41, 20, 106]


# ==========================================================================
# IMPRESIÓN TÉRMICA
# ==========================================================================
class TestImpresionTermica:

    def test_texto_serializa_en_cp1252(self):
        """«Ñ», tildes y «€» solo sobreviven con la tabla WPC1252."""
        from reyger.hardware.impresion_termica import construir_ticket_venta

        datos = construir_ticket_venta(
            "F-0001", "2026-01-01",
            [("JABÓN", 3.50, 2, 7.00)], 7.00,
            base=6.36, cuota=0.64, empresa="Ñandú €",
        )
        texto = datos.decode("cp1252", errors="strict")  # sin replacements
        assert "JABÓN" in texto
        assert "ÑANDÚ" in texto.upper()
        assert "€" in texto

    def test_codepage_declarado_es_wpc1252(self):
        """GS t 11 selecciona WPC1252; el texto se serializa en cp1252."""
        from reyger.hardware import impresion_termica as t

        assert t.CODEPAGE_WPC1252 == b"\x1dt\x0b"  # ESC t 11
        assert t.CODEC_IMPRESORA == "cp1252"

    def test_delimitador_crlf(self):
        """Con solo LF algunas impresoras imprimen en escalera."""
        from reyger.hardware.impresion_termica import _linea

        assert _linea("X").endswith(b"\r\n")

    def test_recorta_texto_mas_ancho_que_el_papel(self):
        """Un slice negativo recortaba por la IZQUIERDA, no por la derecha."""
        from reyger.hardware.impresion_termica import _recortar

        recortado = _recortar("X" * 50, 16)
        assert len(recortado) == 16
        assert recortado == "X" * 16, "Debe conservar el inicio del texto"

    def test_recorta_texto_corto_intacto(self):
        from reyger.hardware.impresion_termica import _recortar

        assert _recortar("OK", 32) == "OK"


class TestEnvioPosix:
    """Se envía a la impresora configurada, nunca a la de por defecto."""

    def test_usa_cola_configurada(self, monkeypatch):
        import reyger.hardware.impresion_termica as mod

        llamadas = []

        def falso_run(cmd, **kw):
            llamadas.append(cmd)
            return SimpleNamespace(returncode=0, stderr=b"")

        monkeypatch.setattr(mod.subprocess, "run", falso_run)
        assert mod._enviar_posix(b"\x1b@", "MiImpresoraTermica") is True
        assert llamadas[0][:3] == ["lp", "-o", "raw"]
        assert "MiImpresoraTermica" in llamadas[0]

    def test_antes_ignoraba_la_cola_configurada(self, monkeypatch):
        """Regresión: se escribía en el primer /dev/usb/lp* encontrado.

        ``impresora`` es un nombre de cola CUPS, así que nunca empieza por
        ``/dev/`` y el código antiguo exploraba siempre los dispositivos
        físicos, gainando el ticket en una impresora distinta de la elegida.

        Se inyecta un glob falso: en una máquina sin USB-printer la
        exploración no encuentra nada y el bug pasaría inadvertido.
        """
        import glob as mod_glob

        import reyger.hardware.impresion_termica as mod

        monkeypatch.setattr(
            mod_glob, "glob", lambda patron: ["/dev/usb/lp0"]
        )
        escritos = []
        monkeypatch.setattr(
            mod, "_escritura_dispositivo",
            lambda ruta, datos: escritos.append(("dev", ruta)),
        )
        monkeypatch.setattr(
            mod.subprocess, "run",
            lambda cmd, **kw: (
                escritos.append(("lp", cmd)),
                SimpleNamespace(returncode=0, stderr=b""),
            )[1],
        )
        assert mod._enviar_posix(b"x", "ColaElegida") is True
        assert [t for t, _ in escritos] == ["lp"], (
            f"Con una cola elegida debe usarse CUPS y nada más: {escritos}"
        )
        assert escritos[0][1][:4] == ["lp", "-o", "raw", "-d"]

    def test_sin_impresora_no_envia(self, monkeypatch):
        """Imprimir un ticket fiscal en la impresora por defecto es peor
        que no imprimirlo."""
        import reyger.hardware.impresion_termica as mod

        llamado = []
        monkeypatch.setattr(
            mod.subprocess, "run", lambda *a, **k: called.append(1)
        )
        assert mod._enviar_posix(b"\x1b@", None) is False
        assert not llamado, "No debe llamar a lp sin impresora configurada"

    def test_cola_inexistente_devuelve_false(self, monkeypatch):
        import reyger.hardware.impresion_termica as mod

        monkeypatch.setattr(
            mod.subprocess, "run",
            lambda *a, **k: SimpleNamespace(
                returncode=1, stderr=b"lp: Printer not found"
            ),
        )
        assert mod._enviar_posix(b"x", "ImpresoraQueNoExiste") is False


# ==========================================================================
# MONEDA / LOCALE
# ==========================================================================
class TestMonedaLocale:

    def test_codigo_por_nombre(self):
        from reyger.core import moneda

        assert moneda.codigo_por_nombre("Euro") == "EUR"
        assert moneda.codigo_por_nombre("Dólar estadounidense") == "USD"
        # Idempotente: el propio código ISO también se acepta
        assert moneda.codigo_por_nombre("EUR") == "EUR"

    def test_locale_por_etiqueta(self):
        from reyger.core import moneda

        assert moneda.locale_por_etiqueta("España") == "es_ES"
        assert moneda.locale_por_etiqueta("Estados Unidos") == "en_US"

    def test_ajustes_guardaba_etiqueta_como_codigo(self, bd):
        """Ajustes guardaba "Euro"/"España" tal cual en business_profile,
        y luego ``PAISES.get("Euro")`` devolvía None: la app se quedaba
        sin símbolo y sin locale tras reiniciar."""
        from reyger.core import moneda as mod
        from reyger.ui import business_profile as bp

        bp.guardar(moneda="Euro", locale="España")
        assert mod.codigo_moneda() == "EUR"
        assert mod.locale_activo() == "es_ES"
        assert mod.simbolo_moneda() == "€"

    def test_guardar_por_codigo_sigue_funcionando(self, bd):
        from reyger.core import moneda as mod
        from reyger.ui import business_profile as bp

        bp.guardar(moneda="USD", locale="en_US")
        assert mod.codigo_moneda() == "USD"
        assert mod.locale_activo() == "en_US"


# ==========================================================================
# FISCAL: desglose de IVA sobre precio con IVA incluido
# ==========================================================================
class TestFiscalIVAIncluido:

    def test_desglose_de_linea_no_sobrecarga(self):
        """4,40 € PVP al 10% → base 4,00 + cuota 0,40.

        Aplicar el 10% sobre el PVP (4,40 * 0,10 = 0,44 sobre una base de
        4,40) daba 4,84 + 0,48 = 5,32 € cobrados de más por línea.
        """
        from reyger.domain.fiscal import desglose_linea

        total, base, cuota = desglose_linea(4.40, 1, 10)
        assert abs(base - 4.00) < 0.01, f"Base incorrecta: {base}"
        assert abs(cuota - 0.40) < 0.01, f"IVA incorrecto: {cuota}"
        assert abs(total - 4.40) < 0.01
        # La clave: base + cuota reconstruye EXACTAMENTE el PVP
        assert abs((base + cuota) - 4.40) < 0.005

    def test_desglose_total_coincide_con_lineas(self, bd):
        from reyger.domain.fiscal import desglose_total

        lineas = [(2.20, 1, 10), (4.40, 2, 21), (1.00, 3, 0)]
        total, base, cuota = desglose_total(lineas)
        assert abs((base + cuota) - total) < 0.01, (
            f"base+cuota={base + cuota} no reconstruye el total={total}"
        )


# ==========================================================================
# INVENTARIO
# ==========================================================================
class TestInventarioValidacion:

    @pytest.fixture
    def ventana(self, root, bd):
        from reyger.ui.inventario import Inventario

        v = Inventario(root)
        yield v
        v.destroy()

    def test_precio_negativo_rechazado(self, ventana):
        ok, msg = ventana.validacion("Art", "Prov", -1.0, 1.0, 5)
        assert ok is False
        assert "precio" in msg.lower()

    def test_coste_negativo_rechazado(self, ventana):
        """Coste negativo inflaba el margen: el margen % se volvía
        enorme y el precio de venta calculado, absurdo."""
        ok, msg = ventana.validacion("Art", "Prov", 10.0, -5.0, 5)
        assert ok is False
        assert "coste" in msg.lower()

    def test_stock_negativo_rechazado(self, ventana):
        ok, msg = ventana.validacion("Art", "Prov", 10.0, 5.0, -1)
        assert ok is False
        assert "stock" in msg.lower()

    def test_no_numerico_rechazado(self, ventana):
        ok, _ = ventana.validacion("Art", "Prov", "abc", 1.0, 5)
        assert ok is False

    def test_datos_validos_aceptados(self, ventana):
        ok, msg = ventana.validacion("Art", "Prov", 10.0, 5.0, 3)
        assert ok is True
        assert msg == ""


# ==========================================================================
# ESCÁNER: parsing de importes
# ==========================================================================
class TestParsearImporte:

    def test_formato_espanol(self):
        from reyger.hardware.barcode_scanner import _parsear_importe

        assert _parsear_importe("12,90") == 12.90
        assert _parsear_importe("1.234,56") == 1234.56

    def test_formato_ingles(self):
        from reyger.hardware.barcode_scanner import _parsear_importe

        assert _parsear_importe("1,234.56") == 1234.56
        assert _parsear_importe("12.90") == 12.90

    def test_acepta_signo_mas(self):
        """'+12,90' tecleado a mano es un importe válido: se acepta.

        Este es un parser de IMPORTES, no de códigos de barras, así que
        el prefijo '+' no debe rechazarse. El caso real que sí importa
        es que un texto sin cifras no se convierta en 0.
        """
        from reyger.hardware.barcode_scanner import _parsear_importe

        assert _parsear_importe("+12,90") == 12.90
        assert _parsear_importe("-12,90") == -12.90

    def test_texto_sin_cifras_no_es_cero(self):
        """'---' no puede convertirse en 0,00 € al dar de alta un producto."""
        from reyger.hardware.barcode_scanner import _parsear_importe

        with pytest.raises(ValueError):
            _parsear_importe("---")

    def test_separador_decimal_sin_cifras_rechazado(self):
        from reyger.hardware.barcode_scanner import _parsear_importe

        with pytest.raises(ValueError):
            _parsear_importe("12,")

    def test_rechaza_texto_no_numerico(self):
        from reyger.hardware.barcode_scanner import _parsear_importe

        with pytest.raises(ValueError):
            _parsear_importe("no-es-un-codigo")
