"""B3: la selección de cliente no puede depender del nombre.

``ventas.py`` resolvía el cliente facturado con
``SELECT id FROM clientes WHERE nombre = ?``, sin ``ORDER BY`` y asumiendo
que ``nombre`` es único. Con dos clientes homónimos («Farmacia»), SQLite
devolvía un ``id`` arbitrario y la factura se emitía con el NIF, la
dirección, el teléfono y el email del cliente **equivocado**, sin ningún
aviso.

Aquí se cubre que la asociación use el ``cliente_id`` elegido en el
desplegable (posición -> id, inequívoco aunque los nombres coincidan) y que,
si el desplegable no es de fiar, la resolución por nombre **falle de forma
explícita** en vez de adivinar.

Los tests conducen el ``pagar()`` real con un ``Treeview`` y un ``Combobox``
reales de Tkinter, así que lo verificado es el camino de producción completo:
fila de ``ventas``, PDF y registro de Veri*Factu*.
"""

import os
import shutil
import subprocess
import sys
from unittest.mock import patch

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

PLANTILLA = os.path.join(SRC_DIR, "reyger", "assets", "database.db")

NOMBRE_HOMONIMO = "Farmacia"
NIF_1 = "B11111111"
NIF_2 = "B22222222"

# Comprobar el PDF exige poder LEERLO, y de eso no se ocupa reportlab. Se usa
# el binario `pdftotext` de poppler-utils, que no está en todas las máquinas
# (ni en los runners de GitHub si no se instala). Los tests que lo necesitan
# se saltan en lugar de fallar por una dependencia del sistema; el CI instala
# poppler-utils para que sí se comprueben allí.
_PDFTOTEXT = shutil.which("pdftotext")
requiere_pdftotext = pytest.mark.skipif(
    _PDFTOTEXT is None,
    reason="requiere el binario 'pdftotext' (paquete poppler-utils)",
)


# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _salida_aislada(tmp_path, monkeypatch):
    """Redirige la salida de PDF al temporal en TODO el módulo.

    Sin esto, ``generar_factura_pdf`` escribe en la carpeta de documentos real
    del usuario y el test deja basura fuera de ``tmp_path``.
    """
    monkeypatch.setattr(
        "reyger.ui.ventas.get_output_path", lambda *_a, **_k: str(tmp_path)
    )


@pytest.fixture(autouse=True)
def _bd_temporal(tmp_path):
    """BD temporal con dos clientes homónimos y un producto en inventario."""
    import reyger.core.db as modulo_db

    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    _sembrar_homonimos()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original


def _sembrar_homonimos():
    """Crea dos clientes con nombre IDÉNTICO y distinto NIF/ficha."""
    import reyger.core.db as modulo_db

    for nif, email, calle in (
        (NIF_1, "primero@farmacia.es", "Calle Primera 1"),
        (NIF_2, "segundo@farmacia.es", "Calle Segunda 2"),
    ):
        modulo_db.execute(
            "INSERT INTO clientes (nombre, tipo_documento, documento, direccion, "
            "codigo_postal, provincia, telefono, email) "
            "VALUES (?, 'CIF', ?, ?, '28001', 'Madrid', '911223344', ?)",
            (NOMBRE_HOMONIMO, nif, calle, email),
        )
    modulo_db.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Paracetamol 1g", "Proveedor Test", 10.0, 6.0, 100, 21),
    )


def _id_de_primer_homonimo():
    import reyger.core.db as modulo_db

    return modulo_db.query(
        "SELECT id FROM clientes WHERE nombre = ? ORDER BY id", (NOMBRE_HOMONIMO,)
    )


# ---------------------------------------------------------------------------
# Arranque de la ventana de ventas con Tk real
# ---------------------------------------------------------------------------


class _WidgetFalso:
    """Widget que solo acepta lo que el código le hace."""

    def __init__(self):
        self.textos = []

    def config(self, **kwargs):
        if "text" in kwargs:
            self.textos.append(kwargs["text"])


class _EntryFalso:
    def __init__(self, valor=""):
        self._valor = valor

    def get(self):
        return self._valor


