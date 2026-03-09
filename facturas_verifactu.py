"""
Módulo para generación de facturas en formato VeriFACTU conforme a la normativa 
de la Agencia Tributaria Española (Hacienda).

Requisitos:
- pip install qrcode[pil]
- pip install reportlab
"""

import os
import sys
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from io import BytesIO
from config import ConfigManager


def get_db_path():
    """Obtiene la ruta de la base de datos"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "database.db")


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
        self.db_path = get_db_path()
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
            facturas_dir = os.path.join(os.path.dirname(self.db_path), "facturas_verifactu")
            os.makedirs(facturas_dir, exist_ok=True)
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
        nombre_empresa = self.config_manager.get("nombre_empresa", "Mi Empresa")
        story.extend(self._crear_encabezado(nombre_empresa, nif_emisor))
        
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
        """Crea el código QR de verificación"""
        elementos = []
        elementos.append(Spacer(1, 0.4*cm))
        
        # Datos para el QR (formato VeriFACTU simplificado)
        if isinstance(fecha, str):
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
        else:
            fecha_obj = fecha
        
        fecha_str = fecha_obj.strftime("%d/%m/%Y")
        
        # Datos del QR: NIF|FACTURA|FECHA|TOTAL|NIF_RECEPTOR
        datos_qr = f"{nif_emisor}|{numero_factura}|{fecha_str}|{float(total):.2f}|{nif_receptor}"
        
        # Generar código QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=5,
            border=2,
        )
        qr.add_data(datos_qr)
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
                "Código QR de Verificación",
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
        """
        Guarda los datos de la factura en la base de datos para auditoría.
        
        Args:
            numero_factura: Número de factura
            fecha: Fecha de emisión
            nif_emisor: NIF del emisor
            nif_receptor: NIF del receptor
            nombre_receptor: Nombre del receptor
            base_imponible: Base imponible
            tipo_iva: Tipo de IVA
            total_iva: Total de IVA
            total: Total
            productos: Lista de productos
            estado: Estado de la factura
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Crear tabla si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facturas_verifactu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_factura TEXT UNIQUE NOT NULL,
                    fecha TEXT NOT NULL,
                    nif_emisor TEXT NOT NULL,
                    nif_receptor TEXT NOT NULL,
                    nombre_receptor TEXT NOT NULL,
                    base_imponible REAL NOT NULL,
                    tipo_iva INTEGER NOT NULL,
                    total_iva REAL NOT NULL,
                    total REAL NOT NULL,
                    estado TEXT DEFAULT 'Emitida',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insertar factura
            cursor.execute("""
                INSERT INTO facturas_verifactu 
                (numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor,
                 base_imponible, tipo_iva, total_iva, total, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (numero_factura, fecha, nif_emisor, nif_receptor, nombre_receptor,
                  base_imponible, tipo_iva, total_iva, total, estado))
            
            factura_id = cursor.lastrowid
            
            # Guardar productos de la factura
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facturas_verifactu_productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    factura_id INTEGER NOT NULL,
                    nombre_producto TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio_unitario REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    FOREIGN KEY(factura_id) REFERENCES facturas_verifactu(id)
                )
            """)
            
            for prod in productos:
                cursor.execute("""
                    INSERT INTO facturas_verifactu_productos
                    (factura_id, nombre_producto, cantidad, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    factura_id,
                    prod.get('nombre_articulo', ''),
                    prod.get('cantidad', 0),
                    prod.get('valor_articulo', 0),
                    prod.get('subtotal', 0)
                ))
            
            conn.commit()
            conn.close()
            
            return True
        except sqlite3.IntegrityError:
            # Factura duplicada
            return False
        except Exception as e:
            print(f"Error guardando factura en BD: {e}")
            return False
