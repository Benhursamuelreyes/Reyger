"""
Módulo para generación de facturas en formato VeriFACTU conforme a la normativa 
de la Agencia Tributaria Española (Hacienda).

Requisitos:
- pip install qrcode[pil]
- pip install reportlab
"""

import os
from datetime import datetime
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image
import qrcode
from ..config import ConfigManager
from ..ui import business_profile as bp
from ..core import db
from ..resources import get_output_path
from .pdf_documento import PdfDocumento


class FacturaVeriFACTU:
    """
    Clase para generar facturas en formato VeriFACTU.
    Cumple con la normativa de la Agencia Tributaria española.
    """
    
    def __init__(self, config_manager=None):
        """
        Inicializa el generador de facturas VeriFACTU.
        
        Args:
            config_manager: Instancia de ConfigManager para acceder a la configuración
        """
        self.config_manager = config_manager or ConfigManager()
        self.pdf = PdfDocumento(self.config_manager)
    
    def crear_factura_verifactu(self, numero_factura, fecha, nif_emisor, nif_receptor,
                               nombre_receptor, productos, base_imponible, tipo_iva=21,
                               total_iva=0, total=0, output_path=None):
        """
        Crea una factura en formato VeriFACTU (PDF A4 estandarizado).
        
        Args:
            numero_factura: Número correlativo de la factura
            fecha: Fecha de emisión (datetime object o string)
            nif_emisor: NIF del emisor (empresa)
            nif_receptor: NIF del receptor (cliente)
            nombre_receptor: Nombre del cliente
            productos: Lista de diccionarios con {nombre, cantidad, precio_unitario, etc}
            base_imponible: Base imponible sin IVA
            tipo_iva: Tipo de IVA aplicado (4, 10 o 21)
            total_iva: Total de IVA
            total: Total a pagar
            output_path: Ruta donde guardar el PDF
        
        Returns:
            Ruta del archivo PDF generado
        """
        
        if output_path is None:
            facturas_dir = get_output_path("facturas_verifactu")
            output_path = os.path.join(
                facturas_dir,
                f"Factura_VeriFACTU_{numero_factura}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        nif_final = nif_emisor or bp.nif()

        # Generar el código QR de verificación AEAT.
        codigo_qr = self._crear_codigo_qr(
            numero_factura, fecha, nif_final, nif_receptor, total
        )

        return self.pdf.generar(
            output_path=output_path,
            titulo_documento=bp.nombre_empresa(),
            subtitulo_documento="FACTURA VeriFACTU",
            numero=numero_factura,
            fecha=fecha,
            cliente_nombre=nombre_receptor,
            cliente_nif=nif_receptor,
            productos=productos,
            base_imponible=base_imponible,
            tipo_iva=tipo_iva,
            total_iva=total_iva,
            total=total,
            codigo_qr=codigo_qr,
            campos_firma=False,
            pie_legal=(
                "<i>Esta factura cumple con los requisitos del artículo 34 de la Ley 37/1992, de 28 de diciembre, "
                "del Impuesto sobre el Valor Añadido. Factura emitida según la normativa de la Agencia Tributaria española. "
                "Registro de Facturas de Ingresos disponible en la empresa.</i>"
            ),
        )
    
    def _crear_codigo_qr(self, numero_factura, fecha, nif_emisor, nif_receptor, total):
        """Crea el código QR de verificación AEAT como flowable."""
        from .verifactu_hash import generar_url_qr

        url_qr = generar_url_qr(
            nif=nif_emisor,
            num_serie=numero_factura,
            fecha=fecha,
            importe_total=float(total),
            produccion=False,
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=2,
        )
        qr.add_data(url_qr)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_qr.save(f, format="PNG")
            ruta_qr = f.name

        elementos = [Spacer(1, 0.4 * cm)]
        datos_qr_tabla = [
            [
                Image(ruta_qr, width=3 * cm, height=3 * cm),
                Paragraph(
                    "<i>Escanee este código para verificar<br/>la autenticidad de la factura</i>",
                    self.pdf.estilo_normal,
                ),
            ]
        ]

        tabla_qr = Table(datos_qr_tabla, colWidths=[3 * cm, 10 * cm])
        tabla_qr.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elementos.append(tabla_qr)
        return elementos
    
    def guardar_datos_factura_db(self, numero_factura, fecha, nif_emisor, nif_receptor,
                                 nombre_receptor, base_imponible, tipo_iva, total_iva,
                                 total, productos, estado="Emitida"):
        """Guarda la factura en BD con la cadena de hash VeriFactu.

        Calcula la huella SHA-256, la cadena de valores y el encadenamiento
        con la factura anterior conforme a la spec AEAT.
        """
        try:
            from .verifactu_hash import calcular_huella_para_factura
            from ..ui import business_profile as bp

            nif = nif_emisor or bp.nif() or ""
            num_serie = numero_factura
            tipo_comp = "F1"
            numero_series = bp.obtener_campo("numero_series") or "A"

            huella, cadena, huella_ant, fecha_gen = calcular_huella_para_factura(
                nif=nif, num_serie=num_serie, fecha=fecha,
                tipo_comprobante=tipo_comp,
                cuota_total=total_iva, importe_total=total,
            )

            conn = db.get_connection()

            # Obtener el siguiente número ordinal
            fila_max = conn.execute(
                "SELECT IFNULL(MAX(numero_ord), 0) FROM facturas_verifactu"
            ).fetchone()
            numero_ord = (fila_max[0] if fila_max else 0) + 1

            cursor = conn.execute("""
                INSERT INTO facturas_verifactu
                (numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor,
                 base_imponible, tipo_iva, total_iva, total, estado,
                 huella, huella_anterior, numero_ord, tipo_comprobante,
                 cadena_valores, fecha_generacion, estado_envio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')
            """, (numero_factura, fecha, nif, nif_receptor, nombre_receptor,
                  base_imponible, tipo_iva, total_iva, total, estado,
                  huella, huella_ant, numero_ord, tipo_comp,
                  cadena, fecha_gen))

            factura_id = cursor.lastrowid

            for prod in productos:
                conn.execute("""
                    INSERT INTO facturas_verifactu_productos
                    (factura_id, nombre_producto, cantidad, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    factura_id,
                    prod.get('nombre_articulo', '') if isinstance(prod, dict) else prod[0],
                    prod.get('cantidad', 0) if isinstance(prod, dict) else prod[2],
                    prod.get('valor_articulo', 0) if isinstance(prod, dict) else prod[1],
                    prod.get('subtotal', 0) if isinstance(prod, dict) else prod[3],
                ))

            conn.commit()
            return True
        except Exception:
            return False