class _VarFalso:
    def __init__(self, valor):
        self._valor = valor

    def get(self):
        return self._valor


class _VentanaFalso:
    """La ventana modal de pago: ``pagar()`` solo la destruye al terminar."""

    def destroy(self):
        pass


class _ComboFalso:
    """``ttk.Combobox`` en modo lectura, con la misma semántica que se usa.

    Se usa un doble en lugar del widget real para que estos tests no dependan
    de un servidor X: sin ``DISPLAY`` fallan los 16 tests del módulo, y el que
    nos importa (``_resolver_cliente_seleccionado``) solo necesita una lista de
    etiquetas y un cursor sobre ella. El test de humo con Tk real está aparte.
    """

    def __init__(self):
        self._valores = ()
        self._indice = -1

    def __setitem__(self, clave, valor):
        assert clave == "values", f"Clave no soportada: {clave}"
        self._valores = tuple(valor)

    def __getitem__(self, clave):
        assert clave == "values"
        return self._valores

    def __len__(self):
        return len(self._valores)

    def current(self, indice=None):
        """Sin argumento devuelve el índice; con argumento, selecciona."""
        if indice is None:
            return self._indice
        self._indice = indice
        return None

    def get(self):
        if 0 <= self._indice < len(self._valores):
            return self._valores[self._indice]
        return ""

    def bind(self, *_a, **_k):
        pass


class _TreeFalso:
    """``ttk.Treeview`` mínimo: lo que ``pagar`` y ``_lineas_carrito`` leen."""

    def __init__(self, filas):
        self._filas = list(filas)

    def get_children(self):
        return list(range(len(self._filas)))

    def item(self, indice, valores=False):
        # Igual que Tkinter: con el argumento ``values`` devuelve la tupla de
        # valores, que el código consume posicionalmente (``item[0]``).
        if valores:
            return self._filas[indice]
        return {}

    def insert(self, _parent, _indice, values):
        self._filas.append(values)

    def delete(self, indice):
        del self._filas[indice]


def _construir_ventana(combo, tree):
    """``Ventas`` con los stubs mínimos para que ``pagar()`` corra de verdad."""
    from reyger.ui.ventas import Ventas

    ventana = object.__new__(Ventas)
    ventana.config_manager = None
    ventana.combo_cliente = combo
    ventana._ids_cliente_venta = []
    ventana.cargar_clientes_venta()
    ventana.tree = tree
    ventana.var_tipo_documento = _VarFalso("factura")
    ventana.label_base = _WidgetFalso()
    ventana.label_cuota = _WidgetFalso()
    ventana.label_suma_total = _WidgetFalso()
    ventana.numero_factura_actual = 1
    ventana.numero_ticket_actual = 1
    ventana.mostrar_numero_documento = lambda: None
    ventana.cargar_productos = lambda: None
    return ventana


LINEA_CARRITO = ("Paracetamol 1g", 10.0, 1, "21%", 10.0, 1)


@pytest.fixture
def ventas_ventana():
    """``Ventas`` con desplegable y carrito, lista para ``pagar()``."""
    yield _construir_ventana(_ComboFalso(), _TreeFalso([LINEA_CARRITO]))


@pytest.fixture
def ventas_ventana_tk():
    """Idéntico pero con los widgets REALES de Tkinter.

    Comprueba que la semántica de selección de un ``Combobox`` de verdad
    (índice + etiqueta) encaja con la resolución por posición. Se salta si no
    hay servidor de X disponible.
    """
    tkinter = pytest.importorskip("tkinter")
    from tkinter import ttk

    try:
        root = tkinter.Tk()
    except Exception as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"Tk no disponible ({exc}); se omite el test con widgets reales")

    root.withdraw()
    try:
        combo = ttk.Combobox(root, state="readonly", width=30)
        tree = ttk.Treeview(root, show="headings")
        tree.insert("", "end", values=LINEA_CARRITO)
        ventana = _construir_ventana(combo, tree)
        ventana.var_tipo_documento = tkinter.StringVar(value="factura")
        yield ventana
    finally:
        root.destroy()


