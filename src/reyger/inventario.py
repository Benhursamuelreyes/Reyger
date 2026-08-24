# inventario.py
import sqlite3
from tkinter import *
import tkinter as tk
from tkinter import ttk, messagebox
from .barcode_scanner import (
    DialogoAsignarCodigoBarras,
    DialogoRegistroRapido,
    EscanerCodigoBarras,
)
from .fiscal import TIPOS_IVA, IVA_POR_DEFECTO, normalizar_tipo_iva
from . import categorias as gestor_categorias
from .resources import get_db_path


class Inventario(tk.Frame):
    db_name = get_db_path()

    def __init__(self, padre):
        super().__init__(padre)
        self.pack()
        self.escaner = EscanerCodigoBarras(self.db_name)
        self.widgets()

    def widgets(self):
        frame1 = tk.Frame(self, bg="#dddddd", highlightbackground="gray", highlightthickness=3)
        frame1.pack(fill="x")
        titulo = tk.Label(frame1, text="INVENTARIO", bg="#dddddd", font="sans 30 bold", anchor="center")
        titulo.pack(fill="both", expand=True)

        frame2 = tk.Frame(self, bg="#C6D9E3", highlightbackground="gray", highlightthickness=1)
        frame2.pack(fill="both", expand=True)

        # Formulario de alta/edición (izquierda)
        labelFrame = LabelFrame(frame2, text="Productos", font="sans 22 bold", bg="#C6D9E3")
        labelFrame.pack(side="left", fill="y", padx=20, pady=20)

        lblNombre = Label(labelFrame, text="Nombre: ", font="sans 14 bold", bg="#C6D9E3")
        lblNombre.grid(row=0, column=0, sticky="e", padx=10, pady=10)
        self.nombre = ttk.Entry(labelFrame, font="sans 14 bold")
        self.nombre.grid(row=0, column=1, sticky="ew", padx=10, pady=10)

        lblProveedor = Label(labelFrame, text="Proveedor: ", font="sans 14 bold", bg="#C6D9E3")
        lblProveedor.grid(row=1, column=0, sticky="e", padx=10, pady=10)
        frame_proveedor = tk.Frame(labelFrame, bg="#C6D9E3")
        frame_proveedor.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        self.proveedor = ttk.Combobox(frame_proveedor, font="sans 14 bold")
        self.proveedor.pack(side="left", fill="x", expand=True)
        btn_nuevo_proveedor = tk.Button(
            frame_proveedor, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white", command=self.nuevo_proveedor,
        )
        btn_nuevo_proveedor.pack(side="left", padx=(6, 0))
        self.cargar_proveedores()

        lblPrecio = Label(labelFrame, text="Precio de venta: ", font="sans 14 bold", bg="#C6D9E3")
        lblPrecio.grid(row=2, column=0, sticky="e", padx=10, pady=10)
        self.precio = ttk.Entry(labelFrame, font="sans 14 bold")
        self.precio.grid(row=2, column=1, sticky="ew", padx=10, pady=10)

        lblCosto = Label(labelFrame, text="Precio de costo: ", font="sans 14 bold", bg="#C6D9E3")
        lblCosto.grid(row=3, column=0, sticky="e", padx=10, pady=10)
        self.costo = ttk.Entry(labelFrame, font="sans 14 bold")
        self.costo.grid(row=3, column=1, sticky="ew", padx=10, pady=10)

        lblStock = Label(labelFrame, text="Stock: ", font="sans 14 bold", bg="#C6D9E3")
        lblStock.grid(row=4, column=0, sticky="e", padx=10, pady=10)
        self.stock = ttk.Entry(labelFrame, font="sans 14 bold")
        self.stock.grid(row=4, column=1, sticky="ew", padx=10, pady=10)

        lblIva = Label(labelFrame, text="IVA: ", font="sans 14 bold", bg="#C6D9E3")
        lblIva.grid(row=5, column=0, sticky="e", padx=10, pady=10)
        self.iva = ttk.Combobox(
            labelFrame, font="sans 14 bold",
            values=[f"{tipo:g}%" for tipo in TIPOS_IVA],
        )
        self.iva.set(f"{IVA_POR_DEFECTO:g}%")
        self.iva.grid(row=5, column=1, sticky="ew", padx=10, pady=10)

        lblCategoria = Label(labelFrame, text="Categoría: ", font="sans 14 bold", bg="#C6D9E3")
        lblCategoria.grid(row=6, column=0, sticky="e", padx=10, pady=10)
        frame_categoria = tk.Frame(labelFrame, bg="#C6D9E3")
        frame_categoria.grid(row=6, column=1, sticky="ew", padx=10, pady=10)
        self.categoria = ttk.Combobox(frame_categoria, font="sans 14 bold", state="readonly")
        self.categoria.pack(side="left", fill="x", expand=True)
        btn_nueva_categoria = tk.Button(
            frame_categoria, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white",
            command=lambda: self.crear_categoria_dialogo(self.categoria),
        )
        btn_nueva_categoria.pack(side="left", padx=(6, 0))
        self.cargar_categorias()

        lblCodigo = Label(labelFrame, text="Código de barras: ", font="sans 14 bold", bg="#C6D9E3")
        lblCodigo.grid(row=7, column=0, sticky="e", padx=10, pady=10)
        self.codigo_barras = ttk.Entry(labelFrame, font="sans 14 bold")
        self.codigo_barras.grid(row=7, column=1, sticky="ew", padx=10, pady=10)

        labelFrame.columnconfigure(1, weight=1)

        boton_agregar = tk.Button(labelFrame, text="➕ Ingresar", font="sans 14 bold", bg="#000CFF", fg="white", command=self.registrar)
        boton_agregar.grid(row=8, column=0, columnspan=2, sticky="ew", padx=10, pady=(25, 10), ipady=4)

        boton_editar = tk.Button(labelFrame, text="✏️ Editar", font="sans 14 bold", bg="#0000FF", fg="white", command=self.editar_producto)
        boton_editar.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=10, ipady=4)

        # Listado (derecha)
        frame_derecha = tk.Frame(frame2, bg="#C6D9E3")
        frame_derecha.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=20)

        frame_filtro = tk.Frame(frame_derecha, bg="#C6D9E3")
        frame_filtro.pack(fill="x", pady=(0, 10))
        lbl_filtro = Label(frame_filtro, text="Filtrar por categoría:", font="sans 13 bold", bg="#C6D9E3")
        lbl_filtro.pack(side="left", padx=(0, 8))
        self.filtro_categoria = ttk.Combobox(frame_filtro, font="sans 13 bold", state="readonly")
        self.filtro_categoria.pack(side="left", fill="x", expand=True)
        self.filtro_categoria.bind("<<ComboboxSelected>>", lambda _evento: self.aplicar_filtro())
        self.cargar_categorias()

        # Barra de entrada manual de códigos de barras
        frame_codigo = tk.Frame(frame_derecha, bg="#C6D9E3")
        frame_codigo.pack(fill="x", pady=(0, 10))
        Label(frame_codigo, text="🏷️ Código de barras:", font="sans 13 bold", bg="#C6D9E3").pack(side="left", padx=(0, 8))
        self.entry_busca_codigo = ttk.Entry(frame_codigo, font="sans 13")
        self.entry_busca_codigo.pack(side="left", fill="x", expand=True)
        self.entry_busca_codigo.bind("<Return>", lambda _evento: self.buscar_por_codigo())
        Button(
            frame_codigo, text="🔍 Buscar", font="sans 12 bold",
            bg="#000CFF", fg="white", command=self.buscar_por_codigo,
        ).pack(side="left", padx=(8, 0), ipadx=6, ipady=2)
        Button(
            frame_codigo, text="🏷️ Asignar al seleccionado", font="sans 12 bold",
            bg="#17A2B8", fg="white", command=self.asignar_codigo_seleccionado,
        ).pack(side="left", padx=(8, 0), ipadx=6, ipady=2)

        treeFrame = Frame(frame_derecha, bg="white")
        treeFrame.pack(fill="both", expand=True)

        scrol_y = ttk.Scrollbar(treeFrame)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_x = ttk.Scrollbar(treeFrame, orient=HORIZONTAL)
        scrol_x.pack(side=BOTTOM, fill=X)

        self.tre = ttk.Treeview(treeFrame, yscrollcommand=scrol_y.set, xscrollcommand=scrol_x.set,
                               columns=("ID", "PRODUCTO", "PROVEEDOR", "PRECIO", "COSTO", "STOCK", "IVA", "CATEGORIA"),
                               show="headings", height=10)
        scrol_y.config(command=self.tre.yview)
        scrol_x.config(command=self.tre.xview)

        self.tre.heading("ID", text="ID")
        self.tre.heading("PRODUCTO", text="Producto")
        self.tre.heading("PROVEEDOR", text="Proveedor")
        self.tre.heading("PRECIO", text="P. venta")
        self.tre.heading("COSTO", text="P. costo")
        self.tre.heading("STOCK", text="Stock")
        self.tre.heading("IVA", text="IVA")
        self.tre.heading("CATEGORIA", text="Categoría")

        self.tre.column("ID", width=70, anchor="center")
        self.tre.column("PRODUCTO", width=200, anchor="center")
        self.tre.column("PROVEEDOR", width=200, anchor="center")
        self.tre.column("PRECIO", width=100, anchor="center")
        self.tre.column("COSTO", width=100, anchor="center")
        self.tre.column("STOCK", width=70, anchor="center")
        self.tre.column("IVA", width=70, anchor="center")
        self.tre.column("CATEGORIA", width=120, anchor="center")

        self.tre.pack(expand=True, fill=BOTH)
        self.mostrar()

        frame_botones = tk.Frame(frame_derecha, bg="#C6D9E3")
        frame_botones.pack(fill="x", pady=(15, 0))
        btn_actualizar = Button(frame_botones, text="🔄 Actualizar inventario", bg="#000CFF", fg="white", font="sans 14 bold", command=self.actualizar_inventario)
        btn_actualizar.pack(side="left", expand=True, fill="x", padx=(0, 8), ipady=6)
        boton_eliminar = tk.Button(frame_botones, text="🗑️ Eliminar", font="sans 14 bold", bg="#000CFF", fg="white", command=self.eliminar_producto)
        boton_eliminar.pack(side="left", expand=True, fill="x", ipady=6)

    def cargar_proveedores(self):
        try:
            result = self.eje_consulta("SELECT nombre FROM proveedores ORDER BY nombre")
            nombres = [fila[0] for fila in result.fetchall()]
        except sqlite3.Error:
            nombres = []
        self.proveedor["values"] = nombres

    def nuevo_proveedor(self):
        ventana = Toplevel(self)
        ventana.title("Nuevo proveedor")
        ventana.geometry("480x420")
        ventana.resizable(True, True)
        ventana.minsize(440, 380)
        ventana.config(bg="#C6D9E3")
        ventana.transient(self.winfo_toplevel())
        ventana.grab_set()

        campos = {}
        for fila, (clave, etiqueta) in enumerate([
            ("nombre", "Nombre *:"), ("cif", "CIF:"),
            ("contacto", "Contacto:"), ("telefono", "Teléfono:"),
            ("email", "Email:"),
        ]):
            Label(ventana, text=etiqueta, font="sans 13 bold", bg="#C6D9E3").grid(
                row=fila, column=0, sticky="e", padx=10, pady=8)
            entry = ttk.Entry(ventana, font="sans 13")
            entry.grid(row=fila, column=1, sticky="ew", padx=10, pady=8)
            campos[clave] = entry
        ventana.columnconfigure(1, weight=1)

        def guardar_proveedor():
            nombre = campos["nombre"].get().strip()
            if not nombre:
                messagebox.showwarning("Nuevo proveedor", "El nombre es obligatorio")
                return
            try:
                self.eje_consulta(
                    "INSERT INTO proveedores (nombre, cif, contacto, telefono, email)"
                    " VALUES (?,?,?,?,?)",
                    (
                        nombre,
                        campos["cif"].get().strip(),
                        campos["contacto"].get().strip(),
                        campos["telefono"].get().strip(),
                        campos["email"].get().strip(),
                    ),
                )
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo guardar el proveedor: {e}")
                return
            self.cargar_proveedores()
            self.proveedor.set(nombre)
            ventana.destroy()

        Button(
            ventana, text="💾 Guardar proveedor", font="sans 13 bold",
            bg="#27AE60", fg="white", command=guardar_proveedor,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(20, 10), ipady=4)
    
    def eje_consulta(self, consulta, parametros=()):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            result = cursor.execute(consulta, parametros)
            conn.commit()
        return result
    
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
    
    def cargar_categorias(self):
        try:
            filas = self.eje_consulta(
                "SELECT nombre FROM categorias ORDER BY CASE WHEN nombre = 'General' THEN 0 ELSE 1 END, nombre"
            ).fetchall()
            nombres = [fila[0] for fila in filas]
        except sqlite3.Error:
            nombres = ["General"]
        if not nombres:
            gestor_categorias.crear("General")
            nombres = ["General"]
        if hasattr(self, "categoria"):
            self.categoria["values"] = nombres
            if self.categoria.get() not in nombres:
                self.categoria.set(nombres[0])
        if hasattr(self, "filtro_categoria"):
            self.filtro_categoria["values"] = ["Todas"] + nombres
            if not self.filtro_categoria.get():
                self.filtro_categoria.set("Todas")

    def crear_categoria_dialogo(self, combo):
        """Diálogo modal para crear una categoría y dejarla seleccionada."""
        dialogo = Toplevel(self)
        dialogo.title("Crear nueva categoría")
        dialogo.geometry("380x180")
        dialogo.resizable(False, False)
        dialogo.config(bg="#C6D9E3")
        dialogo.transient(self.winfo_toplevel())
        dialogo.grab_set()

        Label(
            dialogo, text="Nombre de la categoría:",
            font="sans 13 bold", bg="#C6D9E3",
        ).pack(pady=(20, 6))
        entry_nombre = Entry(dialogo, font="sans 14 bold")
        entry_nombre.pack(ipadx=30, ipady=3)
        entry_nombre.focus_set()

        def guardar():
            try:
                nueva_id = gestor_categorias.crear(entry_nombre.get())
            except ValueError as exc:
                messagebox.showwarning("Crear categoría", str(exc), parent=dialogo)
                return
            if nueva_id is None:
                messagebox.showwarning(
                    "Crear categoría",
                    "Ya existe una categoría con ese nombre.",
                    parent=dialogo,
                )
                return
            self.cargar_categorias()
            combo.set(entry_nombre.get().strip())
            messagebox.showinfo(
                "Crear categoría", "Categoría creada correctamente.", parent=dialogo
            )
            dialogo.destroy()

        entry_nombre.bind("<Return>", lambda _evento: guardar())
        Button(
            dialogo, text="Guardar", font="sans 13 bold",
            bg="#000CFF", fg="white", command=guardar,
        ).pack(pady=(16, 0), ipadx=24, ipady=2)

        dialogo.wait_window()

    def aplicar_filtro(self):
        for item in self.tre.get_children():
            self.tre.delete(item)
        eleccion = self.filtro_categoria.get()
        self.mostrar(None if eleccion == "Todas" else eleccion)

    # ------------------------------------------------------------------
    # Códigos de barras: búsqueda manual y alta automática
    # ------------------------------------------------------------------

    def _refrescar_listado(self):
        for item in self.tre.get_children():
            self.tre.delete(item)
        eleccion = self.filtro_categoria.get() if hasattr(self, "filtro_categoria") else "Todas"
        self.mostrar(None if eleccion == "Todas" else eleccion)

    def _seleccionar_producto(self, id_producto):
        """Selecciona y hace visible la fila del producto indicado."""
        objetivo = str(id_producto)
        for item in self.tre.get_children():
            if str(self.tre.item(item)["text"]) == objetivo:
                self.tre.selection_set(item)
                self.tre.see(item)
                self.tre.focus(item)
                return True
        return False

    def buscar_por_codigo(self):
        """Localiza el producto por código; si no existe, ofrece registrarlo."""
        codigo = self.entry_busca_codigo.get().strip()
        if not codigo:
            return
        self.entry_busca_codigo.delete(0, tk.END)

        producto = self.escaner.buscar_producto_por_codigo(codigo)
        if producto is not None:
            encontrado = self._seleccionar_producto(producto["id"])
            if not encontrado:
                messagebox.showinfo(
                    "Código de barras",
                    f"«{producto['nombre']}» tiene ese código pero no está "
                    "visible con el filtro actual.",
                )
            return

        registrar = messagebox.askyesno(
            "Código no registrado",
            f"El código «{codigo}» no está registrado en el inventario.\n"
            "¿Desea registrar un producto nuevo con él?",
        )
        if not registrar:
            return
        dialogo = DialogoRegistroRapido(self, codigo, self.db_name)
        nuevo = dialogo.resultado
        if nuevo is None:
            return
        self._refrescar_listado()
        self.categoria["values"] = self._categorias_disponibles_nombres()
        self._seleccionar_producto(nuevo["id"])
        messagebox.showinfo(
            "Código de barras",
            f"Producto «{nuevo['nombre']}» registrado con el código {codigo}.",
        )

    def _categorias_disponibles_nombres(self):
        try:
            filas = self.eje_consulta(
                "SELECT nombre FROM categorias ORDER BY CASE WHEN nombre = 'General' THEN 0 ELSE 1 END, nombre"
            ).fetchall()
            return [fila[0] for fila in filas]
        except sqlite3.Error:
            return ["General"]

    def asignar_codigo_seleccionado(self):
        """Abre el diálogo para asignar/editar el código del producto elegido."""
        seleccion = self.tre.selection()
        if not seleccion:
            messagebox.showwarning(
                "Asignar código", "Seleccione un producto en el listado."
            )
            return
        item_id = self.tre.item(seleccion)["text"]
        valores = self.tre.item(seleccion)["values"]
        DialogoAsignarCodigoBarras(self, item_id, valores[1], self.escaner)

    def mostrar(self, filtro_categoria=None):
        # Columnas explícitas: i.* es frágil porque ALTER TABLE añade
        # las columnas nuevas al final y desplaza los índices posicionales.
        base = (
            "SELECT i.id, i.nombre, i.proveedor, i.precio, i.costo,"
            " i.stock, i.tipo_iva, c.nombre FROM inventario i "
            "LEFT JOIN categorias c ON c.id = i.categoria_id "
        )
        if filtro_categoria:
            consulta = base + "WHERE c.nombre = ? ORDER BY i.id DESC"
            result = self.eje_consulta(consulta, (filtro_categoria,))
        else:
            consulta = base + "ORDER BY i.id DESC"
            result = self.eje_consulta(consulta)
        for elem in result:
            try:
                precio_eur = "{:,.0f} €".format(float(elem[3])) if elem[3] else ""
                costo_eur = "{:,.0f} €".format(float(elem[4])) if elem[4] else ""
            except ValueError:
                precio_eur = elem[3]
                costo_eur = elem[4]
            iva_txt = f"{elem[6]:g}%" if elem[6] is not None else ""
            categoria_txt = elem[7] if len(elem) > 7 and elem[7] else ""
            self.tre.insert("", 0, text=elem[0], values=(elem[0], elem[1], elem[2], precio_eur, costo_eur, elem[5], iva_txt, categoria_txt))
    
    def actualizar_inventario(self):
        for item in self.tre.get_children():
            self.tre.delete(item)
        eleccion = self.filtro_categoria.get() if hasattr(self, "filtro_categoria") else "Todas"
        self.mostrar(None if eleccion == "Todas" else eleccion)
        messagebox.showinfo("Actualización", "El inventario ha sido actualizado correctamente")
    
    def registrar(self):
        nombre = self.nombre.get()
        prov = self.proveedor.get()
        precio = self.precio.get().strip().replace(",", ".")
        costo = self.costo.get().strip().replace(",", ".")
        stock = self.stock.get()
        tipo_iva = normalizar_tipo_iva(self.iva.get())
        codigo = self.codigo_barras.get().strip()

        if self.validacion(nombre, prov, precio, costo, stock) and tipo_iva is not None:
            try:
                if codigo:
                    duplicado = self.eje_consulta(
                        "SELECT id FROM inventario WHERE codigo_barras = ?", (codigo,)
                    ).fetchone()
                    if duplicado:
                        messagebox.showwarning(
                            title="Código duplicado",
                            message=f"El código «{codigo}» ya está asignado a otro producto.",
                        )
                        return
                fila_proveedor = self.eje_consulta(
                    "SELECT id FROM proveedores WHERE nombre = ?", (prov,)
                ).fetchone()
                proveedor_id = fila_proveedor[0] if fila_proveedor else None
                fila_categoria = self.eje_consulta(
                    "SELECT id FROM categorias WHERE nombre = ?",
                    (self.categoria.get() or "General",),
                ).fetchone()
                categoria_id = fila_categoria[0] if fila_categoria else None
                consulta = (
                    "INSERT INTO inventario (nombre, proveedor, precio, costo,"
                    " stock, proveedor_id, tipo_iva, categoria_id, codigo_barras)"
                    " VALUES(?,?,?,?,?,?,?,?,?)"
                )
                parametros = (
                    nombre, prov, precio, costo, stock,
                    proveedor_id, tipo_iva, categoria_id, codigo or None,
                )
                self.eje_consulta(consulta, parametros)
                self.actualizar_inventario()
                self.nombre.delete(0, END)
                self.proveedor.delete(0, END)
                self.precio.delete(0, END)
                self.costo.delete(0, END)
                self.stock.delete(0, END)
                self.codigo_barras.delete(0, END)
                self.iva.set(f"{IVA_POR_DEFECTO:g}%")
                self.categoria.set("General")
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
        
        db_row = self.eje_consulta(
            "SELECT precio, costo, tipo_iva, categoria_id, codigo_barras"
            " FROM inventario WHERE id = ?",
            (item_id,),
        ).fetchone()
        if db_row is None:
            messagebox.showwarning("Editar producto", "Producto no encontrado")
            return
        precio_original = db_row[0]
        costo_original = db_row[1]
        iva_original = f"{db_row[2]:g}%" if db_row[2] is not None else f"{IVA_POR_DEFECTO:g}%"
        categoria_actual = db_row[3]
        
        ventana_editar = Toplevel(self)
        ventana_editar.title("Editar producto")
        ventana_editar.geometry("520x620")
        ventana_editar.resizable(True, True)
        ventana_editar.minsize(480, 580)
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
        
        lbl_precio = Label(ventana_editar, text="Precio de venta:", font="sans 14 bold", bg="#C6D9E3")
        lbl_precio.grid(row=2, column=0, padx=10, pady=10)
        entry_precio = Entry(ventana_editar, font="sans 14 bold")
        entry_precio.grid(row=2, column=1, padx=10, pady=10)
        entry_precio.insert(0, precio_original)
        
        lbl_costo = Label(ventana_editar, text="Precio de costo:", font="sans 14 bold", bg="#C6D9E3")
        lbl_costo.grid(row=3, column=0, padx=10, pady=10)
        entry_costo = Entry(ventana_editar, font="sans 14 bold")
        entry_costo.grid(row=3, column=1, padx=10, pady=10)
        entry_costo.insert(0, costo_original)
        
        lbl_stock = Label(ventana_editar, text="Stock:", font="sans 14 bold", bg="#C6D9E3")
        lbl_stock.grid(row=4, column=0, padx=10, pady=10)
        entry_stock = Entry(ventana_editar, font="sans 14 bold")
        entry_stock.grid(row=4, column=1, padx=10, pady=10)
        entry_stock.insert(0, item_values[5])

        lbl_iva = Label(ventana_editar, text="IVA:", font="sans 14 bold", bg="#C6D9E3")
        lbl_iva.grid(row=5, column=0, padx=10, pady=10)
        combo_iva = ttk.Combobox(
            ventana_editar, font="sans 14 bold",
            values=[f"{tipo:g}%" for tipo in TIPOS_IVA],
        )
        combo_iva.set(iva_original)
        combo_iva.grid(row=5, column=1, padx=10, pady=10)

        lbl_categoria = Label(ventana_editar, text="Categoría:", font="sans 14 bold", bg="#C6D9E3")
        lbl_categoria.grid(row=6, column=0, padx=10, pady=10)
        frame_cat = tk.Frame(ventana_editar, bg="#C6D9E3")
        frame_cat.grid(row=6, column=1, padx=10, pady=10)
        combo_categoria = ttk.Combobox(
            frame_cat, font="sans 14 bold", state="readonly",
            values=[n for _, n in self._categorias_disponibles()],
        )
        fila_cat = self.eje_consulta(
            "SELECT nombre FROM categorias WHERE id = ?", (categoria_actual,)
        ).fetchone() if categoria_actual else None
        combo_categoria.set(fila_cat[0] if fila_cat else "General")
        combo_categoria.pack(side="left", fill="x", expand=True)
        btn_nueva_cat = tk.Button(
            frame_cat, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white",
            command=lambda: self.crear_categoria_dialogo(combo_categoria),
        )
        btn_nueva_cat.pack(side="left", padx=(6, 0))

        lbl_codigo = Label(ventana_editar, text="Código de barras:", font="sans 14 bold", bg="#C6D9E3")
        lbl_codigo.grid(row=7, column=0, padx=10, pady=10)
        entry_codigo = Entry(ventana_editar, font="sans 14 bold")
        entry_codigo.grid(row=7, column=1, padx=10, pady=10)
        if db_row[4]:
            entry_codigo.insert(0, db_row[4])

        def guardar_cambio():
            nombre = entry_nombre.get()
            proveedor = entry_proveedor.get()
            precio = entry_precio.get()
            costo = entry_costo.get()
            stock = entry_stock.get()
            tipo_iva = normalizar_tipo_iva(combo_iva.get())
            categoria_elegida = combo_categoria.get()
            codigo_nuevo = entry_codigo.get().strip()

            if not (nombre and proveedor and precio and costo and stock):
                messagebox.showwarning("Guardar cambios", "Rellene todos los campos.")
                return

            if tipo_iva is None:
                messagebox.showwarning("Guardar cambios", "Introduzca un IVA válido (0-100)")
                return

            try:
                precio = float(precio.replace(",", "."))
                costo = float(costo.replace(",", "."))
                stock = int(stock)
            except ValueError:
                messagebox.showwarning("Guardar cambios", "Ingrese valores numéricos válidos para precio de venta, precio de costo y stock")
                return

            if codigo_nuevo:
                duplicado = self.eje_consulta(
                    "SELECT id FROM inventario WHERE codigo_barras = ? AND id != ?",
                    (codigo_nuevo, item_id),
                ).fetchone()
                if duplicado:
                    messagebox.showwarning(
                        "Guardar cambios",
                        f"El código «{codigo_nuevo}» ya está asignado a otro producto.",
                    )
                    return

            fila_cat_nueva = self.eje_consulta(
                "SELECT id FROM categorias WHERE nombre = ?",
                (categoria_elegida or "General",),
            ).fetchone()
            categoria_id_nueva = fila_cat_nueva[0] if fila_cat_nueva else None

            consulta = (
                "UPDATE inventario SET nombre=?, proveedor=?, precio=?, costo=?,"
                " stock=?, tipo_iva=?, categoria_id=?, codigo_barras=? WHERE id=?"
            )
            parametros = (
                nombre, proveedor, precio, costo, stock,
                tipo_iva, categoria_id_nueva, codigo_nuevo or None, item_id,
            )
            self.eje_consulta(consulta, parametros)
            self.actualizar_inventario()
            ventana_editar.destroy()

        btn_guardar = Button(ventana_editar, text="Guardar cambios", font="sans 14 bold", command=guardar_cambio)
        btn_guardar.grid(row=8, column=0, columnspan=2, padx=10, pady=(25, 10), ipady=4)

    def _categorias_disponibles(self):
        try:
            filas = self.eje_consulta(
                "SELECT id, nombre FROM categorias ORDER BY CASE WHEN nombre = 'General' THEN 0 ELSE 1 END, nombre"
            ).fetchall()
            return [(fila[0], fila[1]) for fila in filas]
        except sqlite3.Error:
            return []
    
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