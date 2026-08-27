"""
Módulo para generación de albaranes (documentos de entrega sin valor fiscal).
"""

import os
from datetime import datetime
from ..config import ConfigManager
from . import business_profile as bp
from ..core import db
from ..resources import get_output_path
from ..domain.pdf_documento import PdfDocumento


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
        self.pdf = PdfDocumento(self.config_manager)
    
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

        # Los albaranes son documentos de gestión sin desglose fiscal.
        productos_tabla = [
            {
                "nombre_articulo": p.get("nombre_articulo", "Sin nombre"),
                "cantidad": p.get("cantidad", 0),
                "valor_articulo": 0,
                "subtotal": 0,
                "descripcion": p.get("descripcion", ""),
            }
            for p in productos
        ]

        return self.pdf.generar(
            output_path=output_path,
            titulo_documento=bp.nombre_empresa(),
            subtitulo_documento="ALBARÁN DE ENTREGA",
            numero=numero_albaran,
            fecha=fecha,
            cliente_nombre=cliente_nombre,
            cliente_direccion=cliente_direccion,
            productos=productos_tabla,
            observaciones=observaciones,
            campos_firma=True,
            columnas_productos=["DESCRIPCIÓN", "CANTIDAD", "UNIDAD", "OBSERVACIONES"],
        )
    
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
