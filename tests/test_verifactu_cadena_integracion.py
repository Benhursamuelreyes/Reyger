"""Tests de integración del ENCADENAMIENTO de la cadena de hashes VeriFactu.

Estos tests ejercitan el camino real de producción
(``FacturaVeriFACTU.guardar_datos_factura_db``) en vez de construir la
cadena a mano, porque el encadenamiento automático es justo lo que puede
fallar sin que nada se entere: una ``huella_anterior`` vacía no lanza
ninguna excepción, simplemente deja la cadena rota y el verificador
interno marca la factura como corrupta.

Regresión que cubren: la búsqueda del antecesor leía la serie
``business_profile.numero_series`` ('A') en lugar de la serie con la que se
numeran las facturas (``numero_serie_factura``, 'F-' por defecto). Como el
patrón ``A-%`` no casa con ningún número emitido, **toda** factura se
registraba con ``huella_anterior`` vacía.
"""

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)

NIF_EMISOR = "B12345678"
NIF_RECEPTOR = "B87654321"


@pytest.fixture(autouse=True)
def _bd_temporal(tmp_path):
    """Redirige la capa de datos a una BD temporal con la plantilla."""
    import reyger.core.db as modulo_db

    ruta = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta)
    original = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()
    yield
    modulo_db.close()
    modulo_db.get_db_path = original


def _emitir(generador, numero, fecha="02/10/2026"):
    """Registra una factura por el camino real de producción."""
    guardado = generador.guardar_datos_factura_db(
        numero_factura=numero,
        fecha=fecha,
        nif_emisor=NIF_EMISOR,
        nif_receptor=NIF_RECEPTOR,
        nombre_receptor="Farmacia Test SL",
        base_imponible=100.0,
        tipo_iva=21,
        total_iva=21.0,
        total=121.0,
        productos=[{
            "nombre_articulo": "Paracetamol 1g",
            "valor_articulo": 100.0,
            "cantidad": 1,
            "subtotal": 100.0,
        }],
    )
    assert guardado, f"La factura {numero} no se pudo registrar (excepción silenciada)"
    return numero


def _huellas():
    """Devuelve ``[(numero_factura, huella, huella_anterior)]`` en orden de cadena."""
    import reyger.core.db as modulo_db

    return [
        (f["numero_factura"], f["huella"], f["huella_anterior"])
        for f in modulo_db.query(
            "SELECT numero_factura, huella, huella_anterior "
            "FROM facturas_verifactu ORDER BY numero_ord ASC, id ASC"
        )
    ]


# ── Requisito explícito del encargo ─────────────────────────────────


class TestEncadenamientoCadenaReal:
    """Tres facturas seguidas por el camino de producción."""

    def test_tres_facturas_consecutivas_encadenan(self):
        """F1 vacía -> F2 encadena con F1 -> F3 encadena con F2."""
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU

        generador = FacturaVeriFACTU()
        _emitir(generador, "F-0001")
        _emitir(generador, "F-0002")
        _emitir(generador, "F-0003")

        (_, huella_1, anterior_1), (_, huella_2, anterior_2), (_, huella_3, anterior_3) = _huellas()

        assert anterior_1 == "", "La primera factura inicia la cadena: Huella vacía"
        assert anterior_2 == huella_1, "La 2ª factura debe encadenar con la 1ª"
        assert anterior_3 == huella_2, "La 3ª factura debe encadenar con la 2ª"

    def test_la_cadena_supera_el_verificador_del_producto(self):
        """El validador interno marca las 3 facturas como íntegras."""
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        from reyger.domain.verifactu_hash import verificar_cadena

        generador = FacturaVeriFACTU()
        for numero in ("F-0001", "F-0002", "F-0003"):
            _emitir(generador, numero)

        resultados = verificar_cadena()

        assert len(resultados) == 3
        rotas = [r for r in resultados if not r["ok"]]
        assert not rotas, f"Facturas marcadas como corruptas: {rotas}"


# ── La serie no puede estar cableada ────────────────────────────────


