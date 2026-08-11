import sqlite3
from tkinter import *
from tkinter import ttk, messagebox
import tkinter as tk
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import datetime
import os

from .resources import get_db_path, get_output_path, open_file


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
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ventas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        factura INTEGER NOT NULL,
                        nombre_articulo TEXT NOT NULL,
                        valor_articulo REAL NOT NULL,
                        cantidad INTEGER NOT NULL,
                        subtotal REAL NOT NULL,
                        metodo_pago TEXT DEFAULT 'Efectivo',
                        cantidad_efectivo REAL DEFAULT 0,
                        cantidad_tarjeta REAL DEFAULT 0,
                        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute('ALTER TABLE ventas ADD COLUMN metodo_pago TEXT DEFAULT "Efectivo"')
                except Exception:
                    pass
                try:
                    cursor.execute("ALTER TABLE ventas ADD COLUMN cantidad_efectivo REAL DEFAULT 0")
                except Exception:
                    pass
                try:
                    cursor.execute("ALTER TABLE ventas ADD COLUMN cantidad_tarjeta REAL DEFAULT 0")
                except Exception:
                    pass
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
        lblframe.place(x=10, y=10, width=1060, height=135)

        nFactura = tk.Label(lblframe, text="Num.factura: ", bg="#C6D9E3", font="sans 14 bold")
        nFactura.place(x=10, y=12)

        self.numero_factura = tk.StringVar()
        self.entry_numero_factura = ttk.Entry(lblframe, textvariable=self.numero_factura, state="readonly", font="sans 12 bold")
        self.entry_numero_factura.place(x=130, y=12, width=100)

        label_nombre = tk.Label(lblframe, text="Productos: ", bg="#C6D9E3", font="sans 14 bold")
        label_nombre.place(x=240, y=12)

        self.entry_nombre = ttk.Combobox(lblframe, font="sans 14 bold", state="readonly")
        self.entry_nombre.place(x=360, y=12, width=180)
        self.cargar_productos()

        label_valor = tk.Label(lblframe, text="Precio: ", bg="#C6D9E3", font="sans 14 bold")
        label_valor.place(x=550, y=12)

        self.entry_valor = ttk.Entry(lblframe, font="sans 14 bold", state="readonly")
        self.entry_valor.place(x=630, y=12, width=180)

        self.entry_nombre.bind("<<ComboboxSelected>>", self.actualizar_precio)

        label_cantidad = tk.Label(lblframe, text="Cantidad: ", bg="#C6D9E3", font="sans 14 bold")
        label_cantidad.place(x=820, y=12)

        self.entry_cantidad = ttk.Entry(lblframe, font="sans 14 bold")
        self.entry_cantidad.place(x=920, y=12)

        treFrame = tk.Frame(frame2, bg="#C6D9E3")
        treFrame.place(x=150, y=170, width=800, height=200)

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
        lblframe1.place(x=10, y=430, width=1060, height=100)

        boton_agregar = tk.Button(lblframe1, text="Agregar artículo", bg="#000CFF", fg="white", font="sans 14 bold", command=self.registrar)
        boton_agregar.place(x=50, y=10, width=240, height=50)

        boton_pagar = tk.Button(lblframe1, text="Pagar", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_paga)
        boton_pagar.place(x=400, y=10, width=240, height=50)

        boton_ver_factura = tk.Button(lblframe1, text="Ver Factura", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_factura)
        boton_ver_factura.place(x=750, y=10, width=240, height=50)

        self.label_suma_total = tk.Label(frame2, text="Total a pagar: 0 €", bg="#C6D9E3", font="sans 25 bold")
        self.label_suma_total.place(x=360, y=385)

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
        self.label_suma_total.config(text=f"Total a pagar: {total:.2f} €")

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
            self.tree.insert("", "end", values=(producto, f"{precio:.2f}", cantidad, f"{subtotal:.2f}"))

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

    def _actualizar_campos_pago(self, ventana, var_metodo, label_efe=None, entry_efe=None, label_tar=None, entry_tar=None):
        if label_efe is None:
            return
        metodo = var_metodo.get()
        if metodo == "Efectivo":
            label_efe.place(x=50, y=150)
            entry_efe.place(x=50, y=180, width=400, height=35)
            label_tar.place_forget()
            entry_tar.place_forget()
        elif metodo == "Tarjeta":
            label_efe.place_forget()
            entry_efe.place_forget()
            label_tar.place(x=50, y=150)
            entry_tar.place(x=50, y=180, width=400, height=35)
        else:
            label_efe.place(x=50, y=150)
            entry_efe.place(x=50, y=180, width=400, height=35)
            label_tar.place(x=50, y=230)
            entry_tar.place(x=50, y=260, width=400, height=35)

    def abrir_ventana_paga(self):
        if not self.tree.get_children():
            messagebox.showerror("Error", "No hay artículos para pagar")
            return

        ventana_pago = tk.Toplevel(self)
        ventana_pago.title("Realizar pago")
        ventana_pago.geometry("500x600")
        ventana_pago.config(bg="#C5D9E3")
        ventana_pago.resizable(False, False)

        total = self.obtener_total()
        label_total = tk.Label(ventana_pago, bg="#C6D9E3", text=f"Total a pagar: {total:.2f} €", font="sans 18 bold")
        label_total.place(x=50, y=20)

        label_metodo = tk.Label(ventana_pago, bg="#C6D9E3", text="Método de pago:", font="sans 14 bold")
        label_metodo.place(x=50, y=70)

        var_metodo = tk.StringVar(value="Efectivo")

        def actualizar_campos():
            self._actualizar_campos_pago(ventana_pago, var_metodo, label_efectivo, entry_efectivo, label_tarjeta, entry_tarjeta)

        radio_efectivo = tk.Radiobutton(ventana_pago, text="Efectivo", variable=var_metodo, value="Efectivo", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_efectivo.place(x=50, y=100)

        radio_tarjeta = tk.Radiobutton(ventana_pago, text="Tarjeta", variable=var_metodo, value="Tarjeta", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_tarjeta.place(x=200, y=100)

        radio_mixto = tk.Radiobutton(ventana_pago, text="Mixto", variable=var_metodo, value="Mixto", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_mixto.place(x=320, y=100)

        label_efectivo = tk.Label(ventana_pago, bg="#C6D9E3", text="Cantidad en efectivo:", font="sans 12 bold")
        label_efectivo.place(x=50, y=150)
        entry_efectivo = ttk.Entry(ventana_pago, font="sans 12 bold")
        entry_efectivo.place(x=50, y=180, width=400, height=35)

        label_tarjeta = tk.Label(ventana_pago, bg="#C6D9E3", text="Cantidad en tarjeta:", font="sans 12 bold")
        label_tarjeta.place(x=50, y=230)
        entry_tarjeta = ttk.Entry(ventana_pago, font="sans 12 bold")
        entry_tarjeta.place(x=50, y=260, width=400, height=35)
        label_tarjeta.place_forget()
        entry_tarjeta.place_forget()

        label_cambio = tk.Label(ventana_pago, bg="#C6D9E3", text="", font="sans 14 bold", fg="#27AE60")
        label_cambio.place(x=50, y=320)

        def calcular_cambio():
            try:
                metodo = var_metodo.get()
                if metodo == "Efectivo":
                    cantidad_pagada = float(entry_efectivo.get())
                    cambio = cantidad_pagada - total
                    if cambio < 0:
                        messagebox.showerror("Error", "Cantidad en efectivo insuficiente")
                        label_cambio.config(text="")
                        return
                    label_cambio.config(text=f"Vuelto: {cambio:.2f} €")
                elif metodo == "Tarjeta":
                    cantidad_tarjeta = float(entry_tarjeta.get())
                    if cantidad_tarjeta < total:
                        messagebox.showerror("Error", "Cantidad en tarjeta insuficiente")
                        label_cambio.config(text="")
                        return
                    label_cambio.config(text="Pago con tarjeta registrado")
                elif metodo == "Mixto":
                    cantidad_efectivo = float(entry_efectivo.get())
                    cantidad_tarjeta = float(entry_tarjeta.get())
                    total_pagado = cantidad_efectivo + cantidad_tarjeta
                    if total_pagado < total:
                        messagebox.showerror("Error", "Pago insuficiente (efectivo + tarjeta)")
                        label_cambio.config(text="")
                        return
                    cambio = total_pagado - total
                    label_cambio.config(text=f"Vuelto: {cambio:.2f} € (del efectivo)")
            except ValueError:
                messagebox.showerror("Error", "Ingrese valores numericos validos")

        boton_calcular = tk.Button(ventana_pago, text="Calcular", bg="#0078D4", fg="white", font="sans 12 bold", command=calcular_cambio)
        boton_calcular.place(x=50, y=370, width=400, height=40)

        boton_pagar = tk.Button(ventana_pago, text="Confirmar pago", bg="#27AE60", fg="white", font="sans 14 bold", command=lambda: self.pagar(ventana_pago, entry_efectivo, entry_tarjeta, var_metodo, label_cambio, total))
        boton_pagar.place(x=50, y=430, width=400, height=50)

        boton_cancelar = tk.Button(ventana_pago, text="Cancelar", bg="#C0392B", fg="white", font="sans 12 bold", command=ventana_pago.destroy)
        boton_cancelar.place(x=50, y=500, width=400, height=40)

    def pagar(self, ventana_pago, entry_efectivo, entry_tarjeta, var_metodo, label_cambio, total):
        try:
            metodo_pago = var_metodo.get()
            cantidad_efectivo = 0.0
            cantidad_tarjeta = 0.0

            if metodo_pago == "Efectivo":
                cantidad_efectivo = float(entry_efectivo.get())
                if cantidad_efectivo < total:
                    messagebox.showerror("Error", "Cantidad en efectivo insuficiente")
                    return
            elif metodo_pago == "Tarjeta":
                cantidad_tarjeta = float(entry_tarjeta.get())
                if cantidad_tarjeta < total:
                    messagebox.showerror("Error", "Cantidad en tarjeta insuficiente")
                    return
            elif metodo_pago == "Mixto":
                cantidad_efectivo = float(entry_efectivo.get())
                cantidad_tarjeta = float(entry_tarjeta.get())
                if (cantidad_efectivo + cantidad_tarjeta) < total:
                    messagebox.showerror("Error", "Pago insuficiente (efectivo + tarjeta)")
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
                        INSERT INTO ventas (factura, nombre_articulo, valor_articulo, cantidad, subtotal, metodo_pago, cantidad_efectivo, cantidad_tarjeta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (self.numero_factura_actual, producto, float(precio), cantidad_vendida, subtotal, metodo_pago, cantidad_efectivo, cantidad_tarjeta))

                    c.execute("UPDATE inventario SET stock = stock - ? WHERE nombre = ?", (cantidad_vendida, producto))

                conn.commit()
                numero_factura_emitida = self.numero_factura_actual
                messagebox.showinfo("Exito", f"La venta se ha completado\nMetodo de pago: {metodo_pago}")
                self.numero_factura_actual += 1
                self.mostrar_numero_factura()

                for i in self.tree.get_children():
                    self.tree.delete(i)
                self.label_suma_total.config(text="Total a pagar: 0 €")
                ventana_pago.destroy()

                fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                self.generar_factura_pdf(productos, total, numero_factura_emitida, fecha, metodo_pago)
        except ValueError:
            messagebox.showerror("Error", "Valores ingresados no validos")

    def generar_factura_pdf(self, productos, total, factura_numero, fecha, metodo_pago="Efectivo"):
        pdf_dir = get_output_path("facturas")
        archivo_pdf = os.path.join(pdf_dir, f"factura_{factura_numero}.pdf")
        c = canvas.Canvas(archivo_pdf, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, f"Factura #{factura_numero}")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 70, f"Fecha: {fecha}")
        c.drawString(100, height - 90, f"Metodo de pago: {metodo_pago}")

        data = [["Producto", "Precio", "Cantidad", "Subtotal"]] + [[p[0], p[1], p[2], p[3]] for p in productos]
        table = Table(data)
        table.wrapOn(c, width, height)
        table.drawOn(c, 100, height - 200)

        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 250, f"Total a pagar: {total:.2f} €")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 370, "Gracias por su compra, vuelva pronto")

        c.save()

        try:
            open_file(archivo_pdf)
        except Exception:
            messagebox.showinfo("Factura generada", f"La factura #{factura_numero} ha sido creada exitosamente en:\n{archivo_pdf}")

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
