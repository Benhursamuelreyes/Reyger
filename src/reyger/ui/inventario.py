# inventario.py
import os
import sqlite3
from datetime import datetime
from tkinter import (
    BOTH, BOTTOM, END, HORIZONTAL, RIGHT, X, Y,
    Button, Entry, Frame, Label, LabelFrame, Toplevel,
)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ..hardware.barcode_scanner import (
    DialogoAsignarCodigoBarras,
    DialogoRegistroRapido,
    EscanerCodigoBarras,
)
from ..domain.fiscal import TIPOS_IVA, IVA_POR_DEFECTO, normalizar_tipo_iva
from . import categorias as gestor_categorias
from ..domain import inventario as dominio
from ..core import moneda as mod_moneda
from ..core.db import wal_activo
from ..core.backup import (
    AVISO_COPIA_MANUAL,
    BackupError,
    importar_datos,
    exportar_sqlite,
)
from ..core.hilos import en_hilo
from ..config import ConfigManager


class Inventario(tk.Frame):

    def __init__(self, padre):
        super().__init__(padre)
        self.colors = ConfigManager().get_colors()
        self.pack()
        self.escaner = EscanerCodigoBarras()
        self.widgets()

    def widgets(self):
        frame1 = tk.Frame(self, bg=self.colors["bg_cabecera"], highlightbackground="gray", highlightthickness=3)
        frame1.pack(fill="x")
        titulo = tk.Label(frame1, text="INVENTARIO", bg=self.colors["bg_cabecera"], font="sans 30 bold", anchor="center")
        titulo.pack(fill="both", expand=True)

        frame2 = tk.Frame(self, bg=self.colors["bg_principal"], highlightbackground="gray", highlightthickness=1)
        frame2.pack(fill="both", expand=True)

        # Formulario de alta/edición (izquierda)
        labelFrame = LabelFrame(frame2, text="Productos", font="sans 22 bold", bg=self.colors["bg_principal"])
        labelFrame.pack(side="left", fill="y", padx=20, pady=20)

        lblNombre = Label(labelFrame, text="Nombre: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblNombre.grid(row=0, column=0, sticky="e", padx=10, pady=6)
        self.nombre = ttk.Entry(labelFrame, font="sans 14 bold")
        self.nombre.grid(row=0, column=1, sticky="ew", padx=10, pady=6)

        lblProveedor = Label(labelFrame, text="Proveedor: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblProveedor.grid(row=1, column=0, sticky="e", padx=10, pady=6)
        frame_proveedor = tk.Frame(labelFrame, bg=self.colors["bg_principal"])
        frame_proveedor.grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        self.proveedor = ttk.Combobox(frame_proveedor, font="sans 14 bold")
        self.proveedor.pack(side="left", fill="x", expand=True)
        btn_nuevo_proveedor = tk.Button(
            frame_proveedor, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white", command=self.nuevo_proveedor,
        )
        btn_nuevo_proveedor.pack(side="left", padx=(6, 0))
        self.cargar_proveedores()

        self.precio_sv = tk.StringVar(self)
        self.costo_sv = tk.StringVar(self)
        self.margen_sv = tk.StringVar(self)
        self._calculando = False

        lblCosto = Label(labelFrame, text="Precio de costo (€): ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblCosto.grid(row=2, column=0, sticky="e", padx=10, pady=6)
        self.costo = ttk.Entry(labelFrame, font="sans 14 bold", textvariable=self.costo_sv)
        self.costo.grid(row=2, column=1, sticky="ew", padx=10, pady=6)
        self.costo_sv.trace_add("write", self._desde_costo_margen)

        lblMargen = Label(labelFrame, text="Margen / ganancia (%): ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblMargen.grid(row=3, column=0, sticky="e", padx=10, pady=6)
        self.margen = ttk.Entry(labelFrame, font="sans 14 bold", textvariable=self.margen_sv)
        self.margen.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
        self.margen_sv.trace_add("write", self._desde_costo_margen)

        lblPrecio = Label(labelFrame, text="Precio de venta (€): ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblPrecio.grid(row=4, column=0, sticky="e", padx=10, pady=6)
        self.precio = ttk.Entry(labelFrame, font="sans 14 bold", textvariable=self.precio_sv)
        self.precio.grid(row=4, column=1, sticky="ew", padx=10, pady=6)
        self.precio_sv.trace_add("write", self._desde_venta)

        lblStock = Label(labelFrame, text="Stock: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblStock.grid(row=5, column=0, sticky="e", padx=10, pady=6)
        self.stock = ttk.Entry(labelFrame, font="sans 14 bold")
        self.stock.grid(row=5, column=1, sticky="ew", padx=10, pady=6)

        lblIva = Label(labelFrame, text="IVA: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblIva.grid(row=6, column=0, sticky="e", padx=10, pady=6)
        self.iva = ttk.Combobox(
            labelFrame, font="sans 14 bold",
            values=[f"{tipo:g}%" for tipo in TIPOS_IVA],
        )
        self.iva.set(f"{IVA_POR_DEFECTO:g}%")
        self.iva.grid(row=6, column=1, sticky="ew", padx=10, pady=6)

        lblCategoria = Label(labelFrame, text="Categoría: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblCategoria.grid(row=7, column=0, sticky="e", padx=10, pady=6)
        frame_categoria = tk.Frame(labelFrame, bg=self.colors["bg_principal"])
        frame_categoria.grid(row=7, column=1, sticky="ew", padx=10, pady=6)
        self.categoria = ttk.Combobox(frame_categoria, font="sans 14 bold", state="readonly")
        self.categoria.pack(side="left", fill="x", expand=True)
        btn_nueva_categoria = tk.Button(
            frame_categoria, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white",
            command=lambda: self.crear_categoria_dialogo(self.categoria),
        )
        btn_nueva_categoria.pack(side="left", padx=(6, 0))
        self.cargar_categorias()

        lblCodigo = Label(labelFrame, text="Código de barras: ", font="sans 14 bold", bg=self.colors["bg_principal"])
        lblCodigo.grid(row=8, column=0, sticky="e", padx=10, pady=6)
        self.codigo_barras = ttk.Entry(labelFrame, font="sans 14 bold")
        self.codigo_barras.grid(row=8, column=1, sticky="ew", padx=10, pady=6)

        labelFrame.columnconfigure(1, weight=1)

        boton_agregar = tk.Button(labelFrame, text="➕ Ingresar", font="sans 14 bold", bg="#000CFF", fg="white", command=self.registrar)
        boton_agregar.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=(14, 6), ipady=4)

        boton_editar = tk.Button(labelFrame, text="✏️ Editar", font="sans 14 bold", bg="#0000FF", fg="white", command=self.editar_producto)
        boton_editar.grid(row=10, column=0, columnspan=2, sticky="ew", padx=10, pady=6, ipady=4)

        # Listado (derecha)
        frame_derecha = tk.Frame(frame2, bg=self.colors["bg_principal"])
        frame_derecha.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=20)

        frame_filtro = tk.Frame(frame_derecha, bg=self.colors["bg_principal"])
        frame_filtro.pack(fill="x", pady=(0, 10))
        lbl_filtro = Label(frame_filtro, text="Filtrar por categoría:", font="sans 13 bold", bg=self.colors["bg_principal"])
        lbl_filtro.pack(side="left", padx=(0, 8))
        self.filtro_categoria = ttk.Combobox(frame_filtro, font="sans 13 bold", state="readonly")
        self.filtro_categoria.pack(side="left", fill="x", expand=True)
        self.filtro_categoria.bind("<<ComboboxSelected>>", lambda _evento: self.aplicar_filtro())
        self.cargar_categorias()

        # Barra de entrada manual de códigos de barras
        frame_codigo = tk.Frame(frame_derecha, bg=self.colors["bg_principal"])
        frame_codigo.pack(fill="x", pady=(0, 10))
        Label(frame_codigo, text="🏷️ Código de barras:", font="sans 13 bold", bg=self.colors["bg_principal"]).pack(side="left", padx=(0, 8))
        # Los botones se empaquetan antes que la entrada (por la derecha)
        # para que sea la entrada la que ceda espacio en ventanas estrechas.
        Button(
            frame_codigo, text="🏷️ Asignar", font="sans 12 bold",
            bg="#17A2B8", fg="white", command=self.asignar_codigo_seleccionado,
        ).pack(side="right", padx=(8, 0), ipadx=6, ipady=2)
        Button(
            frame_codigo, text="🔍 Buscar", font="sans 12 bold",
            bg="#000CFF", fg="white", command=self.buscar_por_codigo,
        ).pack(side="right", padx=(8, 0), ipadx=6, ipady=2)
        self.entry_busca_codigo = ttk.Entry(frame_codigo, font="sans 13", width=10)
        self.entry_busca_codigo.pack(side="left", fill="x", expand=True)
        self.entry_busca_codigo.bind("<Return>", lambda _evento: self.buscar_por_codigo())

        # Aviso de stock bajo (umbral configurable en Ajustes)
        self.lbl_stock_bajo = Label(
            frame_derecha, text="", font="sans 12 bold", anchor="w",
            bg=self.colors["bg_principal"],
        )
        self.lbl_stock_bajo.pack(fill="x", pady=(0, 6))

        treeFrame = Frame(frame_derecha, bg=self.colors["bg_tabla"])
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

        self.tre.tag_configure("bajo", background=self.colors["bg_stock_bajo"])
        self.tre.tag_configure("agotado", background=self.colors["bg_agotado"])

        self.tre.pack(expand=True, fill=BOTH)
        self.mostrar()

        frame_botones = tk.Frame(frame_derecha, bg=self.colors["bg_principal"])
        frame_botones.pack(fill="x", pady=(15, 0))
        btn_actualizar = Button(frame_botones, text="🔄 Actualizar inventario", bg="#000CFF", fg="white", font="sans 14 bold", command=self.actualizar_inventario)
        btn_actualizar.pack(side="left", expand=True, fill="x", padx=(0, 8), ipady=6)
        boton_eliminar = tk.Button(frame_botones, text="🗑️ Eliminar", font="sans 14 bold", bg="#C0392B", fg="white", command=self.eliminar_producto)
        boton_eliminar.pack(side="left", expand=True, fill="x", ipady=6)

        # Accesos rápidos a respaldo/restauración de la base de datos
        frame_bd = tk.Frame(frame_derecha, bg=self.colors["bg_principal"])
        frame_bd.pack(fill="x", pady=(8, 0))
        self.btn_exportar_bd = tk.Button(
            frame_bd, text="📤 Exportar base de datos…",
            font="sans 12 bold", bg="#28A745", fg="white",
            command=self.exportar_bd_rapido,
        )
        self.btn_exportar_bd.pack(side="left", expand=True, fill="x", padx=(0, 8), ipady=5)
        self.btn_importar_bd = tk.Button(
            frame_bd, text="📥 Importar base de datos…",
            font="sans 12 bold", bg="#0078D4", fg="white",
            command=self.importar_bd_rapido,
        )
        self.btn_importar_bd.pack(side="left", expand=True, fill="x", ipady=5)

    # ------------------------------------------------------------------
    # Respaldo / restauración rápida de la base de datos
    # ------------------------------------------------------------------
    def _ocupar_botones_bd(self, ocupado):
        estado = "disabled" if ocupado else "normal"
        self.btn_exportar_bd.config(
            state=estado,
            text="⏳ Exportando…" if ocupado else "📤 Exportar base de datos…",
        )
        self.btn_importar_bd.config(state=estado)

    def exportar_bd_rapido(self):
        """Exporta una copia .db completa eligiendo destino y nombre."""
        ruta = filedialog.asksaveasfilename(
            title="Exportar base de datos — SQLite",
            defaultextension=".db",
            initialfile=f"reyger_{datetime.now():%Y%m%d}.db",
            filetypes=[("Base de datos SQLite", "*.db")],
        )
        if not ruta:
            return

        # Aviso solo con WAL activo: es entonces cuando copiar el fichero a
        # mano produce una copia incompleta (los datos recientes siguen en
        # database.db-wal) y al restaurarla faltan tablas o la factura más
        # nueva. En modo delete una copia normal sería válida y el aviso
        # solo sería ruido. El texto vive en core.backup para que esta
        # ventana y la de Ajustes no diverjan.
        if wal_activo():
            if not messagebox.askyesno(
                "Exportar base de datos", AVISO_COPIA_MANUAL
            ):
                return

        def al_terminar(final, error):
            self._ocupar_botones_bd(False)
            if error is not None:
                messagebox.showerror(
                    "Exportar base de datos", f"No se pudo exportar: {error}"
                )
                return
            messagebox.showinfo(
                "Exportar base de datos",
                f"Exportación completada correctamente:\n{final}",
            )

        self._ocupar_botones_bd(True)
        en_hilo(self, lambda: exportar_sqlite(ruta), al_terminar)

    def importar_bd_rapido(self):
        """Importa un respaldo (.db/.xlsx/.zip) con confirmación previa."""
        filetypes = [
            ("Bases compatibles (*.db *.xlsx *.zip)",
             "*.db *.sqlite *.sqlite3 *.xlsx *.zip"),
            ("Base de datos SQLite", "*.db *.sqlite *.sqlite3"),
            ("Libro de Excel", "*.xlsx"),
            ("CSV comprimido", "*.zip"),
            ("Todos los ficheros", "*.*"),
        ]
        ruta = filedialog.askopenfilename(
            title="Importar base de datos", filetypes=filetypes
        )
        if not ruta:
            return

        aviso = (
            "Se SUSTITUIRÁ la base de datos completa por el fichero "
            "seleccionado."
            if os.path.splitext(ruta)[1].lower() in (".db", ".sqlite", ".sqlite3")
            else "Se sustituirá el CONTENIDO de las tablas incluidas en el "
                 "fichero seleccionado."
        )
        aviso += (
            "\n\nAntes se guardará automáticamente una copia de seguridad "
            "de la base actual.\n\n¿Desea continuar?"
        )
        if not messagebox.askyesno("Importar base de datos", aviso):
            return

        def al_terminar(resultado, error):
            self._ocupar_botones_bd(False)
            if error is not None:
                messagebox.showerror(
                    "Importar base de datos",
                    str(error) if isinstance(error, BackupError)
                    else f"No se pudo importar (no se cambió nada):\n{error}",
                )
                return
            messagebox.showinfo(
                "Importación completada",
                "Base de datos importada correctamente.\n\n"
                f"Copia de seguridad previa:\n{resultado.get('respaldo', '')}"
                "\n\n⚠️ Reinicie la aplicación para que todos los módulos "
                "vean los datos actualizados.",
            )

        self._ocupar_botones_bd(True)
        en_hilo(self, lambda: importar_datos(ruta), al_terminar)

    def cargar_proveedores(self):
        try:
            nombres = dominio.nombres_proveedores()
        except Exception:
            nombres = []
        self.proveedor["values"] = nombres

    def nuevo_proveedor(self):
        ventana = Toplevel(self)
        ventana.title("Nuevo proveedor")
        ventana.geometry("480x420")
        ventana.resizable(True, True)
        ventana.minsize(440, 380)
        ventana.config(bg=self.colors["bg_principal"])
        ventana.transient(self.winfo_toplevel())
        ventana.grab_set()

        campos = {}
        for fila, (clave, etiqueta) in enumerate([
            ("nombre", "Nombre *:"), ("cif", "CIF:"),
            ("contacto", "Contacto:"), ("telefono", "Teléfono:"),
            ("email", "Email:"),
        ]):
            Label(ventana, text=etiqueta, font="sans 13 bold", bg=self.colors["bg_principal"]).grid(
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
                dominio.crear_proveedor(
                    nombre,
                    campos["cif"].get().strip(),
                    campos["contacto"].get().strip(),
                    campos["telefono"].get().strip(),
                    campos["email"].get().strip(),
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
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(25, 10), ipady=4)
    
    def validacion(self, nombre, prov, precio, costo, stock):
        return dominio.validar_producto(nombre, prov, precio, costo, stock)

    _calcular_precio_venta = staticmethod(dominio.calcular_precio_venta)
    _calcular_margen = staticmethod(dominio.calcular_margen)
    _parse_float = staticmethod(dominio.parse_float)

    def _desde_costo_margen(self, *_):
        """Al cambiar coste o margen, recalcula el precio de venta."""
        if self._calculando:
            return
        costo = self._parse_float(self.costo_sv.get())
        margen = self._parse_float(self.margen_sv.get())
        if costo is None or costo < 0 or margen is None:
            return
        venta = self._calcular_precio_venta(costo, margen)
        self._calculando = True
        try:
            self.precio_sv.set(f"{venta:.2f}")
        finally:
            self._calculando = False

    def _desde_venta(self, *_):
        """Al cambiar el precio de venta, recalcula el margen obtenido."""
        if self._calculando:
            return
        costo = self._parse_float(self.costo_sv.get())
        venta = self._parse_float(self.precio_sv.get())
        if costo is None or venta is None or costo <= 0:
            return
        margen = self._calcular_margen(costo, venta)
        self._calculando = True
        try:
            self.margen_sv.set(f"{margen:.2f}")
        finally:
            self._calculando = False

    def _margen_actual(self):
        """Devuelve el margen a guardar: el indicado o el calculado."""
        margen = self._parse_float(self.margen_sv.get())
        if margen is not None:
            return round(margen, 2)
        costo = self._parse_float(self.costo_sv.get())
        venta = self._parse_float(self.precio_sv.get())
        if costo and venta:
            return round(self._calcular_margen(costo, venta), 2)
        return 0.0

    def cargar_categorias(self):
        try:
            nombres = gestor_categorias.nombres()
        except Exception:
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
        dialogo.config(bg=self.colors["bg_principal"])
        dialogo.transient(self.winfo_toplevel())
        dialogo.grab_set()

        Label(
            dialogo, text="Nombre de la categoría:",
            font="sans 13 bold", bg=self.colors["bg_principal"],
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
        dialogo = DialogoRegistroRapido(self, codigo)
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
            return gestor_categorias.nombres()
        except Exception:
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
        umbral = int(ConfigManager().get("umbral_stock_bajo", 5))
        avisos = {"bajo": 0, "agotado": 0}
        for elem in dominio.listar_productos(filtro_categoria):
            try:
                precio_eur = mod_moneda.format_currency(float(elem[3]), decimales=0) if elem[3] else ""
                costo_eur = mod_moneda.format_currency(float(elem[4]), decimales=0) if elem[4] else ""
            except ValueError:
                precio_eur = elem[3]
                costo_eur = elem[4]
            iva_txt = f"{elem[6]:g}%" if elem[6] is not None else ""
            categoria_txt = elem[7] if len(elem) > 7 and elem[7] else ""
            estado = dominio.estado_stock(elem[5], umbral)
            if estado:
                avisos[estado] += 1
            self.tre.insert(
                "", 0, text=elem[0],
                values=(elem[0], elem[1], elem[2], precio_eur, costo_eur, elem[5], iva_txt, categoria_txt),
                tags=(estado,) if estado else (),
            )
        self._mostrar_aviso_stock(avisos, umbral)

    def _mostrar_aviso_stock(self, avisos, umbral):
        if not hasattr(self, "lbl_stock_bajo"):
            return
        total = avisos["bajo"] + avisos["agotado"]
        if not total:
            self.lbl_stock_bajo.config(text="")
            return
        partes = []
        if avisos["agotado"]:
            partes.append(f"{avisos['agotado']} agotado{'s' if avisos['agotado'] != 1 else ''}")
        if avisos["bajo"]:
            partes.append(f"{avisos['bajo']} con {umbral} unidades o menos")
        self.lbl_stock_bajo.config(text="⚠️ Stock bajo: " + ", ".join(partes))
    
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

        valido, mensaje_error = self.validacion(nombre, prov, precio, costo, stock)
        if not valido:
            messagebox.showwarning(title="Error", message=mensaje_error)
            return
        if tipo_iva is not None:
            try:
                if codigo and dominio.codigo_en_uso(codigo):
                    messagebox.showwarning(
                        title="Código duplicado",
                        message=f"El código «{codigo}» ya está asignado a otro producto.",
                    )
                    return
                dominio.crear_producto(
                    nombre, prov, precio, costo, stock, tipo_iva,
                    self.categoria.get(), codigo, self._margen_actual(),
                )
                self.actualizar_inventario()
                self.nombre.delete(0, END)
                self.proveedor.delete(0, END)
                self.precio_sv.set("")
                self.costo_sv.set("")
                self.margen_sv.set("")
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
        
        db_row = dominio.obtener_producto(item_id)
        if db_row is None:
            messagebox.showwarning("Editar producto", "Producto no encontrado")
            return
        precio_original = db_row[0]
        costo_original = db_row[1]
        iva_original = f"{db_row[2]:g}%" if db_row[2] is not None else f"{IVA_POR_DEFECTO:g}%"
        categoria_actual = db_row[3]
        if db_row[5] is not None:
            margen_original = round(float(db_row[5]), 2)
        elif costo_original:
            margen_original = round(self._calcular_margen(
                float(costo_original), float(precio_original)), 2)
        else:
            margen_original = 0.0
        
        ventana_editar = Toplevel(self)
        ventana_editar.title("Editar producto")
        ventana_editar.geometry("520x620")
        ventana_editar.resizable(True, True)
        ventana_editar.minsize(480, 580)
        ventana_editar.config(bg=self.colors["bg_principal"])

        # Contenido con scroll vertical (el formulario de 10 filas puede
        # exceder la altura en pantallas pequeñas o con fuentes grandes)
        contenedor = tk.Frame(ventana_editar, bg=self.colors["bg_principal"])
        contenedor.pack(fill="both", expand=True, padx=10, pady=10)

        barra = ttk.Scrollbar(contenedor, orient="vertical")
        barra.pack(side="right", fill="y")

        lienzo = tk.Canvas(
            contenedor, bg=self.colors["bg_principal"], highlightthickness=0,
            yscrollcommand=barra.set,
        )
        lienzo.pack(side="left", fill="both", expand=True)
        barra.config(command=lienzo.yview)

        main_frame = tk.Frame(lienzo, bg=self.colors["bg_principal"])
        ventana_contenido = lienzo.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.bind(
            "<Configure>",
            lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")),
        )

        def _ajustar_ancho(evento):
            lienzo.itemconfigure(ventana_contenido, width=evento.width)

        lienzo.bind("<Configure>", _ajustar_ancho)

        def _rueda(evento):
            num = getattr(evento, "num", 0)
            delta = getattr(evento, "delta", 0)
            if num == 4 or delta > 0:
                lienzo.yview_scroll(-2, "units")
            elif num == 5 or delta < 0:
                lienzo.yview_scroll(2, "units")

        for secuencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            ventana_editar.bind(secuencia, _rueda)
        
        lbl_nombre = Label(main_frame, text="Nombre:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_nombre.grid(row=0, column=0, padx=10, pady=10)
        entry_nombre = Entry(main_frame, font="sans 14 bold")
        entry_nombre.grid(row=0, column=1, padx=10, pady=10)
        entry_nombre.insert(0, item_values[1])
        
        lbl_proveedor = Label(main_frame, text="Proveedor:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_proveedor.grid(row=1, column=0, padx=10, pady=10)
        entry_proveedor = Entry(main_frame, font="sans 14 bold")
        entry_proveedor.grid(row=1, column=1, padx=10, pady=10)
        entry_proveedor.insert(0, item_values[2])
        
        precio_sv = tk.StringVar(self)
        costo_sv = tk.StringVar(self)
        margen_sv = tk.StringVar(self)
        _calculando_edit = {"on": False}

        def _desde_costo_margen_edit(*_):
            if _calculando_edit["on"]:
                return
            costo = self._parse_float(costo_sv.get())
            margen = self._parse_float(margen_sv.get())
            if costo is None or costo < 0 or margen is None:
                return
            _calculando_edit["on"] = True
            try:
                precio_sv.set(f"{self._calcular_precio_venta(costo, margen):.2f}")
            finally:
                _calculando_edit["on"] = False

        def _desde_venta_edit(*_):
            if _calculando_edit["on"]:
                return
            costo = self._parse_float(costo_sv.get())
            venta = self._parse_float(precio_sv.get())
            if costo is None or venta is None or costo <= 0:
                return
            _calculando_edit["on"] = True
            try:
                margen_sv.set(f"{self._calcular_margen(costo, venta):.2f}")
            finally:
                _calculando_edit["on"] = False

        lbl_precio = Label(main_frame, text="Precio de venta:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_precio.grid(row=2, column=0, padx=10, pady=10)
        entry_precio = Entry(main_frame, font="sans 14 bold", textvariable=precio_sv)
        entry_precio.grid(row=2, column=1, padx=10, pady=10)
        precio_sv.set(f"{precio_original}" if precio_original is not None else "")
        precio_sv.trace_add("write", _desde_venta_edit)

        lbl_margen = Label(main_frame, text="Margen / ganancia (%):", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_margen.grid(row=3, column=0, padx=10, pady=10)
        entry_margen = Entry(main_frame, font="sans 14 bold", textvariable=margen_sv)
        entry_margen.grid(row=3, column=1, padx=10, pady=10)
        margen_sv.set(f"{margen_original}")
        margen_sv.trace_add("write", _desde_costo_margen_edit)

        lbl_costo = Label(main_frame, text="Precio de costo:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_costo.grid(row=4, column=0, padx=10, pady=10)
        entry_costo = Entry(main_frame, font="sans 14 bold", textvariable=costo_sv)
        entry_costo.grid(row=4, column=1, padx=10, pady=10)
        costo_sv.set(f"{costo_original}" if costo_original is not None else "")
        costo_sv.trace_add("write", _desde_costo_margen_edit)
        
        lbl_stock = Label(main_frame, text="Stock:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_stock.grid(row=5, column=0, padx=10, pady=10)
        entry_stock = Entry(main_frame, font="sans 14 bold")
        entry_stock.grid(row=5, column=1, padx=10, pady=10)
        entry_stock.insert(0, item_values[5])

        lbl_iva = Label(main_frame, text="IVA:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_iva.grid(row=6, column=0, padx=10, pady=10)
        combo_iva = ttk.Combobox(
            main_frame, font="sans 14 bold",
            values=[f"{tipo:g}%" for tipo in TIPOS_IVA],
        )
        combo_iva.set(iva_original)
        combo_iva.grid(row=6, column=1, padx=10, pady=10)

        lbl_categoria = Label(main_frame, text="Categoría:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_categoria.grid(row=7, column=0, padx=10, pady=10)
        frame_cat = tk.Frame(main_frame, bg=self.colors["bg_principal"])
        frame_cat.grid(row=7, column=1, padx=10, pady=10)
        combo_categoria = ttk.Combobox(
            frame_cat, font="sans 14 bold", state="readonly",
            values=[n for _, n in self._categorias_disponibles()],
        )
        combo_categoria.set(dominio.nombre_categoria(categoria_actual) or "General")
        combo_categoria.pack(side="left", fill="x", expand=True)
        btn_nueva_cat = tk.Button(
            frame_cat, text="➕", font="sans 13 bold",
            bg="#17A2B8", fg="white",
            command=lambda: self.crear_categoria_dialogo(combo_categoria),
        )
        btn_nueva_cat.pack(side="left", padx=(6, 0))

        lbl_codigo = Label(main_frame, text="Código de barras:", font="sans 14 bold", bg=self.colors["bg_principal"])
        lbl_codigo.grid(row=8, column=0, padx=10, pady=10)
        entry_codigo = Entry(main_frame, font="sans 14 bold")
        entry_codigo.grid(row=8, column=1, padx=10, pady=10)
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

            if precio < 0:
                messagebox.showwarning(
                    "Guardar cambios", "El precio de venta no puede ser negativo."
                )
                return
            if costo < 0:
                messagebox.showwarning(
                    "Guardar cambios", "El precio de costo no puede ser negativo."
                )
                return
            if stock < 0:
                messagebox.showwarning(
                    "Guardar cambios", "El stock no puede ser negativo."
                )
                return

            if codigo_nuevo and dominio.codigo_en_uso(codigo_nuevo, excluir_id=item_id):
                messagebox.showwarning(
                    "Guardar cambios",
                    f"El código «{codigo_nuevo}» ya está asignado a otro producto.",
                )
                return

            sum_margen = self._parse_float(margen_sv.get())
            if sum_margen is None and costo:
                sum_margen = self._calcular_margen(costo, precio)

            dominio.actualizar_producto(
                item_id, nombre, proveedor, precio, costo, stock, tipo_iva,
                categoria_elegida, codigo_nuevo,
                round(sum_margen, 2) if sum_margen is not None else 0.0,
            )
            self.actualizar_inventario()
            ventana_editar.destroy()

        btn_guardar = Button(main_frame, text="Guardar cambios", font="sans 14 bold", command=guardar_cambio)
        btn_guardar.grid(row=9, column=0, columnspan=2, padx=10, pady=(25, 10), ipady=4)

    def _categorias_disponibles(self):
        try:
            return gestor_categorias.listar()
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
                dominio.eliminar_producto(item_id)
                self.actualizar_inventario()
                messagebox.showinfo("Éxito", "Producto eliminado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar el producto: {e}")