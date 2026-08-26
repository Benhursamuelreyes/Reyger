"""Tests de generación XML VeriFactu para envío a AEAT."""

import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

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


def test_registro_alta_estructura_basica():
    """El XML de RegistroAlta contiene los elementos obligatorios."""
    from reyger.domain.verifactu_xml import generar_registro_alta

    xml_str = generar_registro_alta(
        numero_factura="A-001",
        fecha="15-03-2024",
        nif_emisor="B12345678",
        nombre_emisor="Mi Empresa",
        tipo_comprobante="F1",
        base_imponible=100.0,
        tipo_iva=21.0,
        cuota_iva=21.0,
        total=121.0,
        huella="ABC123",
        huella_anterior="",
        fecha_generacion="2024-03-15T10:00:00+01:00",
        es_primer_registro=True,
    )

    root = ET.fromstring(xml_str)
    assert "RegistroAlta" in root.tag

    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else None
    prefix = f"{{{ns}}}" if ns else ""

    assert root.find(f"{prefix}IDVersion").text == "1.0"
    id_fac = root.find(f"{prefix}IDFactura")
    assert id_fac.find(f"{prefix}IDEmisorFactura").text == "B12345678"
    assert id_fac.find(f"{prefix}NumSerieFactura").text == "A-001"
    assert root.find(f"{prefix}NombreRazonEmisor").text == "Mi Empresa"
    assert root.find(f"{prefix}TipoFactura").text == "F1"
    assert root.find(f"{prefix}CuotaTotal").text == "21.00"
    assert root.find(f"{prefix}ImporteTotal").text == "121.00"
    assert root.find(f"{prefix}TipoHuella").text == "01"
    assert root.find(f"{prefix}Huella").text == "ABC123"


def test_registro_alta_primer_registro():
    """El primer registro incluye PrimerRegistro=S."""
    from reyger.domain.verifactu_xml import generar_registro_alta

    xml_str = generar_registro_alta(
        numero_factura="F-001", fecha="01-01-2024",
        nif_emisor="B12345678", nombre_emisor="Empresa",
        tipo_comprobante="F1", base_imponible=100.0,
        tipo_iva=21.0, cuota_iva=21.0, total=121.0,
        huella="", huella_anterior="",
        fecha_generacion="2024-01-01T10:00:00+01:00",
        es_primer_registro=True,
    )
    root = ET.fromstring(xml_str)
    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    enc = root.find(f"{p}Encadenamiento")
    assert enc is not None
    assert enc.find(f"{p}PrimerRegistro").text == "S"
    assert enc.find(f"{p}RegistroAnterior") is None


def test_registro_alta_encadenado():
    """Un registro encadenado incluye RegistroAnterior con Huella."""
    from reyger.domain.verifactu_xml import generar_registro_alta

    xml_str = generar_registro_alta(
        numero_factura="F-002", fecha="02-01-2024",
        nif_emisor="B12345678", nombre_emisor="Empresa",
        tipo_comprobante="F1", base_imponible=50.0,
        tipo_iva=21.0, cuota_iva=10.5, total=60.5,
        huella="HASH2", huella_anterior="HASH1",
        fecha_generacion="2024-01-02T10:00:00+01:00",
        es_primer_registro=False,
    )
    root = ET.fromstring(xml_str)
    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    enc = root.find(f"{p}Encadenamiento")
    assert enc.find(f"{p}PrimerRegistro") is None
    reg_ant = enc.find(f"{p}RegistroAnterior")
    assert reg_ant is not None
    assert reg_ant.find(f"{p}Huella").text == "HASH1"


def test_registro_alta_desglose():
    """El desglose incluye IVA con campos correctos."""
    from reyger.domain.verifactu_xml import generar_registro_alta

    xml_str = generar_registro_alta(
        numero_factura="F-003", fecha="01-01-2024",
        nif_emisor="B12345678", nombre_emisor="Empresa",
        tipo_comprobante="F1", base_imponible=200.0,
        tipo_iva=10.0, cuota_iva=20.0, total=220.0,
        huella="", huella_anterior="",
        fecha_generacion="2024-01-01T10:00:00+01:00",
        es_primer_registro=True,
    )
    root = ET.fromstring(xml_str)
    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    det = root.find(f"{p}Desglose/{p}DetalleDesglose")
    assert det.find(f"{p}Impuesto").text == "01"
    assert det.find(f"{p}ClaveRegimen").text == "01"
    assert det.find(f"{p}CalificacionOperacion").text == "S1"
    assert det.find(f"{p}TipoImpositivo").text == "10.00"
    assert det.find(f"{p}BaseImponibleOimporteNoSujeto").text == "200.00"
    assert det.find(f"{p}CuotaRepercutida").text == "20.00"


