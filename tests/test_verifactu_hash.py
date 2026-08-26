"""Tests del motor de hashing SHA-256 VeriFactu.

Valida contra los vectores oficiales de la AEAT (doc v0.1.2, 27/08/2024).
"""

import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


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


def test_vector_aeat_caso_1():
    """Vector oficial AEAT caso 1: primera factura, sin huella anterior."""
    from reyger.domain.verifactu_hash import calcular_huella

    hash_resultado = calcular_huella(
        nif="89890001K",
        num_serie="12345678/G33",
        fecha="01-01-2024",
        tipo_comprobante="F1",
        cuota_total=12.35,
        importe_total=123.45,
        huella_anterior="",
        fecha_hora_gen="2024-01-01T19:20:30+01:00",
    )
    esperado = "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
    assert hash_resultado == esperado
    assert len(hash_resultado) == 64


def test_vector_aeat_caso_2():
    """Vector oficial AEAT caso 2: factura encadenada con hash anterior."""
    from reyger.domain.verifactu_hash import calcular_huella

    hash_1 = calcular_huella(
        nif="89890001K",
        num_serie="12345678/G33",
        fecha="01-01-2024",
        tipo_comprobante="F1",
        cuota_total=12.35,
        importe_total=123.45,
        huella_anterior="",
        fecha_hora_gen="2024-01-01T19:20:30+01:00",
    )
    hash_2 = calcular_huella(
        nif="89890001K",
        num_serie="12345679/G34",
        fecha="01-01-2024",
        tipo_comprobante="F1",
        cuota_total=12.35,
        importe_total=123.45,
        huella_anterior=hash_1,
        fecha_hora_gen="2024-01-01T19:20:35+01:00",
    )
    esperado = "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97"
    assert hash_2 == esperado


def test_cadena_valores_formato():
    """La cadena de valores tiene el formato exacto NAME=VALUE&..."""
    from reyger.domain.verifactu_hash import construir_cadena_valores

    cadena = construir_cadena_valores(
        nif="B12345678",
        num_serie="F-2024-001",
        fecha="15/03/2024",
        tipo_comprobante="F1",
        cuota_total=21.00,
        importe_total=121.00,
        huella_anterior="ABC123",
        fecha_hora_gen="2024-03-15T10:30:00+01:00",
    )
    assert "IDEmisorFactura=B12345678" in cadena
    assert "NumSerieFactura=F-2024-001" in cadena
    assert "FechaExpedicionFactura=15-03-2024" in cadena
    assert "TipoFactura=F1" in cadena
    assert "CuotaTotal=21.00" in cadena
    assert "ImporteTotal=121.00" in cadena
    assert "Huella=ABC123" in cadena
    assert "&" in cadena
    assert cadena.count("&") == 7


def test_cadena_valores_huella_vacia():
    """Cuando no hay huella anterior, el campo Huella queda vacío."""
    from reyger.domain.verifactu_hash import construir_cadena_valores

    cadena = construir_cadena_valores(
        nif="B12345678",
        num_serie="F-2024-001",
        fecha="15-03-2024",
        tipo_comprobante="F1",
        cuota_total=0.0,
        importe_total=100.00,
        huella_anterior="",
        fecha_hora_gen="2024-03-15T10:30:00+01:00",
    )
    assert "Huella=&FechaHoraHusoGenRegistro=" in cadena


def test_formato_fecha_aeat():
    """Acepta DD/MM/YYYY, DD-MM-YYYY y YYYY-MM-DD; devuelve DD-MM-YYYY."""
    from reyger.domain.verifactu_hash import _formato_fecha_aeat

    assert _formato_fecha_aeat("15/03/2024") == "15-03-2024"
    assert _formato_fecha_aeat("15-03-2024") == "15-03-2024"
    assert _formato_fecha_aeat("2024-03-15") == "15-03-2024"


def test_formato_timestamp_aeat():
    """Genera timestamp ISO 8601 con offset +02:00 por defecto."""
    from reyger.domain.verifactu_hash import _formato_timestamp_aeat

    ts = _formato_timestamp_aeat("2024-01-01T19:20:30+01:00")
    assert ts == "2024-01-01T19:20:30+01:00"

    ts_auto = _formato_timestamp_aeat()
    assert "T" in ts_auto
    assert "+02:00" in ts_auto


def test_url_qr_preproduccion():
    """URL de QR en preproducción."""
    from reyger.domain.verifactu_hash import generar_url_qr

    url = generar_url_qr("B12345678", "F-2024-001", "01-01-2024", 123.45)
    assert url.startswith("https://prewww2.aeat.es/")
    assert "nif=B12345678" in url
    assert "numserie=F-2024-001" in url
    assert "fecha=01-01-2024" in url
    assert "importe=123.45" in url


def test_url_qr_produccion():
    """URL de QR en producción."""
    from reyger.domain.verifactu_hash import generar_url_qr

    url = generar_url_qr("B12345678", "F-2024-001", "01-01-2024", 123.45, produccion=True)
    assert url.startswith("https://www2.agenciatributaria.gob.es/")


def test_url_qr_codifica_ampersand():
    """El & en el número de serie se codifica como %26 en la URL QR."""
    from reyger.domain.verifactu_hash import generar_url_qr

    url = generar_url_qr("B12345678", "F/2024&001", "01-01-2024", 50.00)
    assert "%26" in url
    assert "&001" not in url.split("numserie=")[1].split("&")[0]