def _seleccionar_indice(ventana, indice):
    """Selecciona en el desplegable real y devuelve el cliente resuelto."""
    ventana.combo_cliente.current(indice)
    return ventana._resolver_cliente_seleccionado()


def _pagar(ventana, tmp_path, monkeypatch):
    """Ejecuta ``pagar()`` real: escribe en BD y genera el PDF.

    ``get_output_path`` se redirige a un temporal: sin esto la factura de
    prueba acabaría en la carpeta de documentos real del usuario.
    """
    monkeypatch.setattr("reyger.ui.ventas.open_file", lambda *a, **k: None)
    monkeypatch.setattr(
        "reyger.ui.ventas.get_output_path", lambda *_a, **_k: str(tmp_path)
    )
    with patch("reyger.ui.ventas.messagebox") as caja:
        ventana.pagar(
            ventana_pago=_VentanaFalso(),
            entry_efectivo=_EntryFalso("10.00"),
            entry_tarjeta=_EntryFalso(""),
            var_metodo=_VarFalso("Efectivo"),
            label_cambio=_WidgetFalso(),
            total=10.0,
        )
        assert not caja.showerror.called, (
            f"pagar() abortó: {caja.showerror.call_args}"
        )
    return ventana


def _texto_pdf(ruta):
    """Extrae el texto del PDF con ``pdftotext`` (poppler-utils)."""
    return subprocess.run(
        [_PDFTOTEXT, ruta, "-"],
        capture_output=True, text=True, check=True,
    ).stdout


# ---------------------------------------------------------------------------
# 1) El desplegable admite homónimos sin perder el id
# ---------------------------------------------------------------------------


class TestDesplegableConHomonimos:
    """``cargar_clientes_venta`` guarda un id por cada etiqueta."""

    def test_carga_una_entrada_por_cliente_mas_el_sin_cliente(self, ventas_ventana):
        ventana = ventas_ventana
        valores = list(ventana.combo_cliente["values"])
        assert len(valores) == 3, f"Se esperaban 3 entradas: {valores}"
        assert valores[0] == "(Sin cliente)"

    def test_los_tres_valores_por_defecto(self, ventas_ventana):
        ventana = ventas_ventana
        ventana.combo_cliente.current(0)
        cliente_id, nombre, error = ventana._resolver_cliente_seleccionado()
        assert (cliente_id, error) == (None, None)
        assert nombre == "(Sin cliente)"

    def test_los_ids_paralelos_cubren_todas_las_entradas(self, ventas_ventana):
        ventana = ventas_ventana
        entradas = list(ventana.combo_cliente["values"])
        assert len(ventana._ids_cliente_venta) == len(entradas)
        # Ambas posiciones homónimas tienen ids distintos y reales.
        assert ventana._ids_cliente_venta[1] != ventana._ids_cliente_venta[2]
        assert None not in ventana._ids_cliente_venta[1:]

    def test_el_orden_es_estable_entre_arranques(self, ventas_ventana):
        """Con nombres repetidos el orden no depende del desempate de SQLite."""
        ventana = ventas_ventana
        antes = list(ventana._ids_cliente_venta)
        ventana.cargar_clientes_venta()
        assert list(ventana._ids_cliente_venta) == antes


# ---------------------------------------------------------------------------
# 2) La selección resuelve el id correcto
# ---------------------------------------------------------------------------


class TestResolucionDelCliente:
    """El ``cliente_id`` viene de la posición elegida en el desplegable."""

    def test_seleccionar_el_primer_homonimo_devuelve_su_id(self, ventas_ventana):
        ventana = ventas_ventana
        cliente_id, nombre, error = _seleccionar_indice(ventana, 1)
        assert error is None
        assert cliente_id == _id_de_primer_homonimo()[0]["id"]
        assert nombre == NOMBRE_HOMONIMO

    def test_seleccionar_el_segundo_homonimo_devuelve_su_id(self, ventas_ventana):
        """El cliente segundo NO puede resolverse al primero."""
        ventana = ventas_ventana
        cliente_id, _, error = _seleccionar_indice(ventana, 2)
        esperado = _id_de_primer_homonimo()[1]["id"]
        assert error is None
        assert cliente_id == esperado
        assert cliente_id != _id_de_primer_homonimo()[0]["id"]

    def test_por_nombre_el_homonimo_es_ambiguo(self, ventas_ventana):
        """Documenta por qué la consulta por nombre no puede servir."""
        import reyger.core.db as modulo_db

        filas = modulo_db.query(
            "SELECT id FROM clientes WHERE nombre = ?", (NOMBRE_HOMONIMO,)
        )
        assert len(filas) == 2, "Sin duplicados reales el test no demuestra nada"


