# inventario.py
import sqlite3
from tkinter import *
import tkinter as tk
from tkinter import ttk, messagebox
from .barcode_scanner import EscanerCodigoBarras, DialogoAsignarCodigoBarras
from .resources import get_db_path


class Inventario(tk.Frame):
    db_name = get_db_path()
    
    def __init__(self, padre):
        super().__init__(padre)
        self.pack()
        self.escaner = EscanerCodigoBarras(self.db_name)
        self.crear_tabla()
        self.widgets()
    
    def widgets(self):
        frame1 = tk.Frame(self, bg="#dddddd", highlightbackground="gray", highlightthickness=3)
        frame1.pack()
        frame1.place(x=0, y=0, width=1100, height=100)
        titulo = tk.Label(self, text="INVENTARIO", bg="#dddddd", font="sans 30 bold", anchor="center")
        titulo.pack()
        titulo.place(x=5, y=0, width=1090, height=90)
        
        frame2 = tk.Frame(self, bg="#C6D9E3", highlightbackground="gray", highlightthickness=1)
        frame2.place(x=0, y=100, width=1100, height=550)
        
        labelFrame = LabelFrame(frame2, text="Productos", font="sans 22 bold", bg="#C6D9E3")
        labelFrame.place(x=20, y=30, width=400, height=500)
        
        # Campos de entrada
        lblNombre = Label(labelFrame, text="Nombre: ", font="sans 14 bold", bg="#C6D9E3")
        lblNombre.place(x=10, y=20)
        self.nombre = ttk.Entry(labelFrame, font="sans 14 bold")
        self.nombre.place(x=140, y=20, width=240, height=40)
        
        lblProveedor = Label(labelFrame, text="Proveedor: ", font="sans 14 bold", bg="#C6D9E3")
        lblProveedor.place(x=10, y=80)
        self.proveedor = ttk.Entry(labelFrame, font="sans 14 bold")
        self.proveedor.place(x=140, y=80, width=240, height=40)
        
        lblPrecio = Label(labelFrame, text="Precio: ", font="sans 14 bold", bg="#C6D9E3")
        lblPrecio.place(x=10, y=140)
        self.precio = ttk.Entry(labelFrame, font="sans 14 bold")
        self.precio.place(x=140, y=140, width=240, height=40)
        
        lblCosto = Label(labelFrame, text="Costo: ", font="sans 14 bold", bg="#C6D9E3")
        lblCosto.place(x=10, y=200)
        self.costo = ttk.Entry(labelFrame, font="sans 14 bold")
        self.costo.place(x=140, y=200, width=240, height=40)
        
        lblStock = Label(labelFrame, text="Stock: ", font="sans 14 bold", bg="#C6D9E3")
        lblStock.place(x=10, y=260)
        self.stock = ttk.Entry(labelFrame, font="sans 14 bold")
        self.stock.place(x=140, y=260, width=240, height=40)
        
        # Botones
        boton_agregar = tk.Button(labelFrame, text="➕ Ingresar", font="sans 14 bold", bg="#000CFF", fg="white", command=self.registrar)
        boton_agregar.place(x=80, y=340, width=240, height=40)
        
        boton_editar = tk.Button(labelFrame, text="✏️ Editar", font="sans 14 bold", bg="#0000FF", fg="white", command=self.editar_producto)
        boton_editar.place(x=80, y=400, width=240, height=40)
        
        boton_eliminar = tk.Button(frame2, text="🗑️ Eliminar", font="sans 14 bold", bg="#000CFF", fg="white", command=self.eliminar_producto)
        boton_eliminar.place(x=800, y=480, width=260, height=50)
        
        # Tabla de productos
        treeFrame = Frame(frame2, bg="white")
        treeFrame.place(x=440, y=50, width=620, height=400)
        
        scrol_y = ttk.Scrollbar(treeFrame)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_x = ttk.Scrollbar(treeFrame, orient=HORIZONTAL)
        scrol_x.pack(side=BOTTOM, fill=X)
        
        self.tre = ttk.Treeview(treeFrame, yscrollcommand=scrol_y.set, xscrollcommand=scrol_x.set, 
                               columns=("ID", "PRODUCTO", "PROVEEDOR", "PRECIO", "COSTO", "STOCK"), 
                               show="headings", height=10)
        scrol_y.config(command=self.tre.yview)
        scrol_x.config(command=self.tre.xview)
        
        self.tre.heading("ID", text="ID")
        self.tre.heading("PRODUCTO", text="Producto")
        self.tre.heading("PROVEEDOR", text="Proveedor")
        self.tre.heading("PRECIO", text="Precio")
        self.tre.heading("COSTO", text="Costo")
        self.tre.heading("STOCK", text="Stock")
        
        self.tre.column("ID", width=70, anchor="center")
        self.tre.column("PRODUCTO", width=200, anchor="center")
        self.tre.column("PROVEEDOR", width=200, anchor="center")
        self.tre.column("PRECIO", width=100, anchor="center")
        self.tre.column("COSTO", width=100, anchor="center")
        self.tre.column("STOCK", width=70, anchor="center")
        
        self.tre.pack(expand=True, fill=BOTH)
        self.mostrar()
        
        btn_actualizar = Button(frame2, text="🔄 Actualizar inventario", bg="#000CFF", fg="white", font="sans 14 bold", command=self.actualizar_inventario)
        btn_actualizar.place(x=440, y=480, width=260, height=50)
    
    def eje_consulta(self, consulta, parametros=()):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            result = cursor.execute(consulta, parametros)
            conn.commit()
        return result

    def crear_tabla(self):
        consulta = """
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            stock INTEGER NOT NULL
        );
        """
        self.eje_consulta(consulta)
    
    def validacion(self, nombre, prov, precio, costo, stock):
        if not (nombre and prov and precio and costo and stock):
            return False
        try:
            float(precio)
            float(costo)
            int(stock)
        except ValueError:
            return False
        return True
    
    def mostrar(self):
        consulta = "SELECT * FROM inventario ORDER BY id DESC"
        result = self.eje_consulta(consulta)
        for elem in result:
            try:
                precio_eur = "{:,.0f} €".format(float(elem[3])) if elem[3] else ""
                costo_eur = "{:,.0f} €".format(float(elem[4])) if elem[4] else ""
            except ValueError:
                precio_eur = elem[3]
                costo_eur = elem[4]
            self.tre.insert("", 0, text=elem[0], values=(elem[0], elem[1], elem[2], precio_eur, costo_eur, elem[5]))
    
    def actualizar_inventario(self):
        for item in self.tre.get_children():
            self.tre.delete(item)
        self.mostrar()
        messagebox.showinfo("Actualización", "El inventario ha sido actualizado correctamente")
    
    def registrar(self):
        nombre = self.nombre.get()
        prov = self.proveedor.get()
        precio = self.precio.get().strip().replace(",", ".")
        costo = self.costo.get().strip().replace(",", ".")
        stock = self.stock.get()
        
        if self.validacion(nombre, prov, precio, costo, stock):
            try:
                consulta = "INSERT INTO inventario VALUES(?,?,?,?,?,?)"
                parametros = (None, nombre, prov, precio, costo, stock)
                self.eje_consulta(consulta, parametros)
                self.actualizar_inventario()
                self.nombre.delete(0, END)
                self.proveedor.delete(0, END)
                self.precio.delete(0, END)
                self.costo.delete(0, END)
                self.stock.delete(0, END)
            except Exception as e:
                messagebox.showwarning(title="Error", message=f"Error al registrar el producto: {e}")
        else:
            messagebox.showwarning(title="Error", message="Rellene todos los campos correctamente")
    
    def editar_producto(self):
        seleccion = self.tre.selection()
        if not seleccion:
            messagebox.showwarning("Editar producto", "Seleccione un producto para editarlo")
            return
        
        item_id = self.tre.item(seleccion)["text"]
        item_values = self.tre.item(seleccion)["values"]
        
        db_row = self.eje_consulta("SELECT precio, costo FROM inventario WHERE id = ?", (item_id,)).fetchone()
        if db_row is None:
            messagebox.showwarning("Editar producto", "Producto no encontrado")
            return
        precio_original, costo_original = db_row
        
        ventana_editar = Toplevel(self)
        ventana_editar.title("Editar producto")
        ventana_editar.geometry("400x400")
        ventana_editar.config(bg="#C6D9E3")
        
        lbl_nombre = Label(ventana_editar, text="Nombre:", font="sans 14 bold", bg="#C6D9E3")
        lbl_nombre.grid(row=0, column=0, padx=10, pady=10)
        entry_nombre = Entry(ventana_editar, font="sans 14 bold")
        entry_nombre.grid(row=0, column=1, padx=10, pady=10)
        entry_nombre.insert(0, item_values[1])
        
        lbl_proveedor = Label(ventana_editar, text="Proveedor:", font="sans 14 bold", bg="#C6D9E3")
        lbl_proveedor.grid(row=1, column=0, padx=10, pady=10)
        entry_proveedor = Entry(ventana_editar, font="sans 14 bold")
        entry_proveedor.grid(row=1, column=1, padx=10, pady=10)
        entry_proveedor.insert(0, item_values[2])
        
        lbl_precio = Label(ventana_editar, text="Precio:", font="sans 14 bold", bg="#C6D9E3")
        lbl_precio.grid(row=2, column=0, padx=10, pady=10)
        entry_precio = Entry(ventana_editar, font="sans 14 bold")
        entry_precio.grid(row=2, column=1, padx=10, pady=10)
        entry_precio.insert(0, precio_original)
        
        lbl_costo = Label(ventana_editar, text="Costo:", font="sans 14 bold", bg="#C6D9E3")
        lbl_costo.grid(row=3, column=0, padx=10, pady=10)
        entry_costo = Entry(ventana_editar, font="sans 14 bold")
        entry_costo.grid(row=3, column=1, padx=10, pady=10)
        entry_costo.insert(0, costo_original)
        
        lbl_stock = Label(ventana_editar, text="Stock:", font="sans 14 bold", bg="#C6D9E3")
        lbl_stock.grid(row=4, column=0, padx=10, pady=10)
        entry_stock = Entry(ventana_editar, font="sans 14 bold")
        entry_stock.grid(row=4, column=1, padx=10, pady=10)
        entry_stock.insert(0, item_values[5])
        
        def guardar_cambio():
            nombre = entry_nombre.get()
            proveedor = entry_proveedor.get()
            precio = entry_precio.get()
            costo = entry_costo.get()
            stock = entry_stock.get()
            
            if not (nombre and proveedor and precio and costo and stock):
                messagebox.showwarning("Guardar cambios", "Rellene todos los campos.")
                return
            
            try:
                precio = float(precio.replace(",", "."))
                costo = float(costo.replace(",", "."))
                stock = int(stock)
            except ValueError:
                messagebox.showwarning("Guardar cambios", "Ingrese valores numéricos válidos para precio, costo y stock")
                return
            
            consulta = "UPDATE inventario SET nombre=?, proveedor=?, precio=?, costo=?, stock=? WHERE id=?"
            parametros = (nombre, proveedor, precio, costo, stock, item_id)
            self.eje_consulta(consulta, parametros)
            self.actualizar_inventario()
            ventana_editar.destroy()
        
        btn_guardar = Button(ventana_editar, text="Guardar cambios", font="sans 14 bold", command=guardar_cambio)
        btn_guardar.place(x=80, y=250, width=240, height=40)
    
    def eliminar_producto(self):
        seleccion = self.tre.selection()
        if not seleccion:
            messagebox.showwarning("Eliminar producto", "Seleccione un producto para eliminar")
            return
        
        item_id = self.tre.item(seleccion)["text"]
        nombre_producto = self.tre.item(seleccion)["values"][1]
        
        if messagebox.askyesno("Confirmar eliminación", f"¿Está seguro de eliminar '{nombre_producto}'?"):
            try:
                consulta = "DELETE FROM inventario WHERE id = ?"
                self.eje_consulta(consulta, (item_id,))
                self.actualizar_inventario()
                messagebox.showinfo("Éxito", "Producto eliminado correctamente")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar el producto: {e}")