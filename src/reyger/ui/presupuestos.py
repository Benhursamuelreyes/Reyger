"""
Módulo de presupuestos para la aplicación de caja registradora.
Permite crear, gestionar y generar presupuestos en formato PDF.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from ..config import ConfigManager
from . import business_profile as bp
from ..core import db
from ..core.hilos import en_hilo
from ..resources import get_output_path, open_file


class Presupuestos(tk.Frame):
    """
    Ventana para gestión de presupuestos.
    """
    
    def __init__(self, parent, usuario=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.pack(fill="both", expand=True)
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        
        self.presupuesto_id_actual = None
        self.productos_presupuesto = []
        self.tipo_iva_actual = 21
        
        self.crear_tabla_presupuestos()
        self.widgets()
        self.cargar_lista_presupuestos()
    
    def crear_tabla_presupuestos(self):
        """Crea las tablas de presupuestos en la BD"""
        try:
            conn = db.get_connection()
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS presupuestos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_presupuesto TEXT UNIQUE NOT NULL,
                    cliente_nombre TEXT NOT NULL,
                    cliente_email TEXT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    base_imponible REAL DEFAULT 0,
                    tipo_iva INTEGER DEFAULT 21,
                    total_iva REAL DEFAULT 0,
                    total REAL DEFAULT 0,
                    estado TEXT DEFAULT 'Pendiente',
                    notas TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS presupuestos_productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    presupuesto_id INTEGER NOT NULL,
                    nombre_producto TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio_unitario REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    FOREIGN KEY(presupuesto_id) REFERENCES presupuestos(id)
                )
            """)
            
            conn.commit()
        except Exception as e:
            messagebox.showerror("Error", f"Error creando tablas: {e}")
    
    def widgets(self):
        """Crea los widgets de la ventana"""
        
        # Frame superior con título (alto dinámico según la fuente elegida)
        frame_titulo = tk.Frame(self, bg="#0078D4")
        frame_titulo.pack(fill="x")
        
        titulo = tk.Label(
            frame_titulo,
            text="📝 PRESUPUESTOS",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold"
        )
        titulo.pack(pady=14)
        
        # Frame principal dividido en dos: Arriba (entrada) y Abajo (lista)
        # PARTE SUPERIOR: Datos del presupuesto
        frame_superior = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_superior.pack(fill="x", padx=20, pady=20)
        
        # Datos del cliente
        frame_cliente = tk.LabelFrame(
            frame_superior,
            text="Datos del Cliente",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans 12 bold",
            padx=10,
            pady=10
        )
        frame_cliente.pack(fill="x", pady=10)
        
        tk.Label(frame_cliente, text="Nombre:", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold").pack(side="left", padx=5)
        self.entry_cliente = ttk.Entry(frame_cliente, font="sans 10", width=30)
        self.entry_cliente.pack(side="left", padx=5)
        
        tk.Label(frame_cliente, text="Email:", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold").pack(side="left", padx=5)
        self.entry_email = ttk.Entry(frame_cliente, font="sans 10", width=25)
        self.entry_email.pack(side="left", padx=5)
        
        # Productos del presupuesto
        frame_productos = tk.LabelFrame(
            frame_superior,
            text="Agregar Productos",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans 12 bold",
            padx=10,
            pady=10
        )
        frame_productos.pack(fill="x", pady=10)
        
        tk.Label(frame_productos, text="Producto:", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold").pack(side="left", padx=5)
        self.combo_productos = ttk.Combobox(frame_productos, font="sans 10", width=20, state="readonly")
        self.combo_productos.pack(side="left", padx=5)
        self.cargar_productos_combo()
        self.combo_productos.bind("<<ComboboxSelected>>", lambda e: self.actualizar_precio_producto())
        
        tk.Label(frame_productos, text="Precio de venta:", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold").pack(side="left", padx=5)
        self.entry_precio = ttk.Entry(frame_productos, font="sans 10", width=10, state="readonly")
        self.entry_precio.pack(side="left", padx=5)
        
        tk.Label(frame_productos, text="Cantidad:", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold").pack(side="left", padx=5)
        self.entry_cantidad_prod = ttk.Entry(frame_productos, font="sans 10", width=10)
        self.entry_cantidad_prod.pack(side="left", padx=5)
        
        btn_agregar = tk.Button(
            frame_productos,
            text="Agregar",
            bg="#0078D4",
            fg="white",
            font="sans 10 bold",
            command=self.agregar_producto_presupuesto
        )
        btn_agregar.pack(side="left", padx=5)
        
        # IVA selector
        frame_iva = tk.LabelFrame(
            frame_superior,
            text="IVA",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans 12 bold",
            padx=10,
            pady=10
        )
        frame_iva.pack(fill="x", pady=10)
        
        self.var_iva = tk.IntVar(value=21)
        for iva in [4, 10, 21]:
            tk.Radiobutton(
                frame_iva,
                text=f"{iva}%",
                variable=self.var_iva,
                value=iva,
                bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"],
                font="sans 10 bold",
                command=self.recalcular_totales
            ).pack(side="left", padx=10)
        
        # Tabla de productos agregados
        frame_tabla = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_tabla.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        scrollbar_x = ttk.Scrollbar(frame_tabla, orient="horizontal")
        scrollbar_x.pack(side="bottom", fill="x")
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=("Producto", "Cantidad", "Precio", "Subtotal"),
            show="headings",
            height=8,
            yscrollcommand=scrollbar.set,
            xscrollcommand=scrollbar_x.set
        )
        scrollbar.config(command=self.tree.yview)
        scrollbar_x.config(command=self.tree.xview)
        
        self.tree.heading("Producto", text="Producto")
        self.tree.heading("Cantidad", text="Cantidad")
        self.tree.heading("Precio", text="Precio Unitario")
        self.tree.heading("Subtotal", text="Subtotal")
        
        self.tree.column("Producto", width=400)
        self.tree.column("Cantidad", width=80)
        self.tree.column("Precio", width=100)
        self.tree.column("Subtotal", width=100)
        
        self.tree.pack(fill="both", expand=True)
        
        # Frame de totales y botones
        frame_botones = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_botones.pack(fill="x", padx=20, pady=(0, 20))
        
        # Totales
        frame_total = tk.LabelFrame(
            frame_botones,
            text="Totales",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans 12 bold",
            padx=10,
            pady=10
        )
        frame_total.pack(fill="x", pady=10)
        
        self.label_base = tk.Label(frame_total, text="Base Imponible: 0.00 €", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold")
        self.label_base.pack(anchor="e", padx=10)
        
        self.label_iva_total = tk.Label(frame_total, text="IVA: 0.00 €", bg=self.colors["bg_principal"], fg=self.colors["fg_texto"], font="sans 10 bold")
        self.label_iva_total.pack(anchor="e", padx=10)
        
        self.label_total_presupuesto = tk.Label(frame_total, text="TOTAL: 0.00 €", bg=self.colors["bg_principal"], fg="#27AE60", font="sans 14 bold")
        self.label_total_presupuesto.pack(anchor="e", padx=10)
        
        # Botones de acción
        frame_acciones = tk.Frame(frame_botones, bg=self.colors["bg_principal"])
        frame_acciones.pack(fill="x", pady=10)
        
        tk.Button(
            frame_acciones,
            text="Guardar Presupuesto",
            bg="#27AE60",
            fg="white",
            font="sans 10 bold",
            command=self.guardar_presupuesto
        ).pack(side="left", padx=5)
        
        tk.Button(
            frame_acciones,
            text="Generar PDF",
            bg="#F39C12",
            fg="white",
            font="sans 10 bold",
            command=self.generar_pdf_presupuesto
        ).pack(side="left", padx=5)

        tk.Button(
            frame_acciones,
            text="Imprimir",
            bg="#0078D4",
            fg="white",
            font="sans 10 bold",
            command=self._imprimir_presupuesto,
        ).pack(side="left", padx=5)

        tk.Button(
            frame_acciones,
            text="Limpiar",
            bg="#95A5A6",
            fg="white",
            font="sans 10 bold",
            command=self.limpiar_presupuesto
        ).pack(side="left", padx=5)
    
    def cargar_productos_combo(self):
        """Carga los productos del inventario en el combobox"""
        try:
            filas = db.query("SELECT nombre FROM inventario ORDER BY nombre")
            productos = [fila["nombre"] for fila in filas]
            self.combo_productos["values"] = productos
        except Exception:
            pass
    
    def actualizar_precio_producto(self):
        """Actualiza el precio cuando se selecciona un producto"""
        producto = self.combo_productos.get()
        if not producto:
            return
        
        try:
            fila = db.query_one("SELECT precio FROM inventario WHERE nombre = ?", (producto,))
            
            if fila:
                self.entry_precio.config(state="normal")
                self.entry_precio.delete(0, "end")
                self.entry_precio.insert(0, str(fila["precio"]))
                self.entry_precio.config(state="readonly")
        except Exception:
            pass
    
    def agregar_producto_presupuesto(self):
        """Agrega un producto al presupuesto"""
        producto = self.combo_productos.get().strip()
        precio_str = self.entry_precio.get().strip()
        cantidad_str = self.entry_cantidad_prod.get().strip()
        
        if not all([producto, precio_str, cantidad_str]):
            messagebox.showerror("Error", "Complete todos los campos")
            return
        
        try:
            precio = float(precio_str)
            cantidad = int(cantidad_str)
            subtotal = precio * cantidad
            
            self.tree.insert("", "end", values=(producto, cantidad, f"{precio:.2f}", f"{subtotal:.2f}"))
            self.productos_presupuesto.append({
                'nombre': producto,
                'cantidad': cantidad,
                'precio': precio,
                'subtotal': subtotal
            })
            
            self.combo_productos.set("")
            self.entry_precio.config(state="normal")
            self.entry_precio.delete(0, "end")
            self.entry_precio.config(state="readonly")
            self.entry_cantidad_prod.delete(0, "end")
            
            self.recalcular_totales()
        except ValueError:
            messagebox.showerror("Error", "Valores no validos")
    
    def recalcular_totales(self):
        """Recalcula los totales del presupuesto"""
        base_imponible = 0.0
        for child in self.tree.get_children():
            subtotal = float(self.tree.item(child, "values")[3])
            base_imponible += subtotal
        
        tipo_iva = self.var_iva.get()
        total_iva = base_imponible * (tipo_iva / 100)
        total = base_imponible + total_iva
        
        self.label_base.config(text=f"Base Imponible: {base_imponible:.2f} €")
        self.label_iva_total.config(text=f"IVA ({tipo_iva}%): {total_iva:.2f} €")
        self.label_total_presupuesto.config(text=f"TOTAL: {total:.2f} €")
        
        self.tipo_iva_actual = tipo_iva
    
    def guardar_presupuesto(self):
        """Guarda el presupuesto en la BD"""
        cliente = self.entry_cliente.get().strip()
        if not cliente:
            messagebox.showerror("Error", "Ingrese el nombre del cliente")
            return
        
        if not self.tree.get_children():
            messagebox.showerror("Error", "Agregue productos al presupuesto")
            return
        
        try:
            base_imponible = 0.0
            for child in self.tree.get_children():
                subtotal = float(self.tree.item(child, "values")[3])
                base_imponible += subtotal
            
            tipo_iva = self.var_iva.get()
            total_iva = base_imponible * (tipo_iva / 100)
            total = base_imponible + total_iva
            
            with db.transaccion() as conn:
                numero_temp = f"PRE-TEMP-{datetime.now().timestamp()}"
                cursor = conn.execute("""
                    INSERT INTO presupuestos
                    (numero_presupuesto, cliente_nombre, cliente_email, base_imponible, 
                     tipo_iva, total_iva, total, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_temp, cliente, self.entry_email.get(), base_imponible,
                      tipo_iva, total_iva, total, "Pendiente"))
                
                presupuesto_id = cursor.lastrowid
                numero_presupuesto = f"PRE-{datetime.now().strftime('%Y')}-{presupuesto_id:05d}"
                conn.execute("UPDATE presupuestos SET numero_presupuesto = ? WHERE id = ?",
                           (numero_presupuesto, presupuesto_id))
                
                for child in self.tree.get_children():
                    valores = self.tree.item(child, "values")
                    conn.execute("""
                        INSERT INTO presupuestos_productos
                        (presupuesto_id, nombre_producto, cantidad, precio_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (presupuesto_id, valores[0], int(valores[1]), 
                          float(valores[2]), float(valores[3])))
            
            messagebox.showinfo("Exito", f"Presupuesto {numero_presupuesto} guardado correctamente")
            self.limpiar_presupuesto()
            self.cargar_lista_presupuestos()
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando presupuesto: {e}")
    
    def generar_pdf_presupuesto(self):
        """Genera un PDF del presupuesto con membrete de la empresa."""
        cliente = self.entry_cliente.get().strip()
        if not cliente or not self.tree.get_children():
            messagebox.showerror("Error", "Complete el presupuesto primero")
            return

        try:
            presupuestos_dir = get_output_path("presupuestos_pdf")
            archivo_pdf = os.path.join(
                presupuestos_dir,
                f"Presupuesto_{cliente}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

            doc = SimpleDocTemplate(
                archivo_pdf, pagesize=A4,
                rightMargin=1.5 * cm, leftMargin=1.5 * cm,
            )
            story = []
            estilos = getSampleStyleSheet()

            estilo_titulo = ParagraphStyle(
                "PresupuestoTitle",
                parent=estilos["Heading1"],
                fontSize=20,
                textColor=colors.HexColor("#0078D4"),
                spaceAfter=10,
                alignment=1,
                fontName="Helvetica-Bold",
            )
            estilo_empresa = ParagraphStyle(
                "PresupuestoEmpresa",
                parent=estilos["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#555555"),
                alignment=1,
                spaceAfter=4,
            )

            # Membrete dinámico
            nombre = bp.nombre_empresa()
            story.append(Paragraph(f"<b>{nombre.upper()}</b>", estilo_titulo))

            perfil = bp.obtener()
            if perfil:
                p = dict(perfil)
                lineas = []
                if p.get("nif"):
                    lineas.append(f"NIF: {p['nif']}")
                if p.get("direccion"):
                    d = p["direccion"]
                    if p.get("codigo_postal"):
                        d += f", {p['codigo_postal']}"
                    if p.get("provincia"):
                        d += f" — {p['provincia']}"
                    lineas.append(d)
                if p.get("telefono"):
                    lineas.append(f"Tel: {p['telefono']}")
                if p.get("email"):
                    lineas.append(f"Email: {p['email']}")
                if lineas:
                    story.append(Paragraph(" | ".join(lineas), estilo_empresa))

            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("<b>PRESUPUESTO</b>", estilos["Heading2"]))
            story.append(Spacer(1, 0.3 * cm))

            # Datos del cliente
            email = self.entry_email.get().strip()
            story.append(Paragraph(f"<b>Cliente:</b> {cliente}", estilos["Normal"]))
            if email:
                story.append(Paragraph(f"<b>Email:</b> {email}", estilos["Normal"]))
            story.append(Paragraph(
                f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')}",
                estilos["Normal"],
            ))
            story.append(Spacer(1, 0.5 * cm))

            # Tabla de productos
            datos = [["Producto", "Cantidad", "P. Unitario", "Subtotal"]]
            for child in self.tree.get_children():
                v = self.tree.item(child, "values")
                datos.append([
                    v[0], v[1],
                    f"{float(v[2]):.2f} €",
                    f"{float(v[3]):.2f} €",
                ])

            tabla = Table(datos, colWidths=[6 * cm, 2.5 * cm, 3 * cm, 3 * cm])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0078D4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(tabla)
            story.append(Spacer(1, 0.5 * cm))

            # Totales
            base = sum(
                float(self.tree.item(c, "values")[3])
                for c in self.tree.get_children()
            )
            iva = base * (self.var_iva.get() / 100)
            total = base + iva

            story.append(Paragraph(
                f"<b>Base Imponible:</b> {base:.2f} €", estilos["Normal"]
            ))
            story.append(Paragraph(
                f"<b>IVA ({self.var_iva.get()}%):</b> {iva:.2f} €",
                estilos["Normal"],
            ))
            story.append(Paragraph(
                f"<b>TOTAL:</b> {total:.2f} €", estilos["Heading2"]
            ))

            doc.build(story)
            messagebox.showinfo("Éxito", f"PDF generado en:\n{archivo_pdf}")

            try:
                open_file(os.path.abspath(archivo_pdf))
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Error generando PDF: {e}")

    def _imprimir_presupuesto(self):
        """Imprime el presupuesto en la impresora predeterminada del sistema."""
        cliente = self.entry_cliente.get().strip()
        if not cliente or not self.tree.get_children():
            messagebox.showerror("Error", "Complete el presupuesto primero")
            return

        try:
            import tempfile
            presupuestos_dir = get_output_path("presupuestos_pdf")
            archivo_tmp = os.path.join(
                presupuestos_dir,
                f"_impresion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            doc = SimpleDocTemplate(
                archivo_tmp, pagesize=A4,
                rightMargin=1.5 * cm, leftMargin=1.5 * cm,
            )
            story = []
            estilos = getSampleStyleSheet()

            estilo_titulo = ParagraphStyle(
                "PresupTitle",
                parent=estilos["Heading1"],
                fontSize=20,
                textColor=colors.HexColor("#0078D4"),
                spaceAfter=10,
                alignment=1,
                fontName="Helvetica-Bold",
            )
            estilo_empresa = ParagraphStyle(
                "PresupEmpresa",
                parent=estilos["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#555555"),
                alignment=1,
                spaceAfter=4,
            )

            nombre = bp.nombre_empresa()
            story.append(Paragraph(f"<b>{nombre.upper()}</b>", estilo_titulo))

            perfil = bp.obtener()
            if perfil:
                p = dict(perfil)
                lineas = []
                if p.get("nif"):
                    lineas.append(f"NIF: {p['nif']}")
                if p.get("direccion"):
                    d = p["direccion"]
                    if p.get("codigo_postal"):
                        d += f", {p['codigo_postal']}"
                    if p.get("provincia"):
                        d += f" — {p['provincia']}"
                    lineas.append(d)
                if p.get("telefono"):
                    lineas.append(f"Tel: {p['telefono']}")
                if p.get("email"):
                    lineas.append(f"Email: {p['email']}")
                if lineas:
                    story.append(Paragraph(" | ".join(lineas), estilo_empresa))

            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("<b>PRESUPUESTO</b>", estilos["Heading2"]))
            story.append(Spacer(1, 0.3 * cm))

            email = self.entry_email.get().strip()
            story.append(Paragraph(f"<b>Cliente:</b> {cliente}", estilos["Normal"]))
            if email:
                story.append(Paragraph(f"<b>Email:</b> {email}", estilos["Normal"]))
            story.append(Paragraph(
                f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y')}",
                estilos["Normal"],
            ))
            story.append(Spacer(1, 0.5 * cm))

            datos = [["Producto", "Cantidad", "P. Unitario", "Subtotal"]]
            for child in self.tree.get_children():
                v = self.tree.item(child, "values")
                datos.append([
                    v[0], v[1],
                    f"{float(v[2]):.2f} €",
                    f"{float(v[3]):.2f} €",
                ])

            tabla = Table(datos, colWidths=[6 * cm, 2.5 * cm, 3 * cm, 3 * cm])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0078D4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(tabla)
            story.append(Spacer(1, 0.5 * cm))

            base = sum(
                float(self.tree.item(c, "values")[3])
                for c in self.tree.get_children()
            )
            iva = base * (self.var_iva.get() / 100)
            total = base + iva

            story.append(Paragraph(
                f"<b>Base Imponible:</b> {base:.2f} €", estilos["Normal"]
            ))
            story.append(Paragraph(
                f"<b>IVA ({self.var_iva.get()}%):</b> {iva:.2f} €",
                estilos["Normal"],
            ))
            story.append(Paragraph(
                f"<b>TOTAL:</b> {total:.2f} €", estilos["Heading2"]
            ))

            doc.build(story)

            try:
                from ..hardware.impresion_termica import enviar_a_impresora
                ok, msg = enviar_a_impresora(archivo_tmp)
                if not ok:
                    messagebox.showwarning("Impresión", msg)
            except ImportError:
                from ..resources import open_file
                open_file(archivo_tmp)
        except Exception as e:
            messagebox.showerror("Error", f"Error al imprimir: {e}")
    
    def limpiar_presupuesto(self):
        """Limpia el presupuesto actual"""
        self.entry_cliente.delete(0, "end")
        self.entry_email.delete(0, "end")
        self.combo_productos.set("")
        self.entry_precio.config(state="normal")
        self.entry_precio.delete(0, "end")
        self.entry_precio.config(state="readonly")
        self.entry_cantidad_prod.delete(0, "end")
        
        for child in self.tree.get_children():
            self.tree.delete(child)
        
        self.productos_presupuesto = []
        self.var_iva.set(21)
        self.recalcular_totales()
    
    def cargar_lista_presupuestos(self):
        """Carga la lista de presupuestos guardados"""
        # Esto se puede mejorar agregando un widget adicional
        pass
