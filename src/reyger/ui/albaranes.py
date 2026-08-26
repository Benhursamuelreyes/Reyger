"""
Módulo para generación de albaranes (documentos de entrega sin valor fiscal).
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from ..config import ConfigManager
from . import business_profile as bp
from ..core import db
from ..resources import get_output_path


class AlbaranEntrega:
    """
    Generador de albaranes de entrega (documentos sin valor fiscal).
    """
    
    def __init__(self, config_manager=None):
        """
        Inicializa el generador de albaranes.
        
        Args:
            config_manager: Instancia de ConfigManager
        """
        self.config_manager = config_manager or ConfigManager()
        self.estilos = getSampleStyleSheet()
        self._crear_estilos_personalizados()
    
    def _crear_estilos_personalizados(self):
        """Crea estilos personalizados para el albarán"""
        self.estilo_titulo = ParagraphStyle(
            'AlbaranTitle',
            parent=self.estilos['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#0078D4'),
            spaceAfter=20,
            alignment=1,  # Centrado
            fontName='Helvetica-Bold'
        )
        
        self.estilo_subtitulo = ParagraphStyle(
            'AlbaranSubtitle',
            parent=self.estilos['Heading2'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        self.estilo_normal = ParagraphStyle(
            'AlbaranNormal',
            parent=self.estilos['Normal'],
            fontSize=10,
            spaceAfter=6
        )
    
    def crear_albaran(self, numero_albaran, fecha, cliente_nombre, cliente_direccion,
                     productos, observaciones="", output_path=None):
        """
        Crea un albarán de entrega.
        
        Args:
            numero_albaran: Número correlativo del albarán
            fecha: Fecha del albarán (datetime o string)
            cliente_nombre: Nombre del cliente
            cliente_direccion: Dirección del cliente
            productos: Lista de diccionarios con {nombre, cantidad, descripcion}
            observaciones: Observaciones adicionales
            output_path: Ruta donde guardar el PDF
        
        Returns:
            Ruta del archivo PDF generado
        """
        
        if output_path is None:
            albaranes_dir = get_output_path("albaranes")
            output_path = os.path.join(
                albaranes_dir,
                f"Albaran_{numero_albaran}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
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
        
        # 1. Encabezado
        nombre_empresa = bp.nombre_empresa()
        story.extend(self._crear_encabezado_albaran(nombre_empresa))
        
        story.append(Spacer(1, 0.4*cm))
        
        # 2. Información del albarán
        story.extend(self._crear_info_albaran(numero_albaran, fecha))
        
        story.append(Spacer(1, 0.3*cm))
        
        # 3. Datos del cliente
        story.extend(self._crear_datos_cliente_albaran(cliente_nombre, cliente_direccion))
        
        story.append(Spacer(1, 0.3*cm))
        
        # 4. Tabla de productos
        story.extend(self._crear_tabla_productos_albaran(productos))
        
        story.append(Spacer(1, 0.4*cm))
        
        # 5. Observaciones
        if observaciones.strip():
            story.extend(self._crear_observaciones_albaran(observaciones))
            story.append(Spacer(1, 0.3*cm))
        
        # 6. Campos de firma
        story.extend(self._crear_campos_firma_albaran())
        
        # Generar PDF
        doc.build(story)
        
        return output_path
    
    def _crear_encabezado_albaran(self, nombre_empresa):
        """Crea el encabezado del albarán con datos del negocio."""
        elementos = []

        elementos.append(Paragraph(
            f"<b>{nombre_empresa.upper()}</b>",
            self.estilo_titulo
        ))

        perfil = bp.obtener()
        if perfil:
            p = dict(perfil)
            lineas_contacto = []
            if p.get("nif"):
                lineas_contacto.append(f"NIF: {p['nif']}")
            if p.get("direccion"):
                dir_completa = p["direccion"]
                if p.get("codigo_postal"):
                    dir_completa += f", {p['codigo_postal']}"
                if p.get("provincia"):
                    dir_completa += f" — {p['provincia']}"
                lineas_contacto.append(dir_completa)
            if p.get("telefono"):
                lineas_contacto.append(f"Tel: {p['telefono']}")
            if p.get("email"):
                lineas_contacto.append(f"Email: {p['email']}")
            if lineas_contacto:
                elementos.append(Paragraph(
                    " | ".join(lineas_contacto),
                    self.estilo_normal
                ))

        elementos.append(Spacer(1, 0.2 * cm))

        elementos.append(Paragraph(
            "<b>ALBARÁN DE ENTREGA</b>",
            self.estilo_subtitulo
        ))

        elementos.append(Paragraph(
            "<i>Documento de gestión. No tiene carácter de factura.</i>",
            self.estilo_normal
        ))

        return elementos
    
    def _crear_info_albaran(self, numero_albaran, fecha):
        """Crea la información del albarán"""
        if isinstance(fecha, str):
            try:
                fecha_obj = datetime.strptime(fecha, "%Y-%m-%d")
            except:
                fecha_obj = datetime.now()
        else:
            fecha_obj = fecha
        
        fecha_str = fecha_obj.strftime("%d/%m/%Y")
        
        datos_albaran = [
            ["Número de Albarán:", numero_albaran],
            ["Fecha de entrega:", fecha_str],
        ]
        
        tabla = Table(datos_albaran, colWidths=[4*cm, 12*cm])
        tabla.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0078D4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        return [tabla]
    
    def _crear_datos_cliente_albaran(self, cliente_nombre, cliente_direccion):
        """Crea la sección de datos del cliente"""
        elementos = []
        
        elementos.append(Paragraph(
            "<b>DATOS DEL CLIENTE</b>",
            self.estilo_subtitulo
        ))
        
        datos_cliente = [
            ["Nombre/Empresa:", cliente_nombre],
            ["Dirección:", cliente_direccion],
        ]
        
        tabla = Table(datos_cliente, colWidths=[4*cm, 12*cm])
        tabla.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#0078D4')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        return [tabla]
    
    def _crear_tabla_productos_albaran(self, productos):
        """Crea la tabla de productos entregados"""
        elementos = []
        
        # Encabezados
        datos_tabla = [
            ["DESCRIPCIÓN", "CANTIDAD", "UNIDAD", "OBSERVACIONES"]
        ]
        
        # Agregar productos
        for prod in productos:
            nombre = prod.get('nombre_articulo', 'Sin nombre')
            cantidad = str(prod.get('cantidad', 0))
            descripcion = prod.get('descripcion', '')
            
            datos_tabla.append([
                nombre,
                cantidad,
                "Ud.",
                descripcion
            ])
        
        tabla = Table(datos_tabla, colWidths=[5.5*cm, 2.5*cm, 2*cm, 6*cm])
        tabla.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0078D4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Datos
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (2, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            # Líneas
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        
        return [tabla]
    
    def _crear_observaciones_albaran(self, observaciones):
        """Crea la sección de observaciones"""
        elementos = []
        
        elementos.append(Paragraph(
            "<b>OBSERVACIONES</b>",
            self.estilo_subtitulo
        ))
        
        elementos.append(Paragraph(
            observaciones,
            self.estilo_normal
        ))
        
        return elementos
    
    def _crear_campos_firma_albaran(self):
        """Crea los campos de firma"""
        elementos = []
        
        elementos.append(Paragraph(
            "<b>CONFORMIDAD DE ENTREGA</b>",
            self.estilo_subtitulo
        ))
        
        # Tabla con espacios para firmas
        datos_firma = [
            ["Conforme conforme entrega", "Firma y sello del cliente"],
            [" ", " "],
            [" ", " "],
            [" ", " "],
        ]
        
        tabla_firma = Table(datos_firma, colWidths=[7.5*cm, 7.5*cm])
        tabla_firma.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            
            ('TOPPADDING', (0, 1), (-1, -1), 40),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            ('GRID', (0, 1), (-1, 3), 1, colors.black),
            ('ALIGN', (0, 1), (-1, 3), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 3), 'TOP'),
        ]))
        
        return [tabla_firma]
    
    def guardar_albaran_db(self, numero_albaran, fecha, cliente_nombre, cliente_direccion,
                          productos, observaciones=""):
        """
        Guarda los datos del albarán en la base de datos.
        
        Args:
            numero_albaran: Número del albarán
            fecha: Fecha
            cliente_nombre: Nombre del cliente
            cliente_direccion: Dirección del cliente
            productos: Lista de productos
            observaciones: Observaciones
        
        Returns:
            Boolean indicando éxito
        """
        try:
            conn = db.get_connection()
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS albaranes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_albaran TEXT UNIQUE NOT NULL,
                    fecha TEXT NOT NULL,
                    cliente_nombre TEXT NOT NULL,
                    cliente_direccion TEXT NOT NULL,
                    observaciones TEXT,
                    estado TEXT DEFAULT 'Abierto',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor = conn.execute("""
                INSERT INTO albaranes 
                (numero_albaran, fecha, cliente_nombre, cliente_direccion, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, (numero_albaran, fecha, cliente_nombre, cliente_direccion, observaciones))
            
            albaran_id = cursor.lastrowid
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS albaranes_productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    albaran_id INTEGER NOT NULL,
                    nombre_producto TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    descripcion TEXT,
                    FOREIGN KEY(albaran_id) REFERENCES albaranes(id)
                )
            """)
            
            for prod in productos:
                conn.execute("""
                    INSERT INTO albaranes_productos
                    (albaran_id, nombre_producto, cantidad, descripcion)
                    VALUES (?, ?, ?, ?)
                """, (
                    albaran_id,
                    prod.get('nombre_articulo', ''),
                    prod.get('cantidad', 0),
                    prod.get('descripcion', '')
                ))
            
            conn.commit()
            
            return True
        except Exception:
            return False
    
    def cambiar_estado_albaran(self, numero_albaran, nuevo_estado):
        """
        Cambia el estado de un albarán (Abierto, Entregado, Rechazado).
        
        Args:
            numero_albaran: Número del albarán
            nuevo_estado: Nuevo estado
        
        Returns:
            Boolean indicando éxito
        """
        try:
            conn = db.get_connection()
            
            conn.execute("""
                UPDATE albaranes 
                SET estado = ? 
                WHERE numero_albaran = ?
            """, (nuevo_estado, numero_albaran))
            
            conn.commit()
            
            return True
        except Exception:
            return False