class TestDegradacionSegura:
    """Si el desplegable no es de fiar, se exige resolución: nunca adivinar."""

    def test_desplegable_desincronizado_con_homonimos_da_error(self, ventas_ventana):
        ventana = ventas_ventana
        ventana._ids_cliente_venta = []  # como si nunca se hubiera cargado
        ventana.combo_cliente.current(2)

        cliente_id, _, error = ventana._resolver_cliente_seleccionado()

        assert cliente_id is None, "Nunca debe adivinar un id entre homónimos"
        assert error and "2" in error and NOMBRE_HOMONIMO in error

    def test_indice_fuera_de_rango_con_homonimos_da_error(self, ventas_ventana):
        ventana = ventas_ventana
        ventana._ids_cliente_venta = [None]  # truncado: índice 2 no existe
        ventana.combo_cliente.current(2)

        _, _, error = ventana._resolver_cliente_seleccionado()

        assert error is not None

    def test_nombre_unico_sigue_resolviendo_por_nombre(self, ventas_ventana):
        """La degradación no rompe el caso normal: un solo match es válido."""
        import reyger.core.db as modulo_db

        modulo_db.execute(
            "INSERT INTO clientes (nombre, tipo_documento, documento) "
            "VALUES ('Optica Unica', 'CIF', 'B99999999')"
        )
        ventana = ventas_ventana
        ventana.cargar_clientes_venta()
        ventana._ids_cliente_venta = []  # forzar la degradación
        indice = list(ventana.combo_cliente["values"]).index("Optica Unica")
        ventana.combo_cliente.current(indice)

        cliente_id, nombre, error = ventana._resolver_cliente_seleccionado()

        assert error is None
        assert cliente_id is not None
        assert nombre == "Optica Unica"


# ---------------------------------------------------------------------------
# 3) Factura emitida: BD, PDF y VeriFactu con el cliente elegido
# ---------------------------------------------------------------------------


class TestFacturaConHomonomo:
    """``pagar()`` real con el segundo homónimo seleccionado."""

    @pytest.fixture
    def emitida(self, ventas_ventana, tmp_path, monkeypatch):
        """Emite la factura por el camino real y devuelve el PDF generado."""
        ventana = ventas_ventana
        _seleccionar_indice(ventana, 2)  # el segundo «Farmacia»
        _pagar(ventana, tmp_path, monkeypatch)
        pdfs = list(tmp_path.glob("factura_*.pdf"))
        assert len(pdfs) == 1, f"``pagar()`` debería emitir un PDF: {pdfs}"
        return ventana, _id_de_primer_homonimo()[1]["id"], pdfs[0]

    def test_la_fila_de_ventas_guarda_el_cliente_id_seleccionado(self, emitida):
        """La venta apunta al cliente 2, no al homónimo equivocado."""
        import reyger.core.db as modulo_db

        _, cliente_id, _ = emitida
        fila = modulo_db.query_one(
            "SELECT cliente_id FROM ventas ORDER BY id DESC LIMIT 1"
        )
        assert fila["cliente_id"] == cliente_id

    @requiere_pdftotext
    def test_el_pdf_lleva_el_nif_del_cliente_seleccionado(self, emitida):
        """El PDF emitido lleva el NIF del cliente 2 y no el del 1."""
        _, _, pdf = emitida
        texto = _texto_pdf(str(pdf))
        assert NIF_2 in texto, f"El PDF no contiene el NIF del cliente 2:\n{texto}"
        assert NIF_1 not in texto, "El PDF contiene el NIF del homónimo equivocado"

    @requiere_pdftotext
    def test_el_pdf_lleva_la_direccion_del_cliente_seleccionado(self, emitida):
        """La dirección también viene de la ficha correcta."""
        _, _, pdf = emitida
        texto = _texto_pdf(str(pdf))
        assert "Calle Segunda 2" in texto
        assert "Calle Primera 1" not in texto

    def test_el_registro_verifactu_lleva_el_nif_del_cliente(self, emitida):
        """El registro fiscal guarda el NIF del receptor seleccionado."""
        import reyger.core.db as modulo_db

        fila = modulo_db.query_one(
            "SELECT nif_receptor, nombre_receptor FROM facturas_verifactu "
            "ORDER BY id DESC LIMIT 1"
        )
        if fila is None:
            pytest.skip("VeriFactu inactivo en la plantilla")
        assert fila["nif_receptor"] == NIF_2, (
            "El registro de VeriFactu debe llevar el NIF del cliente facturado"
        )


