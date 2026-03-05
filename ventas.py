import sqlite3
from tkinter import *
from tkinter import ttk, messagebox
import tkinter as tk
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import datetime
import sys
import os

def get_db_path():
    if getattr(sys, 'frozen', False):
        # Ejecutando como .exe compilado
        base_dir = os.path.dirname(sys.executable)
    else:
        # Ejecutando como script .py normal
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "database.db")
class Ventas(tk.Frame):
    db_name = get_db_path()
    
    def __init__(self, parent):
        super().__init__(parent)
        self.crear_tabla_ventas()
        self.numero_factura_actual = self.obtener_numero_factura_actual()
        self.widgets()
        self.mostrar_numero_factura()
    
    def crear_tabla_ventas(self):
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ventas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        factura INTEGER NOT NULL,
                        nombre_articulo TEXT NOT NULL,
                        valor_articulo REAL NOT NULL,
                        cantidad INTEGER NOT NULL,
                        subtotal REAL NOT NULL,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo crear la tabla ventas: {e}")
    
    def widgets(self):
        frame1 = tk.Frame(self, bg="#dddddd", highlightbackground="gray", highlightthickness=3)
        frame1.pack()
        frame1.place(x=0, y=0, width=1100, height=100)
        titulo = tk.Label(self, text="VENTAS", bg="#dddddd", font="sans 30 bold", anchor="center")
        titulo.pack()
        titulo.place(x=5, y=0, width=1090, height=90)
        
        frame2 = tk.Frame(self, bg="#C6D9E3", highlightbackground="gray", highlightthickness=3)
        frame2.place(x=0, y=100, width=1100, height=550)
        
        lblframe = LabelFrame(frame2, text="Información de la venta", bg="#C6D9E3", font="sans 16 bold")
        lblframe.place(x=10, y=10, width=1060, height=95)
        
        nFactura = tk.Label(lblframe, text="Numero de factura", bg="#C6D9E3", font="sans 14 bold")
        nFactura.place(x=10, y=5)
        
        self.numero_factura = tk.StringVar()
        self.entry_numero_factura = ttk.Entry(lblframe, textvariable=self.numero_factura, state="readonly", font="sans 12 bold")
        self.entry_numero_factura.place(x=130, y=5, width=100)
        
        label_nombre = tk.Label(lblframe, text="Productos: ", bg="#C6D9E3", font="sans 14 bold")
        label_nombre.place(x=240, y=12)
        
        self.entry_nombre = ttk.Combobox(lblframe, font="sans 14 bold", state="readonly")
        self.entry_nombre.place(x=360, y=10, width=180)
        self.cargar_productos()
        
        label_valor = tk.Label(lblframe, text="Precio: ", bg="#C6D9E3", font="sans 14 bold")
        label_valor.place(x=550, y=12)
        
        self.entry_valor = ttk.Entry(lblframe, font="sans 14 bold", state="readonly")
        self.entry_valor.place(x=630, y=10, width=180)
        
        self.entry_nombre.bind("<<ComboboxSelected>>", self.actualizar_precio)
        
        label_cantidad = tk.Label(lblframe, text="Cantidad: ", bg="#C6D9E3", font="sans 14 bold")
        label_cantidad.place(x=820, y=12)
        
        self.entry_cantidad = ttk.Entry(lblframe, font="sans 14 bold")
        self.entry_cantidad.place(x=920, y=10)
        
        treFrame = tk.Frame(frame2, bg="#C6D9E3")
        treFrame.place(x=150, y=120, width=800, height=200)
        
        scrol_y = ttk.Scrollbar(treFrame, orient=VERTICAL)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_x = ttk.Scrollbar(treFrame, orient=HORIZONTAL)
        scrol_x.pack(side=BOTTOM, fill=X)
        
        self.tree = ttk.Treeview(treFrame, columns=("producto", "Precio", "Cantidad", "Subtotal"), show="headings", height=10, yscrollcommand=scrol_y.set, xscrollcommand=scrol_x.set)
        scrol_y.config(command=self.tree.yview)
        scrol_x.config(command=self.tree.xview)
        
        self.tree.heading("producto", text="Producto")
        self.tree.heading("Precio", text="Precio")
        self.tree.heading("Cantidad", text="Cantidad")
        self.tree.heading("Subtotal", text="Subtotal")
        
        self.tree.column("producto", anchor="center")
        self.tree.column("Precio", anchor="center")
        self.tree.column("Cantidad", anchor="center")
        self.tree.column("Subtotal", anchor="center")
        
        self.tree.pack(expand=True, fill=BOTH)
        
        lblframe1 = LabelFrame(frame2, text="Opciones", bg="#C6D9E3", font="sans 14 bold")
        lblframe1.place(x=10, y=380, width=1060, height=100)
        
        boton_agregar = tk.Button(lblframe1, text="Agregar artículo", bg="#000CFF", fg="white", font="sans 14 bold", command=self.registrar)
        boton_agregar.place(x=50, y=10, width=240, height=50)
        
        boton_pagar = tk.Button(lblframe1, text="Pagar", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_paga)
        boton_pagar.place(x=400, y=10, width=240, height=50)
        
        boton_ver_factura = tk.Button(lblframe1, text="Ver Factura", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_factura)
        boton_ver_factura.place(x=750, y=10, width=240, height=50)
        
        self.label_suma_total = tk.Label(frame2, text="Total a pagar: 0 €", bg="#C6D9E3", font="sans 25 bold")
        self.label_suma_total.place(x=360, y=335)
    
    def cargar_productos(self):
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT nombre FROM inventario")
                resultados = cursor.fetchall()
                nombres = [producto[0] for producto in resultados]
                self.entry_nombre["values"] = nombres
                if not nombres:
                    print("Advertencia: La base de datos no contiene productos registrados")
        except sqlite3.Error as e:
            print(f"Error al cargar productos desde la base de datos: {e}")
        except Exception as ex:
            print(f"Error inesperado: {ex}")
    
    def actualizar_precio(self, event):
        nombre_producto = self.entry_nombre.get()
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT precio FROM inventario WHERE nombre = ?", (nombre_producto,))
            precio = c.fetchone()
            if precio:
                self.entry_valor.config(state="normal")
                self.entry_valor.delete(0, tk.END)
                self.entry_valor.insert(0, precio[0])
                self.entry_valor.config(state="readonly")
            else:
                self.entry_valor.config(state="normal")
                self.entry_valor.delete(0, tk.END)
                self.entry_valor.insert(0, "Precio no disponible")
                self.entry_valor.config(state="readonly")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al obtener el precio: {e}")
        finally:
            if conn:
                conn.close()
    
    def actualizar_total(self):
        total = 0.0
        for child in self.tree.get_children():
            subtotal = float(self.tree.item(child, "values")[3])
            total += subtotal
        self.label_suma_total.config(text=f"Total a pagar: {total:.0f} €")
    
    def registrar(self):
        producto = self.entry_nombre.get().strip()
        precio_str = self.entry_valor.get().strip()
        cantidad_str = self.entry_cantidad.get().strip()
        
        if not all([producto, precio_str, cantidad_str]):
            messagebox.showerror("Error", "Debe completar todos los campos")
            return
        
        try:
            cantidad = int(cantidad_str)
            precio = float(precio_str)
            
            if not self.validar_stock(producto, cantidad):
                messagebox.showerror("Error", "Stock insuficiente para el producto seleccionado")
                return
            
            subtotal = cantidad * precio
            self.tree.insert("", "end", values=(producto, f"{precio:.0f}", cantidad, f"{subtotal:.0f}"))
            
            self.entry_nombre.set("")
            self.entry_valor.config(state="normal")
            self.entry_valor.delete(0, tk.END)
            self.entry_valor.config(state="readonly")
            self.entry_cantidad.delete(0, tk.END)
            
            self.actualizar_total()
        except ValueError:
            messagebox.showerror("Error", "Cantidad o precio no válidos. Asegúrese de ingresar números válidos")
    
    def validar_stock(self, nombre_producto, cantidad):
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT stock FROM inventario WHERE nombre = ?", (nombre_producto,))
            stock = c.fetchone()
            if stock and stock[0] >= cantidad:
                return True
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al validar el stock: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def obtener_total(self):
        total = 0.0
        for child in self.tree.get_children():
            subtotal = float(self.tree.item(child, "values")[3])
            total += subtotal
        return total
    
    def abrir_ventana_paga(self):
        if not self.tree.get_children():
            messagebox.showerror("Error", "No hay artículos para pagar")
            return
        
        ventana_pago = tk.Toplevel(self)
        ventana_pago.title("Realizar pago")
        ventana_pago.geometry("400x400")
        ventana_pago.config(bg="#C5D9E3")
        ventana_pago.resizable(False, False)
        
        label_total = tk.Label(ventana_pago, bg="#C6D9E3", text=f"Total a pagar: {self.obtener_total():.0f} €", font="sans 18 bold")
        label_total.place(x=70, y=20)
        
        label_cantidad_pagada = tk.Label(ventana_pago, bg="#C6D9E3", text="Cantidad pagada:", font="sans 14 bold")
        label_cantidad_pagada.place(x=100, y=90)
        
        entry_cantidad_pagada = ttk.Entry(ventana_pago, font="sans 14 bold")
        entry_cantidad_pagada.place(x=100, y=130)
        
        label_cambio = tk.Label(ventana_pago, bg="#C6D9E3", text="", font="sans 14 bold")
        label_cambio.place(x=100, y=190)
        
        def calcular_cambio():
            try:
                cantidad_pagada = float(entry_cantidad_pagada.get())
                total = self.obtener_total()
                cambio = cantidad_pagada - total
                if cambio < 0:
                    messagebox.showerror("Error", "Cantidad insuficiente")
                    return
                label_cambio.config(text=f"Vuelto: {cambio:.0f} €")
            except ValueError:
                messagebox.showerror("Error", "Cantidad no válida")
        
        boton_calcular = tk.Button(ventana_pago, text="Calcular vuelto", font="sans 12 bold", command=calcular_cambio)
        boton_calcular.place(x=100, y=240, width=240, height=40)
        
        boton_pagar = tk.Button(ventana_pago, text="Pagar", font="sans 12 bold", command=lambda: self.pagar(ventana_pago, entry_cantidad_pagada, label_cambio))
        boton_pagar.place(x=100, y=300, width=240, height=40)
    
    def pagar(self, ventana_pago, entry_cantidad_pagada, label_cambio):
        try:
            cantidad_pagada = float(entry_cantidad_pagada.get())
            total = self.obtener_total()
            cambio = cantidad_pagada - total
            if cambio < 0:
                messagebox.showerror("Error", "La cantidad pagada es insuficiente")
                return
            
            with sqlite3.connect(self.db_name) as conn:
                c = conn.cursor()
                productos = []
                
                for i in self.tree.get_children():
                    item = self.tree.item(i, "values")
                    producto = item[0]
                    precio = item[1]
                    cantidad_vendida = int(item[2])
                    subtotal = float(item[3])
                    productos.append((producto, precio, cantidad_vendida, subtotal))
                    
                    c.execute("""
                        INSERT INTO ventas (
                            factura, nombre_articulo, valor_articulo, cantidad, subtotal
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (self.numero_factura_actual, producto, float(precio), cantidad_vendida, subtotal))
                    
                    c.execute("UPDATE inventario SET stock = stock - ? WHERE nombre = ?", (cantidad_vendida, producto))
                
                conn.commit()
                messagebox.showinfo("Éxito", "La venta se ha completado")
                self.numero_factura_actual += 1
                self.mostrar_numero_factura()
                
                for i in self.tree.get_children():
                    self.tree.delete(i)
                self.label_suma_total.config(text="Total a pagar: 0 €")
                ventana_pago.destroy()
                
                fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                self.generar_factura_pdf(productos, total, self.numero_factura_actual, fecha)
        except ValueError:
            messagebox.showerror("Error", "Cantidad pagada no válida")
    
    def generar_factura_pdf(self, productos, total, factura_numero, fecha):
        if not os.path.exists("facturas"):
            os.makedirs("facturas")
        
        archivo_pdf = f"facturas/factura_{factura_numero}.pdf"
        c = canvas.Canvas(archivo_pdf, pagesize=letter)
        width, height = letter
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, f"Factura #{factura_numero}")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 70, f"Fecha: {fecha}")
        
        data = [["Producto", "Precio", "Cantidad", "Subtotal"]] + [[p[0], p[1], p[2], p[3]] for p in productos]
        table = Table(data)
        table.wrapOn(c, width, height)
        table.drawOn(c, 100, height - 200)
        
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 250, f"Total a pagar: {total:.0f} €")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 370, "Gracias por su compra, vuelva pronto")
        
        c.save()
        
        try:
            os.startfile(os.path.abspath(archivo_pdf))
        except Exception:
            messagebox.showinfo("Factura generada", f"La factura #{factura_numero} ha sido creada exitosamente en:\n{os.path.abspath(archivo_pdf)}")
    
    def obtener_numero_factura_actual(self):
        try:
            with sqlite3.connect(self.db_name) as conn:
                c = conn.cursor()
                c.execute("SELECT IFNULL(MAX(factura), 0) FROM ventas")
                max_factura = c.fetchone()[0]
                return max_factura + 1
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al obtener el número de factura: {e}")
            return 1
    
    def mostrar_numero_factura(self):
        self.numero_factura.set(self.numero_factura_actual)
    
    def abrir_ventana_factura(self):
        ventana_facturas = tk.Toplevel(self)
        ventana_facturas.title("Facturas")
        ventana_facturas.geometry("800x500")
        ventana_facturas.config(bg="#C6D9E3")
        ventana_facturas.resizable(False, False)
        
        facturas_label = tk.Label(ventana_facturas, bg="#C6D9E3", text="Facturas registradas", font="sans 36 bold")
        facturas_label.place(x=150, y=15)
        
        treFrame = tk.Frame(ventana_facturas, bg="#C6D9E3")
        treFrame.place(x=10, y=100, width=780, height=380)
        
        scrol_y = ttk.Scrollbar(treFrame, orient=VERTICAL)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_x = ttk.Scrollbar(treFrame, orient=HORIZONTAL)
        scrol_x.pack(side=BOTTOM, fill=X)
        
        tree_facturas = ttk.Treeview(treFrame, columns=("ID", "Factura", "Producto", "Precio", "Cantidad", "Subtotal"), show="headings", height=10, yscrollcommand=scrol_y.set, xscrollcommand=scrol_x.set)
        scrol_y.config(command=tree_facturas.yview)
        scrol_x.config(command=tree_facturas.xview)
        
        tree_facturas.heading("ID", text="ID")
        tree_facturas.heading("Factura", text="Factura")
        tree_facturas.heading("Producto", text="Producto")
        tree_facturas.heading("Precio", text="Precio")
        tree_facturas.heading("Cantidad", text="Cantidad")
        tree_facturas.heading("Subtotal", text="Subtotal")
        
        tree_facturas.column("ID", width=70, anchor="center")
        tree_facturas.column("Factura", width=100, anchor="center")
        tree_facturas.column("Producto", width=200, anchor="center")
        tree_facturas.column("Precio", width=130, anchor="center")
        tree_facturas.column("Cantidad", width=130, anchor="center")
        tree_facturas.column("Subtotal", width=130, anchor="center")
        
        tree_facturas.pack(expand=True, fill=BOTH)
        self.cargar_facturas(tree_facturas)
    
    def cargar_facturas(self, tree):
        try:
            with sqlite3.connect(self.db_name) as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM ventas")
                facturas = c.fetchall()
                for factura in facturas:
                    tree.insert("", "end", values=factura)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error al cargar las facturas: {e}")