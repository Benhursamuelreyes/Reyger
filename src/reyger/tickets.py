"""
Módulo para generación de tickets simplificados (tipo rollo de 80mm).
Útil para impresoras térmicas de recibos tradicionales.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from .config import ConfigManager
from .resources import get_db_path, get_output_path


class TicketSimplificado:
    """
    Generador de tickets simplificados en formato de rollo (80mm).
    Diseñado para impresoras térmicas.
    """
    
    def __init__(self, config_manager=None):
        """
        Inicializa el generador de tickets.
        
        Args:
            config_manager: Instancia de ConfigManager
        """
        self.config_manager = config_manager or ConfigManager()
        self.db_path = get_db_path()
        self.ancho_ticket = 80 * mm  # Tamaño estándar de impresora térmica
        self.alto_ticket = 297 * mm  # A4 de altura (se divide en varios tickets)
        self.estilos = getSampleStyleSheet()
        self._crear_estilos_personalizados()
    
    def _crear_estilos_personalizados(self):
        """Crea estilos personalizados para el ticket"""
        self.estilo_titulo = ParagraphStyle(
            'TicketTitle',
            parent=self.estilos['Heading1'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=6,
            alignment=1,  # Centrado
            fontName='Helvetica-Bold'
        )
        
        self.estilo_subtitulo = ParagraphStyle(
            'TicketSubtitle',
            parent=self.estilos['Normal'],
            fontSize=9,
            textColor=colors.black,
            spaceAfter=4,
            alignment=1,
            fontName='Helvetica'
        )
        
        self.estilo_normal = ParagraphStyle(
            'TicketNormal',
            parent=self.estilos['Normal'],
            fontSize=8,
            spaceAfter=2,
            alignment=0,  # Izquierda
            fontName='Helvetica'
        )
        
        self.estilo_centrado = ParagraphStyle(
            'TicketCentrado',
            parent=self.estilos['Normal'],
            fontSize=8,
            spaceAfter=2,
            alignment=1,  # Centrado
            fontName='Helvetica'
        )
    
    def generar_ticket(self, numero_factura, fecha, productos, total, 
                      metodo_pago="Efectivo", output_path=None):
        """
        Genera un ticket simplificado.
        
        Args:
            numero_factura: Número de la factura
            fecha: Fecha del ticket (datetime o string)
            productos: Lista de diccionarios con {nombre, cantidad, precio_unitario, subtotal}
            total: Total a pagar
            metodo_pago: Método de pago utilizado
            output_path: Ruta donde guardar el PDF
        
        Returns:
            Ruta del archivo PDF generado
        """
        
        if output_path is None:
            tickets_dir = get_output_path("tickets")
            output_path = os.path.join(
                tickets_dir,
                f"Ticket_{numero_factura}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        
        # Crear documento con tamaño de ticket
        doc = SimpleDocTemplate(
            output_path,
            pagesize=(self.ancho_ticket, 297 * mm),  # Ancho 80mm, alto A4
            rightMargin=3 * mm,
            leftMargin=3 * mm,
            topMargin=3 * mm,
            bottomMargin=3 * mm
        )
        
        story = []
        
        # 1. Encabezado del ticket
        nombre_empresa = self.config_manager.get("nombre_empresa", "Mi Empresa")
        story.extend(self._crear_encabezado_ticket(nombre_empresa))
        
        story.append(Spacer(1, 0.2 * mm))
        
        # 2. Información del ticket
        story.extend(self._crear_info_ticket(numero_factura, fecha))
        
        story.append(Spacer(1, 0.3 * mm))
        
        # Línea separadora
        story.append(Paragraph(
            "_" * 35,
            self.estilo_centrado
        ))
        
        story.append(Spacer(1, 0.2 * mm))
        
        # 3. Tabla de productos
        story.extend(self._crear_tabla_productos_ticket(productos))
        
        story.append(Spacer(1, 0.2 * mm))
        
        # Línea separadora
        story.append(Paragraph(
            "_" * 35,
            self.estilo_centrado
        ))
        
        story.append(Spacer(1, 0.3 * mm))
        
        # 4. Total
        story.extend(self._crear_total_ticket(total))
        
        story.append(Spacer(1, 0.3 * mm))
        
        # 5. Método de pago
        story.extend(self._crear_metodo_pago_ticket(metodo_pago))
        
        story.append(Spacer(1, 0.4 * mm))
        
        # 6. Pie de página
        story.extend(self._crear_pie_ticket())
        
        # Generar PDF
        doc.build(story)
        
        return output_path
    
    def _crear_encabezado_ticket(self, nombre_empresa):
        """Crea el encabezado del ticket"""
        elementos = []
        
        elementos.append(Paragraph(
            f"<b>{nombre_empresa.upper()}</b>",
            self.estilo_titulo
        ))
        
        elementos.append(Paragraph(
            "RECIBO DE VENTA",
            self.estilo_subtitulo
        ))
        
        return elementos
    
    def _crear_info_ticket(self, numero_factura, fecha):
        """Crea la información del ticket"""
        if isinstance(fecha, str):
            try:
                fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
            except:
                fecha_obj = datetime.now()
        else:
            fecha_obj = fecha
        
        fecha_str = fecha_obj.strftime("%d/%m/%Y %H:%M:%S")
        
        elementos = []
        elementos.append(Paragraph(
            f"Recibo: <b>{numero_factura}</b>",
            self.estilo_normal
        ))
        elementos.append(Paragraph(
            f"Fecha: {fecha_str}",
            self.estilo_normal
        ))
        
        return elementos
    
    def _crear_tabla_productos_ticket(self, productos):
        """Crea la tabla de productos para el ticket"""
        elementos = []
        
        # Encabezado
        datos = [["ARTÍCULO", "CANT.", "PRECIO", "SUB."]]
        
        # Agregar productos
        for prod in productos:
            nombre = prod.get('nombre_articulo', 'Sin nombre')
            cantidad = int(prod.get('cantidad', 0))
            precio = float(prod.get('valor_articulo', 0))
            subtotal = float(prod.get('subtotal', 0))
            
            # Truncar nombre si es muy largo
            nombre_corto = nombre[:25] if len(nombre) > 25 else nombre
            
            datos.append([
                nombre_corto,
                str(cantidad),
                f"{precio:.2f}",
                f"{subtotal:.2f}"
            ])
        
        # Crear tabla
        tabla = Table(datos, colWidths=[3.8*cm, 1*cm, 1.5*cm, 1.5*cm])
        tabla.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CCCCCC')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 2),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
            
            # Datos
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 1), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
            
            # Líneas
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elementos.append(tabla)
        return elementos
    
    def _crear_total_ticket(self, total):
        """Crea la sección de total"""
        elementos = []
        
        elementos.append(Paragraph(
            f"<b>TOTAL: {float(total):.2f} €</b>",
            self.estilo_titulo
        ))
        
        return elementos
    
    def _crear_metodo_pago_ticket(self, metodo_pago):
        """Crea la sección del método de pago"""
        elementos = []
        
        elementos.append(Paragraph(
            f"Pago: <b>{metodo_pago}</b>",
            self.estilo_centrado
        ))
        
        return elementos
    
    def _crear_pie_ticket(self):
        """Crea el pie del ticket"""
        elementos = []
        
        elementos.append(Spacer(1, 0.2*mm))
        
        elementos.append(Paragraph(
            "Gracias por su compra",
            self.estilo_centrado
        ))
        
        elementos.append(Paragraph(
            "Conserve este recibo",
            self.estilo_centrado
        ))
        
        hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
        elementos.append(Paragraph(
            f"<i>{hora_actual}</i>",
            self.estilo_centrado
        ))
        
        return elementos
