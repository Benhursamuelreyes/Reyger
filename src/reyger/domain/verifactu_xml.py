"""Generación XML para el envío de facturas a la AEAT (VeriFactu).

Genera XML conforme al esquema ``SuministroInformacion.xsd`` de la
Agencia Tributaria, listo para su envío mediante el web service
``SistemaFacturacion`` (operación ``RegFactuSistemaFacturacion``).

No requiere firma electrónica: los sistemas VERI*FACTU están exentos
de firma digital según la normativa vigente.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional

from ..core import db
from ..ui import business_profile as bp


def _texto(valor) -> str:
    """Convierte un valor a texto limpio para XML."""
    if valor is None:
        return ""
    return str(valor).strip()


def _formato_fecha_aeat(fecha: str) -> str:
    """Convierte fecha a ``DD-MM-YYYY`` para el XML AEAT."""
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return fecha


def _formato_importe(valor: float) -> str:
    r"""Formatea un importe para el XML: ``(\+|-)?\d{1,12}(\.\d{0,2})?``."""
    return f"{valor:.2f}"


def generar_registro_alta(
    numero_factura: str,
    fecha: str,
    nif_emisor: str,
    nombre_emisor: str,
    tipo_comprobante: str,
    base_imponible: float,
    tipo_iva: float,
    cuota_iva: float,
    total: float,
    huella: str,
    huella_anterior: str,
    fecha_generacion: str,
    nombre_receptor: Optional[str] = None,
    nif_receptor: Optional[str] = None,
    es_primer_registro: bool = False,
) -> str:
    """Genera el XML de un RegistroAlta conforme al esquema AEAT.

    Devuelve una cadena con el XML formateado.
    """
    ns = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"

    root = ET.Element("RegistroAlta")
    root.set("xmlns", ns)

    ET.SubElement(root, "IDVersion").text = "1.0"

    id_factura = ET.SubElement(root, "IDFactura")
    ET.SubElement(id_factura, "IDEmisorFactura").text = _texto(nif_emisor)
    ET.SubElement(id_factura, "NumSerieFactura").text = _texto(numero_factura)
    ET.SubElement(id_factura, "FechaExpedicionFactura").text = _formato_fecha_aeat(fecha)

    ET.SubElement(root, "NombreRazonEmisor").text = _texto(nombre_emisor)
    ET.SubElement(root, "TipoFactura").text = _texto(tipo_comprobante)

    desglose = ET.SubElement(root, "Desglose")
    detalle = ET.SubElement(desglose, "DetalleDesglose")
    ET.SubElement(detalle, "Impuesto").text = "01"  # IVA
    ET.SubElement(detalle, "ClaveRegimen").text = "01"  # Régimen general
    ET.SubElement(detalle, "CalificacionOperacion").text = "S1"  # Sujeto, no exento
    ET.SubElement(detalle, "TipoImpositivo").text = f"{tipo_iva:.2f}"
    ET.SubElement(detalle, "BaseImponibleOimporteNoSujeto").text = _formato_importe(base_imponible)
    ET.SubElement(detalle, "CuotaRepercutida").text = _formato_importe(cuota_iva)

    ET.SubElement(root, "CuotaTotal").text = _formato_importe(cuota_iva)
    ET.SubElement(root, "ImporteTotal").text = _formato_importe(total)

    encadenamiento = ET.SubElement(root, "Encadenamiento")
    if es_primer_registro:
        ET.SubElement(encadenamiento, "PrimerRegistro").text = "S"
    else:
        reg_ant = ET.SubElement(encadenamiento, "RegistroAnterior")
        ET.SubElement(reg_ant, "Huella").text = _texto(huella_anterior)

    sistema = ET.SubElement(root, "SistemaInformatico")
    ET.SubElement(sistema, "NombreRazon").text = _texto(nombre_emisor)
    ET.SubElement(sistema, "NIF").text = _texto(nif_emisor)
    ET.SubElement(sistema, "NombreSistemaInformatico").text = "Reyger"
    ET.SubElement(sistema, "IdSistemaInformatico").text = "RG"
    ET.SubElement(sistema, "Version").text = "1.0"
    ET.SubElement(sistema, "NumeroInstalacion").text = _texto(nif_emisor)
    ET.SubElement(sistema, "TipoUsoPosibleSoloVerifactu").text = "S"
    ET.SubElement(sistema, "TipoUsoPosibleMultiOT").text = "N"
    ET.SubElement(sistema, "IndicadorMultiplesOT").text = "N"

    ET.SubElement(root, "FechaHoraHusoGenRegistro").text = _texto(fecha_generacion)
    ET.SubElement(root, "TipoHuella").text = "01"
    ET.SubElement(root, "Huella").text = _texto(huella)

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(
        indent="  ", encoding=None
    )
    return xml_str


def generar_envio_batch(facturas: list[dict]) -> str:
    """Genera el XML de envío de un lote de facturas (max 1000).

    Cada elemento de *facturas* es un diccionario con los campos de
    ``generar_registro_alta``.

    Devuelve una cadena con el XML completo.
    """
    ns_lr = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
    ns = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"

    root = ET.Element("RegistroFacturacion")
    root.set("xmlns", ns_lr)
    root.set("xmlns:tns", ns)

    for factura in facturas[:1000]:
        registro = ET.SubElement(root, "RegistroAlta")

        ET.SubElement(registro, "IDVersion").text = "1.0"

        id_factura = ET.SubElement(registro, "IDFactura")
        ET.SubElement(id_factura, "IDEmisorFactura").text = _texto(factura.get("nif_emisor"))
        ET.SubElement(id_factura, "NumSerieFactura").text = _texto(factura.get("numero_factura"))
        ET.SubElement(id_factura, "FechaExpedicionFactura").text = _formato_fecha_aeat(
            factura.get("fecha", "")
        )

        ET.SubElement(registro, "NombreRazonEmisor").text = _texto(factura.get("nombre_emisor"))
        ET.SubElement(registro, "TipoFactura").text = _texto(
            factura.get("tipo_comprobante", "F1")
        )

        desglose = ET.SubElement(registro, "Desglose")
        detalle = ET.SubElement(desglose, "DetalleDesglose")
        ET.SubElement(detalle, "Impuesto").text = "01"
        ET.SubElement(detalle, "ClaveRegimen").text = "01"
        ET.SubElement(detalle, "CalificacionOperacion").text = "S1"
        ET.SubElement(detalle, "TipoImpositivo").text = f"{factura.get('tipo_iva', 21.0):.2f}"
        ET.SubElement(detalle, "BaseImponibleOimporteNoSujeto").text = _formato_importe(
            factura.get("base_imponible", 0.0)
        )
        ET.SubElement(detalle, "CuotaRepercutida").text = _formato_importe(
            factura.get("cuota_iva", 0.0)
        )

        ET.SubElement(registro, "CuotaTotal").text = _formato_importe(
            factura.get("cuota_iva", 0.0)
        )
        ET.SubElement(registro, "ImporteTotal").text = _formato_importe(
            factura.get("total", 0.0)
        )

        encadenamiento = ET.SubElement(registro, "Encadenamiento")
        es_primero = factura.get("es_primer_registro", False)
        if es_primero:
            ET.SubElement(encadenamiento, "PrimerRegistro").text = "S"
        else:
            reg_ant = ET.SubElement(encadenamiento, "RegistroAnterior")
            ET.SubElement(reg_ant, "Huella").text = _texto(factura.get("huella_anterior", ""))

        sistema = ET.SubElement(registro, "SistemaInformatico")
        ET.SubElement(sistema, "NombreRazon").text = _texto(factura.get("nombre_emisor"))
        ET.SubElement(sistema, "NIF").text = _texto(factura.get("nif_emisor"))
        ET.SubElement(sistema, "NombreSistemaInformatico").text = "Reyger"
        ET.SubElement(sistema, "IdSistemaInformatico").text = "RG"
        ET.SubElement(sistema, "Version").text = "1.0"
        ET.SubElement(sistema, "NumeroInstalacion").text = _texto(factura.get("nif_emisor"))
        ET.SubElement(sistema, "TipoUsoPosibleSoloVerifactu").text = "S"
        ET.SubElement(sistema, "TipoUsoPosibleMultiOT").text = "N"
        ET.SubElement(sistema, "IndicadorMultiplesOT").text = "N"

        ET.SubElement(registro, "FechaHoraHusoGenRegistro").text = _texto(
            factura.get("fecha_generacion", "")
        )
        ET.SubElement(registro, "TipoHuella").text = "01"
        ET.SubElement(registro, "Huella").text = _texto(factura.get("huella", ""))

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(
        indent="  ", encoding=None
    )
    return xml_str


def exportar_facturas_xml(ruta_salida: str, solo_pendientes: bool = True) -> int:
    """Exporta facturas de la BD a un fichero XML listo para envío a AEAT.

    Devuelve el número de facturas exportadas.
    """
    from ..ui import business_profile as bp

    nif = bp.nif() or ""
    nombre = bp.nombre_empresa() or ""

    condicion = "WHERE estado_envio = 'pendiente'" if solo_pendientes else ""
    filas = db.query(
        f"SELECT numero_factura, fecha, nif_emisor, tipo_comprobante, "
        f"total_iva, total, base_imponible, tipo_iva, huella, huella_anterior, "
        f"fecha_generacion, numero_ord "
        f"FROM facturas_verifactu {condicion} ORDER BY numero_ord ASC, id ASC"
    )

    if not filas:
        return 0

    facturas_xml = []
    for i, fila in enumerate(filas):
        facturas_xml.append({
            "numero_factura": fila["numero_factura"],
            "fecha": fila["fecha"],
            "nif_emisor": fila["nif_emisor"] or nif,
            "nombre_emisor": nombre,
            "tipo_comprobante": fila["tipo_comprobante"],
            "base_imponible": fila["base_imponible"],
            "tipo_iva": fila["tipo_iva"],
            "cuota_iva": fila["total_iva"],
            "total": fila["total"],
            "huella": fila["huella"] or "",
            "huella_anterior": fila["huella_anterior"] or "",
            "fecha_generacion": fila["fecha_generacion"] or "",
            "es_primer_registro": i == 0 and not fila["huella_anterior"],
        })

    xml_content = generar_envio_batch(facturas_xml)

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(xml_content)

    return len(facturas_xml)
