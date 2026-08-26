"""
Módulo para generación de facturas en formato VeriFACTU conforme a la normativa 
de la Agencia Tributaria Española (Hacienda).

Requisitos:
- pip install qrcode[pil]
- pip install reportlab
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from io import BytesIO
from ..config import ConfigManager
from ..ui import business_profile as bp
from ..core import db
from ..resources import get_output_path


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
        self.estilos = getSampleStyleSheet()
        self._crear_estilos_personalizados()
    
    def _crear_estilos_personalizados(self):
        """Crea estilos personalizados para el PDF"""
        # Estilo para encabezado
        self.estilo_titulo = ParagraphStyle(
            'CustomTitle',
            parent=self.estilos['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0078D4'),
            spaceAfter=30,
            alignment=1  # Centrado
        )
        
        # Estilo para subtítulos
        self.estilo_subtitulo = ParagraphStyle(
            'CustomSubtitle',
            parent=self.estilos['Heading2'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para texto normal
        self.estilo_normal = ParagraphStyle(
            'CustomNormal',
            parent=self.estilos['Normal'],
            fontSize=10,
            spaceAfter=6
        )
    
    def crear_factura_verifactu(self, numero_factura, fecha, nif_emisor, nif_receptor,
                               nombre_receptor, productos, base_imponible, tipo_iva=21,
                               total_iva=0, total=0, output_path=None):
        """
        Crea una factura en formato VeriFACTU.
        
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
            # Crear carpeta de facturas si no existe
            facturas_dir = get_output_path("facturas_verifactu")
            output_path = os.path.join(
                facturas_dir,
                f"Factura_VeriFACTU_{numero_factura}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        # Crear documento PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )
        
        story = []
        
        # 1. Encabezado con datos de la empresa emisora
        nombre_empresa = bp.nombre_empresa()
        nif_final = nif_emisor or bp.nif()
        story.extend(self._crear_encabezado(nombre_empresa, nif_final))
        
        story.append(Spacer(1, 0.5*cm))
        
        # 2. Información de la factura
        story.extend(self._crear_info_factura(numero_factura, fecha))
        
        story.append(Spacer(1, 0.3*cm))
        
        # 3. Datos del receptor (cliente)
        story.extend(self._crear_datos_cliente(nif_receptor, nombre_receptor))
        
        story.append(Spacer(1, 0.3*cm))
        
        # 4. Tabla de productos/servicios
        story.extend(self._crear_tabla_productos(productos))
        
        story.append(Spacer(1, 0.3*cm))
        
        # 5. Tabla de totales (Base, IVA, Total)
        story.extend(self._crear_tabla_totales(base_imponible, tipo_iva, total_iva, total))
        
        story.append(Spacer(1, 0.5*cm))
        
        # 6. Código QR de verificación
        story.extend(self._crear_codigo_qr(numero_factura, fecha, nif_emisor, nif_receptor, total))
        
        # 7. Legal (Régimen de facturación)
        story.extend(self._crear_pie_legal())
        
        # Generar PDF
        doc.build(story)
        
        return output_path
    
    def _crear_encabezado(self, nombre_empresa, nif_emisor):
        """Crea el encabezado con datos de la empresa"""
        elementos = []
        
        # Intentar cargar logo
        logo_path = self.config_manager.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            try:
                elementos.append(Spacer(1, 0.2*cm))
                img = ImageReader(logo_path)
                elementos.append(Paragraph(
                    f'<img src="{logo_path}" width="80" height="80"/>',
                    self.estilos['Normal']
                ))
                elementos.append(Spacer(1, 0.3*cm))
            except:
                pass
        
        # Nombre empresa y NIF
        elementos.append(Paragraph(
            f"<b>{nombre_empresa.upper()}</b>",
            self.estilo_titulo
        ))
        elementos.append(Paragraph(
            f"NIF: <b>{nif_emisor}</b>",
            self.estilo_normal
        ))
        
        return elementos
    
    def _crear_info_factura(self, numero_factura, fecha):
        """Crea la sección de información de la factura"""
        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha, "%Y-%m-%d")
        
        fecha_formateada = fecha.strftime("%d/%m/%Y")
        
        elementos = []
        elementos.append(Paragraph(
            f"<b>FACTURA VeriFACTU</b>",
            self.estilo_subtitulo
        ))
        
        datos_factura = [
            ["Número de Factura:", numero_factura],
            ["Fecha de emisión:", fecha_formateada],
            ["Régimen:", "Régimen general de facturación"],
        ]
        
        tabla = Table(datos_factura, colWidths=[4*cm, 12*cm])
        tabla.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0078D4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elementos.append(tabla)
        return elementos
    
    def _crear_datos_cliente(self, nif_receptor, nombre_receptor):
        """Crea la sección de datos del cliente"""
        elementos = []
        elementos.append(Paragraph(
            "<b>DATOS DEL CLIENTE</b>",
            self.estilo_subtitulo
        ))
        
        datos_cliente = [
            ["Nombre/Razón Social:", nombre_receptor],
            ["NIF/VAT ID:", nif_receptor],
        ]
        
        tabla = Table(datos_cliente, colWidths=[4*cm, 12*cm])
        tabla.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0078D4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elementos.append(tabla)
        return elementos
    
    def _crear_tabla_productos(self, productos):
        """Crea la tabla de productos/servicios"""
        elementos = []
        
        # Encabezados de tabla
        datos_tabla = [
            ["DESCRIPCIÓN", "CANTIDAD", "P. UNITARIO (€)", "SUBTOTAL (€)"]
        ]
        
        # Agregar productos
        for prod in productos:
            nombre = prod.get('nombre_articulo', 'Sin nombre')
            cantidad = prod.get('cantidad', 0)
            precio = prod.get('valor_articulo', 0)
            subtotal = prod.get('subtotal', cantidad * precio)
            
            datos_tabla.append([
                nombre,
                str(cantidad),
                f"{float(precio):.2f}",
                f"{float(subtotal):.2f}"
            ])
        
        # Crear tabla
        tabla = Table(datos_tabla, colWidths=[7*cm, 2.5*cm, 3*cm, 3*cm])
        tabla.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Datos
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            # Líneas
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        
        elementos.append(tabla)
        return elementos
    
    def _crear_tabla_totales(self, base_imponible, tipo_iva, total_iva, total):
        """Crea la tabla de cálculo de totales"""
        elementos = []
        elementos.append(Spacer(1, 0.2*cm))
        
        # Tabla de totales alineada a la derecha
        datos_totales = [
            ["Subtotal (Base Imponible):", f"{float(base_imponible):.2f} €"],
            [f"IVA {tipo_iva}%:", f"{float(total_iva):.2f} €"],
            ["TOTAL A PAGAR:", f"{float(total):.2f} €"],
        ]
        
        tabla = Table(datos_totales, colWidths=[9*cm, 3*cm])
        tabla.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('TEXTCOLOR', (0, -1), (0, -1), colors.HexColor('#0078D4')),
            ('TEXTCOLOR', (1, -1), (1, -1), colors.HexColor('#0078D4')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F0F7')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elementos.append(tabla)
        return elementos
    
    def _crear_codigo_qr(self, numero_factura, fecha, nif_emisor, nif_receptor, total):
        """Crea el código QR de verificación con URL AEAT VeriFactu."""
        from .verifactu_hash import generar_url_qr

        elementos = []
        elementos.append(Spacer(1, 0.4*cm))

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
        
        # Guardar en BytesIO para usar en el PDF
        qr_bytes = BytesIO()
        img_qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        
        # Crear elemento de imagen para el PDF
        img_reader = ImageReader(qr_bytes)
        
        # Tabla con QR y texto
        datos_qr_tabla = [
            [
                Image(img_reader, width=3*cm, height=3*cm),
                Paragraph(
                    f"<i>Escanee este código para verificar<br/>la autenticidad de la factura</i>",
                    self.estilo_normal
                )
            ]
        ]
        
        tabla_qr = Table(datos_qr_tabla, colWidths=[3*cm, 10*cm])
        tabla_qr.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elementos.append(tabla_qr)
        return elementos
    
    def _crear_pie_legal(self):
        """Crea el pie de página con información legal"""
        elementos = []
        elementos.append(Spacer(1, 0.4*cm))
        
        texto_legal = (
            "<i>Esta factura cumple con los requisitos del artículo 34 de la Ley 37/1992, de 28 de diciembre, "
            "del Impuesto sobre el Valor Añadido. Factura emitida según la normativa de la Agencia Tributaria española. "
            "Registro de Facturas de Ingresos disponible en la empresa.</i>"
        )
        
        elementos.append(Paragraph(texto_legal, self.estilo_normal))
        
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