def test_registro_alta_sistema_informativo():
    """El SistemaInformatico tiene los campos identificativos de Reyger."""
    from reyger.domain.verifactu_xml import generar_registro_alta

    xml_str = generar_registro_alta(
        numero_factura="F-004", fecha="01-01-2024",
        nif_emisor="B12345678", nombre_emisor="Empresa",
        tipo_comprobante="F1", base_imponible=100.0,
        tipo_iva=21.0, cuota_iva=21.0, total=121.0,
        huella="", huella_anterior="",
        fecha_generacion="2024-01-01T10:00:00+01:00",
        es_primer_registro=True,
    )
    root = ET.fromstring(xml_str)
    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    sis = root.find(f"{p}SistemaInformatico")
    assert sis.find(f"{p}NombreSistemaInformatico").text == "Reyger"
    assert sis.find(f"{p}IdSistemaInformatico").text == "RG"
    assert sis.find(f"{p}TipoUsoPosibleSoloVerifactu").text == "S"


def test_envio_batch_multiples_facturas():
    """El batch contiene múltiples RegistroAlta."""
    from reyger.domain.verifactu_xml import generar_envio_batch

    facturas = [
        {
            "numero_factura": f"F-{i:03d}", "fecha": "01-01-2024",
            "nif_emisor": "B12345678", "nombre_emisor": "Empresa",
            "tipo_comprobante": "F1", "base_imponible": 100.0 * i,
            "tipo_iva": 21.0, "cuota_iva": 21.0 * i, "total": 121.0 * i,
            "huella": f"HASH{i}", "huella_anterior": f"HASH{i-1}" if i > 0 else "",
            "fecha_generacion": f"2024-01-01T{i+9:02d}:00:00+01:00",
            "es_primer_registro": i == 0,
        }
        for i in range(1, 4)
    ]
    xml_str = generar_envio_batch(facturas)
    root = ET.fromstring(xml_str)

    ns = root.tag.split("}")[0].lstrip("{") if "{" in root.tag else ""
    p = f"{{{ns}}}" if ns else ""

    registros = root.findall(f"{p}RegistroAlta")
    assert len(registros) == 3


def test_exportar_facturas_xml(tmp_path):
    """exportar_facturas_xml genera un fichero XML con las facturas pendientes."""
    import reyger.core.db as modulo_db
    from reyger.domain.verifactu_hash import calcular_huella
    from reyger.domain.verifactu_xml import exportar_facturas_xml

    conn = modulo_db.get_connection()
    h1 = calcular_huella(
        nif="B12345678", num_serie="X-1", fecha="01-01-2024",
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
        ("X-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente",
         100.0, 21, 21.0, 121.0, h1, "", 1, "F1", "cadena1",
         "2024-01-01T10:00:00+01:00", "pendiente"),
    )
    conn.commit()
    modulo_db.close()

    ruta_xml = str(tmp_path / "envio_aeat.xml")
    n = exportar_facturas_xml(ruta_xml, solo_pendientes=True)
    assert n == 1
    assert os.path.exists(ruta_xml)

    with open(ruta_xml, "r", encoding="utf-8") as f:
        contenido = f.read()
    assert "X-1" in contenido
    assert "B12345678" in contenido


def test_exportar_solo_pendientes(tmp_path):
    """Solo exporta facturas con estado_envio='pendiente'."""
    import reyger.core.db as modulo_db
    from reyger.domain.verifactu_hash import calcular_huella
    from reyger.domain.verifactu_xml import exportar_facturas_xml

    conn = modulo_db.get_connection()

    # Pendiente
    h1 = calcular_huella(
        nif="B12345678", num_serie="Y-1", fecha="01-01-2024",
        tipo_comprobante="F1", cuota_total=0.0, importe_total=100.0,
        huella_anterior="", fecha_hora_gen="2024-01-01T10:00:00+01:00",
    )
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion, "
        "estado_envio) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("Y-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente",
         100.0, 21, 0.0, 100.0, h1, "", 1, "F1", "cadena1",
         "2024-01-01T10:00:00+01:00", "pendiente"),
    )

    # Ya enviada
    h2 = calcular_huella(
        nif="B12345678", num_serie="Y-2", fecha="02-01-2024",
        tipo_comprobante="F1", cuota_total=0.0, importe_total=50.0,
        huella_anterior=h1, fecha_hora_gen="2024-01-02T10:00:00+01:00",
    )
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion, "
        "estado_envio) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("Y-2", "02-01-2024", "B12345678", "Y0000000B", "Cliente 2",
         50.0, 21, 0.0, 50.0, h2, h1, 2, "F1", "cadena2",
         "2024-01-02T10:00:00+01:00", "enviado"),
    )
    conn.commit()
    modulo_db.close()

    ruta_xml = str(tmp_path / "envio.xml")
    n = exportar_facturas_xml(ruta_xml, solo_pendientes=True)
    assert n == 1


def test_formato_fecha_aeat():
    """La función auxiliar formatea fechas correctamente."""
    from reyger.domain.verifactu_xml import _formato_fecha_aeat

    assert _formato_fecha_aeat("15/03/2024") == "15-03-2024"
    assert _formato_fecha_aeat("2024-03-15") == "15-03-2024"
    assert _formato_fecha_aeat("15-03-2024") == "15-03-2024"


def test_formato_importe():
    """Los importes se formatean con 2 decimales."""
    from reyger.domain.verifactu_xml import _formato_importe

    assert _formato_importe(123.4) == "123.40"
    assert _formato_importe(100.0) == "100.00"
    assert _formato_importe(0.0) == "0.00"