class TestSerieNoCableada:
    """El encadenamiento sigue la serie real, no una constante."""

    def test_la_serie_por_defecto_no_usa_el_campo_heredado_A(self):
        """Pinzá el bug: ``numero_series`` sigue a 'A' y aun así encadena."""
        from reyger.ui import business_profile as bp
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Test SL", nif=NIF_EMISOR)
        modulo_db.close()
        assert bp.obtener_campo("numero_series") == "A"
        assert bp.obtener_campo("numero_serie_factura") == "F-"

        generador = FacturaVeriFACTU()
        _emitir(generador, "F-0001")
        _emitir(generador, "F-0002")

        (_, huella_1, _), (_, _, anterior_2) = _huellas()
        assert anterior_2 == huella_1

    def test_una_serie_personalizada_tambien_encadena(self):
        """Con serie 'FAC-' configurada, las facturas FAC-* encadenan igual."""
        from reyger.ui import business_profile as bp
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Test SL", nif=NIF_EMISOR, numero_serie_factura="FAC-")
        modulo_db.close()

        generador = FacturaVeriFACTU()
        _emitir(generador, "FAC-0001")
        _emitir(generador, "FAC-0002")

        (_, huella_1, anterior_1), (_, _, anterior_2) = _huellas()
        assert anterior_1 == ""
        assert anterior_2 == huella_1

    def test_serie_con_numero_inicial_usa_el_prefijo_real(self):
        """Configurar 'F-100' no rompe la cadena: los números salen 'F-0100'..."""
        from reyger.ui import business_profile as bp
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        import reyger.core.db as modulo_db

        bp.guardar(nombre="Test SL", nif=NIF_EMISOR, numero_serie_factura="F-100")
        modulo_db.close()

        generador = FacturaVeriFACTU()
        _emitir(generador, "F-0100")
        _emitir(generador, "F-0101")

        (_, huella_1, anterior_1), (_, _, anterior_2) = _huellas()
        assert anterior_1 == ""
        assert anterior_2 == huella_1

    def test_series_distintas_no_se_encadenan_entre_si(self):
        """La cadena es por serie: una factura 'A-*' no precede a una 'F-*'."""
        from reyger.domain.facturas_verifactu import FacturaVeriFACTU
        from reyger.domain.verifactu_hash import obtener_huella_anterior
        import reyger.core.db as modulo_db

        generador = FacturaVeriFACTU()
        _emitir(generador, "F-0001")

        # Se inyecta una factura de otra serie, como si existiera del histórico.
        conn = modulo_db.get_connection()
        conn.execute(
            "INSERT INTO facturas_verifactu "
            "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
            "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
            "numero_ord) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("A-9999", "01/10/2026", NIF_EMISOR, NIF_RECEPTOR, "Otra",
             100.0, 21, 21.0, 121.0, "H" * 64, "", 99),
        )
        conn.commit()

        huella, numero, _ = obtener_huella_anterior(numero_factura="F-0002")
        assert numero == "F-0001", "Debe encadenar con su propia serie, no con 'A-9999'"
        assert huella != "H" * 64


# ── La suite debe detectar la regresión ──────────────────────────────


class TestLaSerieSeDeduceDelCodigo:
    """Prueba de que estos tests atań el fallo (fallan si se revierte)."""

    def test_el_antecesoro_se_busca_por_la_serie_de_la_factura(self):
        """``obtener_huella_anterior`` debe derivar la serie de la factura."""
        from reyger.domain.verifactu_hash import _prefijo_serie_factura

        assert _prefijo_serie_factura("F-0001") == "F-"
        assert _prefijo_serie_factura("FAC-0042") == "FAC-"
        assert _prefijo_serie_factura() == "F-", "Sin número, usa la serie configurada"

    def test_huella_anterior_acepta_numero_de_factura(self):
        """La firma acepta el número completo de la factura en curso."""
        import inspect

        from reyger.domain.verifactu_hash import obtener_huella_anterior

        parametros = inspect.signature(obtener_huella_anterior).parameters
        assert "numero_factura" in parametros
