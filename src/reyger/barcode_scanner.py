"""
Módulo para soporte de escáner de código de barras.
Los escáneres USB funcionan como teclados HID, por lo que se capturan
los códigos escaneados y se buscan automáticamente en el inventario.
"""

import sqlite3
import tkinter as tk
from tkinter import messagebox
from .resources import get_db_path


class EscanerCodigoBarras:
    """
    Gestor de códigos de barras.
    Busca productos por código de barras en el inventario.
    """
    
    def __init__(self, db_path=None):
        """
        Inicializa el escáner.
        
        Args:
            db_path: Ruta de la base de datos
        """
        self.db_path = db_path or get_db_path()
        self.crear_columna_codigo_barras()
    
    def crear_columna_codigo_barras(self):
        """
        Crea la columna codigo_barras en la tabla inventario si no existe.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Intenta agregar la columna
            try:
                cursor.execute("""
                    ALTER TABLE inventario 
                    ADD COLUMN codigo_barras TEXT UNIQUE
                """)
                conn.commit()
            except sqlite3.OperationalError:
                # La columna ya existe
                pass
            
            conn.close()
        except Exception as e:
            print(f"Error creando columna: {e}")
    
    def buscar_producto_por_codigo(self, codigo_barras):
        """
        Busca un producto por su código de barras.
        
        Args:
            codigo_barras: Código a buscar
        
        Returns:
            Diccionario con datos del producto o None si no existe
        """
        if not codigo_barras or not codigo_barras.strip():
            return None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT id, nombre, precio, stock, codigo_barras 
                    FROM inventario 
                    WHERE codigo_barras = ?
                """, (codigo_barras.strip(),)).fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'precio': row[2],
                    'stock': row[3],
                    'codigo_barras': row[4]
                }
            return None
        except Exception as e:
            print(f"Error buscando producto: {e}")
            return None
    
    def guardar_codigo_barras(self, id_producto, codigo_barras):
        """
        Guarda el código de barras para un producto.
        
        Args:
            id_producto: ID del producto en la tabla inventario
            codigo_barras: Código de barras a guardar
        
        Returns:
            Boolean indicando éxito
        """
        if not codigo_barras or not codigo_barras.strip():
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE inventario 
                    SET codigo_barras = ? 
                    WHERE id = ?
                """, (codigo_barras.strip(), id_producto))
            return True
        except sqlite3.IntegrityError:
            # Código de barras duplicado
            return False
        except Exception as e:
            print(f"Error guardando código: {e}")
            return False
    
    def obtener_producto_por_id(self, id_producto):
        """
        Obtiene datos del producto por ID.
        
        Args:
            id_producto: ID del producto
        
        Returns:
            Diccionario con datos del producto
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT id, nombre, precio, stock, codigo_barras 
                    FROM inventario 
                    WHERE id = ?
                """, (id_producto,)).fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'precio': row[2],
                    'stock': row[3],
                    'codigo_barras': row[4]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo producto: {e}")
            return None
    
    def listar_productos_sin_codigo(self):
        """
        Lista todos los productos que no tienen código de barras asignado.
        
        Returns:
            Lista de tuplas (id, nombre, código_actual)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                productos = conn.execute("""
                    SELECT id, nombre, codigo_barras 
                    FROM inventario 
                    WHERE codigo_barras IS NULL OR codigo_barras = ''
                    ORDER BY nombre
                """).fetchall()
            return productos
        except Exception as e:
            print(f"Error listando productos: {e}")
            return []


class DialogoAsignarCodigoBarras(tk.Toplevel):
    """
    Diálogo para asignar códigos de barras a productos.
    """
    
    def __init__(self, parent, id_producto, nombre_producto, escaner):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre
            id_producto: ID del producto
            nombre_producto: Nombre del producto
            escaner: Instancia de EscanerCodigoBarras
        """
        super().__init__(parent)
        self.title("Asignar Código de Barras")
        self.geometry("400x250")
        self.resizable(False, False)
        
        self.id_producto = id_producto
        self.nombre_producto = nombre_producto
        self.escaner = escaner
        self.codigo_asignado = False
        
        # Frame principal
        frame = tk.Frame(self, bg="#C5D9E3")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Título
        titulo = tk.Label(
            frame,
            text=f"Asignar Código de Barras",
            bg="#C5D9E3",
            font="sans 14 bold"
        )
        titulo.pack(pady=10)
        
        # Información del producto
        info = tk.Label(
            frame,
            text=f"Producto: {nombre_producto}",
            bg="#C5D9E3",
            font="sans 11",
            wraplength=350
        )
        info.pack(pady=5)
        
        # Instrucción
        instruccion = tk.Label(
            frame,
            text="Escanee el código de barras o ingreselo manualmente:",
            bg="#C5D9E3",
            font="sans 10"
        )
        instruccion.pack(pady=10)
        
        # Campo de entrada
        self.entry_codigo = tk.Entry(frame, font="sans 12 bold", width=30)
        self.entry_codigo.pack(pady=10, ipady=5)
        self.entry_codigo.focus()
        self.entry_codigo.bind("<Return>", lambda e: self._guardar_codigo())
        
        # Botones
        frame_botones = tk.Frame(frame, bg="#C5D9E3")
        frame_botones.pack(pady=15)
        
        btn_guardar = tk.Button(
            frame_botones,
            text="Guardar",
            bg="#27AE60",
            fg="white",
            font="sans 10 bold",
            command=self._guardar_codigo
        )
        btn_guardar.pack(side="left", padx=5)
        
        btn_cancelar = tk.Button(
            frame_botones,
            text="Cancelar",
            bg="#C0392B",
            fg="white",
            font="sans 10 bold",
            command=self.destroy
        )
        btn_cancelar.pack(side="left", padx=5)
        
        # Hacer modal
        self.transient(parent)
        self.grab_set()
    
    def _guardar_codigo(self):
        """Guarda el código de barras"""
        codigo = self.entry_codigo.get().strip()
        
        if not codigo:
            messagebox.showerror("Error", "Ingrese un código de barras")
            return
        
        if self.escaner.guardar_codigo_barras(self.id_producto, codigo):
            messagebox.showinfo(
                "Exito",
                f"Código de barras asignado correctamente:\n{codigo}"
            )
            self.codigo_asignado = True
            self.destroy()
        else:
            messagebox.showerror(
                "Error",
                "Este código de barras ya está asignado a otro producto"
            )
            self.entry_codigo.delete(0, "end")
            self.entry_codigo.focus()