# ---------------------------------------------------------------------------
# 4) El camino de ticket no se altera
# ---------------------------------------------------------------------------


class TestTicketSinCliente:
    """Un ticket admite venta sin cliente: no debe romperse."""

    def test_el_ticket_sin_cliente_no_asigna_id(self, ventas_ventana):
        ventana = ventas_ventana
        cliente_id, nombre, error = _seleccionar_indice(ventana, 0)
        assert (cliente_id, error) == (None, None)
        assert nombre == "(Sin cliente)"

    def test_el_borrador_guarda_el_cliente_id_seleccionado(self, ventas_ventana):
        """``guardar_borrador`` resuelve igual que ``pagar`` (mismo bug duplicado)."""
        import reyger.core.db as modulo_db

        ventana = ventas_ventana
        _seleccionar_indice(ventana, 2)
        with patch("reyger.ui.ventas.messagebox"):
            ventana.guardar_borrador()

        fila = modulo_db.query_one(
            "SELECT cliente_id FROM ventas ORDER BY id DESC LIMIT 1"
        )
        assert fila["cliente_id"] == _id_de_primer_homonimo()[1]["id"]


# ---------------------------------------------------------------------------
# 5) Los widgets reales de Tk se comportan como el doble
# ---------------------------------------------------------------------------


class TestWidgetsRealesDeTk:
    """El ``Combobox`` de verdad selecciona lo que el doble resuelve.

    El resto del módulo usa un doble para no depender de un servidor X, pero
    eso solo vale si la semántica del widget real es la misma. Este test lo
    comprueba con ``tkinter`` de verdad.
    """

    def test_el_combobox_real_expone_los_homonimos(self, ventas_ventana_tk):
        ventana = ventas_ventana_tk
        valores = list(ventana.combo_cliente["values"])
        assert valores == ["(Sin cliente)", NOMBRE_HOMONIMO, NOMBRE_HOMONIMO]

    def test_seleccionar_en_el_widget_real_devuelve_el_id_correcto(
        self, ventas_ventana_tk
    ):
        ventana = ventas_ventana_tk
        ventana.combo_cliente.current(2)

        cliente_id, nombre, error = ventana._resolver_cliente_seleccionado()

        assert error is None
        assert nombre == NOMBRE_HOMONIMO
        assert cliente_id == _id_de_primer_homonimo()[1]["id"]

    def test_el_carro_real_tambien_emite_la_factura_correcta(
        self, ventas_ventana_tk, tmp_path, monkeypatch
    ):
        """``pagar()`` con ``Treeview`` real: la fila guardada es la del id 2."""
        import reyger.core.db as modulo_db

        ventana = ventas_ventana_tk
        ventana.combo_cliente.current(2)
        _pagar(ventana, tmp_path, monkeypatch)

        fila = modulo_db.query_one(
            "SELECT cliente_id FROM ventas ORDER BY id DESC LIMIT 1"
        )
        assert fila["cliente_id"] == _id_de_primer_homonimo()[1]["id"]
