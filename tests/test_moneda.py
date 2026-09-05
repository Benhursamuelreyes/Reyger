"""Tests del módulo multimoneda y configuración regional (core/moneda.py).

Cubren el formateo global de importes según moneda/locale, la
persistencia en business_profile y que los valores se siguen guardando
como números puros en la BD (el símbolo se aplica solo al mostrarlos).
"""

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_bd(tmp_path):
    """BD temporal con esquema al día (migraciones 1..8)."""
    import reyger.core.db as modulo_db
    from reyger.core import migrations

    ruta_bd = str(tmp_path / "tienda.db")
    tmp_tmpl = str(tmp_path / "plantilla.db")
    shutil.copyfile(PLANTILLA, tmp_tmpl)
    # Llevar la copia al día (por si la plantilla quedó atrás por defecto)
    import sqlite3
    conn = sqlite3.connect(tmp_tmpl)
    migrations.run_migrations(conn)
    conn.close()
    shutil.copyfile(tmp_tmpl, ruta_bd)

    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original


def _importar_moneda():
    from reyger.core import moneda as mod_moneda
    return mod_moneda


def test_defecto_es_eur_espana():
    """Sin configurar, se usa EUR + es_ES."""
    m = _importar_moneda()
    assert m.codigo_moneda() == "EUR"
    assert m.locale_activo() == "es_ES"
    assert m.simbolo_moneda() == "€"
    assert m.format_currency(1234567.5) == "1.234.567,50 €"


def test_formato_number_es_espana():
    """Los separadores de miles/decimales del locale se aplican."""
    m = _importar_moneda()
    assert m.format_number(1234567.5) == "1.234.567,50"
    assert m.format_number(1234) == "1.234,00"


def test_moneda_usd_locale_en_us():
    """USD + en_US → símbolo prefijo y separadores anglosajones."""
    from reyger.ui import business_profile as bp
    import reyger.core.db as modulo_db

    bp.guardar(moneda="USD", locale="en_US")
    modulo_db.close()

    m = _importar_moneda()
    assert m.codigo_moneda() == "USD"
    assert m.simbolo_moneda() == "$"
    assert m.format_currency(1234567.5) == "$1,234,567.50"


def test_moneda_hnl():
    """HNL → símbolo L con posición prefijo."""
    from reyger.ui import business_profile as bp
    import reyger.core.db as modulo_db

    bp.guardar(moneda="HNL", locale="es_HN")
    modulo_db.close()

    m = _importar_moneda()
    assert m.codigo_moneda() == "HNL"
    assert m.simbolo_moneda() == "L"
    assert m.format_currency(1234567.5) == "L1,234,567.50"


def test_moneda_desconocida_vuelve_a_eur():
    """Un código no soportado cae a EUR por defecto."""
    from reyger.ui import business_profile as bp
    import reyger.core.db as modulo_db

    bp.guardar(moneda="XXX")
    modulo_db.close()

    m = _importar_moneda()
    assert m.codigo_moneda() == "EUR"


def test_format_currency_posicion_explicita():
    """Se puede forzar el símbolo/posición sin cambiar la moneda global."""
    m = _importar_moneda()
    assert m.format_currency(1234.56, simbolo="€", posicion=False) == "1.234,56 €"
    assert m.format_currency(1234.56, simbolo="$", posicion=True) == "$1.234,56"


def test_decimales_jpy():
    """JPY se formatea sin decimales por defecto."""
    from reyger.ui import business_profile as bp
    import reyger.core.db as modulo_db

    bp.guardar(moneda="JPY", locale="ja_JP")
    modulo_db.close()

    m = _importar_moneda()
    assert m.format_currency(1234) == "¥1,234"


def test_bd_almacena_numeros_puros():
    """Los importes se guardan como números (REAL), no formateados."""
    from reyger.ui import business_profile as bp

    # La preferencia de moneda sí va a la BD como texto de configuración
    bp.guardar(nombre="Tienda Test", moneda="USD")
    fila = bp.obtener()
    assert fila["moneda"] == "USD"

    # Simula una venta: el importe se persiste como número puro, no como
    # cadena formateada.
    import reyger.core.db as modulo_db
    conn = modulo_db.get_connection()
    conn.execute(
        """
        INSERT INTO inventario (nombre, proveedor, precio, costo, stock, tipo_iva)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("Producto X", "Proveedor", 10.5, 8.0, 100, 21.0),
    )
    conn.execute(
        """
        INSERT INTO ventas (factura, nombre_articulo, valor_articulo, cantidad,
            subtotal, metodo_pago, tipo_iva, cuota_iva, base_imponible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "Producto X", 10.5, 2, 21.0, "Efectivo", 21.0, 3.64, 17.36),
    )
    conn.commit()

    venta = modulo_db.query_one("SELECT valor_articulo, subtotal FROM ventas WHERE id = 1")
    assert isinstance(venta["valor_articulo"], float)
    assert isinstance(venta["subtotal"], float)
    assert venta["valor_articulo"] == 10.5
    assert venta["subtotal"] == 21.0


def test_regiones_consistentes():
    """Los catálogos (PAISES/LOCALES/MONEDAS) son coherentes entre sí."""
    m = _importar_moneda()

    assert len(m.LOCALES) == len(m.PAISES)
    for locale in m.LOCALES:
        assert locale in m.PAISES, f"LOCALES sin país: {locale}"
    for locale in m.PAISES:
        assert locale in m.LOCALES, f"PAISES sin separadores: {locale}"
        assert m.PAISES[locale]["moneda"] in m.MONEDAS
    for codigo, info in m.MONEDAS.items():
        for campo in ("simbolo", "posicion", "nombre"):
            assert campo in info, f"MONEDA {codigo} sin {campo}"
    assert len(m.PAISES) >= 50
    continentes = m.continentes()
    for cinco in ("Asia", "África", "América", "Europa", "Oceanía"):
        assert cinco in continentes, f"Falta continente {cinco}"


def test_zona_euro_solo_pais():
    """Coalición monetaria: solo se añade el país; la moneda es compartida."""
    m = _importar_moneda()
    eurozona = ("es_ES", "de_DE", "fr_FR", "it_IT", "pt_PT",
                "nl_NL", "el_GR", "en_IE", "de_AT", "fi_FI", "nl_BE")
    for locale in eurozona:
        assert m.moneda_para_locale(locale) == "EUR"


def test_nombres_legibles_pais_y_moneda():
    """La UI muestra [nombre del país] y [nombre de la moneda], no códigos."""
    m = _importar_moneda()
    assert m.nombre_moneda("EUR") == "Euro"
    assert m.nombre_moneda("JPY") == "Yen japonés"
    assert m.nombre_moneda("USD") == "Dólar estadounidense"
    assert m.pais_por_locale("es_ES") == ("España", "EUR")
    assert m.pais_por_locale("ja_JP") == ("Japón", "JPY")
    orden_nombres = [m.MONEDAS[c]["nombre"] for c in m.monedas_ordenadas()]
    assert orden_nombres == sorted(orden_nombres)
    orden_paises = [m.PAISES[l]["pais"] for l in m.paises_ordenados()]
    assert orden_paises == sorted(orden_paises)


def test_formateo_con_separadores_sobrescritos():
    """Sobrescribir separadores permite previsualizar otra región sin
    cambiar la configuración persistida."""
    m = _importar_moneda()
    assert m.format_currency(
        1234567.5, simbolo="$", posicion=True,
        separacion=(",", "."),
    ) == "$1,234,567.50"
    assert m.format_currency(
        1234567.5, simbolo="€", posicion=False,
        separacion=(".", ","),
    ) == "1.234.567,50 €"