def test_calcular_huella_64caracteres():
    """El hash tiene exactamente 64 caracteres hex mayúsculas."""
    from reyger.domain.verifactu_hash import calcular_huella

    h = calcular_huella(
        nif="X0000000A",
        num_serie="T-1",
        fecha="01-01-2024",
        tipo_comprobante="F2",
        cuota_total=0.0,
        importe_total=10.0,
        huella_anterior="",
        fecha_hora_gen="2024-01-01T00:00:00+01:00",
    )
    assert len(h) == 64
    assert h == h.upper()
    assert all(c in "0123456789ABCDEF" for c in h)


def test_hash_sensible_a_cambios():
    """Un cambio en cualquier campo produce un hash distinto."""
    from reyger.domain.verifactu_hash import calcular_huella

    base = calcular_huella(
        nif="B12345678", num_serie="F-1", fecha="01-01-2024",
        tipo_comprobante="F1", cuota_total=21.0, importe_total=121.0,
        huella_anterior="", fecha_hora_gen="2024-01-01T00:00:00+01:00",
    )
    # Cambiar NIF
    otro = calcular_huella(
        nif="B87654321", num_serie="F-1", fecha="01-01-2024",
        tipo_comprobante="F1", cuota_total=21.0, importe_total=121.0,
        huella_anterior="", fecha_hora_gen="2024-01-01T00:00:00+01:00",
    )
    assert base != otro


def test_verificar_cadena_vacia():
    """Verificar cadena sin facturas devuelve lista vacía."""
    from reyger.domain.verifactu_hash import verificar_cadena

    resultados = verificar_cadena()
    assert resultados == []


def test_verificar_cadena_integra():
    """Inserta 3 facturas encadenadas y verifica que la cadena es íntegra."""
    import reyger.core.db as modulo_db
    from reyger.domain.verifactu_hash import calcular_huella, verificar_cadena

    conn = modulo_db.get_connection()

    # Factura 1
    h1 = calcular_huella(
        nif="B12345678", num_serie="A-1", fecha="01-01-2024",
        tipo_comprobante="F1", cuota_total=21.0, importe_total=121.0,
        huella_anterior="", fecha_hora_gen="2024-01-01T10:00:00+01:00",
    )
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("A-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente 1",
         100.0, 21, 21.0, 121.0, h1, "", 1, "F1",
         f"IDEmisorFactura=B12345678&NumSerieFactura=A-1&FechaExpedicionFactura=01-01-2024&TipoFactura=F1&CuotaTotal=21.00&ImporteTotal=121.00&Huella=&FechaHoraHusoGenRegistro=2024-01-01T10:00:00+01:00",
         "2024-01-01T10:00:00+01:00"),
    )

    # Factura 2
    h2 = calcular_huella(
        nif="B12345678", num_serie="A-2", fecha="02-01-2024",
        tipo_comprobante="F1", cuota_total=4.20, importe_total=24.20,
        huella_anterior=h1, fecha_hora_gen="2024-01-02T10:00:00+01:00",
    )
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("A-2", "02-01-2024", "B12345678", "Y0000000B", "Cliente 2",
         20.0, 21, 4.2, 24.2, h2, h1, 2, "F1",
         f"IDEmisorFactura=B12345678&NumSerieFactura=A-2&FechaExpedicionFactura=02-01-2024&TipoFactura=F1&CuotaTotal=4.20&ImporteTotal=24.20&Huella={h1}&FechaHoraHusoGenRegistro=2024-01-02T10:00:00+01:00",
         "2024-01-02T10:00:00+01:00"),
    )

    # Factura 3
    h3 = calcular_huella(
        nif="B12345678", num_serie="A-3", fecha="03-01-2024",
        tipo_comprobante="F1", cuota_total=10.50, importe_total=60.50,
        huella_anterior=h2, fecha_hora_gen="2024-01-03T10:00:00+01:00",
    )
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("A-3", "03-01-2024", "B12345678", "Y0000000C", "Cliente 3",
         50.0, 21, 10.5, 60.5, h3, h2, 3, "F1",
         f"IDEmisorFactura=B12345678&NumSerieFactura=A-3&FechaExpedicionFactura=03-01-2024&TipoFactura=F1&CuotaTotal=10.50&ImporteTotal=60.50&Huella={h2}&FechaHoraHusoGenRegistro=2024-01-03T10:00:00+01:00",
         "2024-01-03T10:00:00+01:00"),
    )
    conn.commit()
    modulo_db.close()

    resultados = verificar_cadena()
    assert len(resultados) == 3
    assert all(r["ok"] for r in resultados)


def test_verificar_cadena_rota():
    """Si se altera una huella, la verificación lo detecta."""
    import reyger.core.db as modulo_db
    from reyger.domain.verifactu_hash import calcular_huella, verificar_cadena

    conn = modulo_db.get_connection()

    h1 = calcular_huella(
        nif="B12345678", num_serie="B-1", fecha="01-01-2024",
        tipo_comprobante="F1", cuota_total=0.0, importe_total=100.0,
        huella_anterior="", fecha_hora_gen="2024-01-01T10:00:00+01:00",
    )
    # Insertar con huella alterada
    conn.execute(
        "INSERT INTO facturas_verifactu "
        "(numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor, "
        "base_imponible, tipo_iva, total_iva, total, huella, huella_anterior, "
        "numero_ord, tipo_comprobante, cadena_valores, fecha_generacion) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("B-1", "01-01-2024", "B12345678", "Y0000000A", "Cliente",
         100.0, 21, 0.0, 100.0, "FALSA" + "0" * 59, "", 1, "F1",
         "cadena_falsa", "ts"),
    )
    conn.commit()
    modulo_db.close()

    resultados = verificar_cadena()
    assert len(resultados) == 1
    assert not resultados[0]["ok"]
    assert any("huella mismatch" in e for e in resultados[0]["errores"])
