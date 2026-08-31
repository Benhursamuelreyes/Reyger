from tkinter import *
from tkinter import ttk, messagebox
import tkinter as tk
import datetime
import os
import time

from . import business_profile as bp
from ..core import db
from ..core import moneda as mod_moneda
from ..resources import get_output_path, open_file, get_bundled_path
from ..config import ConfigManager
from ..core.hilos import en_hilo
from ..hardware.barcode_scanner import (
    CapturaEscanero,
    DialogoRegistroRapido,
    EscanerCodigoBarras,
)
from ..domain.fiscal import (
    IVA_POR_DEFECTO,
    desglose_linea,
    desglose_total,
)
from ..hardware.impresion_termica import (
    ANCHO_58MM,
    ANCHO_80MM,
    imprimir_ticket_venta,
)


def _resolver_logo(config):
    """Ruta del logo para el ticket: el personalizado o el integrado."""
    ruta = config.get("logo_path")
    if ruta and os.path.exists(ruta):
        return ruta
    integrado = get_bundled_path(os.path.join("assets", "img", "logo.png"))
    if os.path.exists(integrado):
        return integrado
    return None


class Ventas(tk.Frame):

    def __init__(self, padre):
        super().__init__(padre)
        self.productos_info = {}
        self.productos_por_categoria = {}
        self.config_manager = ConfigManager()
        self.escaner = EscanerCodigoBarras()
        self.captura = CapturaEscanero(self.winfo_toplevel(), self._procesar_codigo)
        self._ult_codigo = None
        self._ult_momento = 0.0
        self.crear_tabla_ventas()
        self.numero_factura_actual = self.obtener_numero_factura_actual()
        self.widgets()
        self.mostrar_numero_factura()
        if self.var_escaner.get():
            self.captura.iniciar()

    def crear_tabla_ventas(self):
        try:
            conn = db.get_connection()
            conn.execute("""
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
            conn.commit()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo crear la tabla ventas: {e}")

    def widgets(self):
        frame1 = tk.Frame(self, bg="#dddddd", highlightbackground="gray", highlightthickness=3)
        frame1.pack(fill="x")
        titulo = tk.Label(frame1, text="VENTAS", bg="#dddddd", font="sans 30 bold", anchor="center")
        titulo.pack(fill="both", expand=True)

        frame2 = tk.Frame(self, bg="#C6D9E3", highlightbackground="gray", highlightthickness=3)
        frame2.pack(fill="both", expand=True)

        lblframe = LabelFrame(frame2, text="Información de la venta", bg="#C6D9E3", font="sans 16 bold")
        lblframe.pack(fill="x", padx=10, pady=10)

        nFactura = tk.Label(lblframe, text="Num.factura: ", bg="#C6D9E3", font="sans 14 bold")
        nFactura.grid(row=0, column=0, padx=(10, 0), pady=12, sticky="w")

        self.numero_factura = tk.StringVar()
        self.entry_numero_factura = ttk.Entry(lblframe, textvariable=self.numero_factura, state="readonly", font="sans 12 bold", width=10)
        self.entry_numero_factura.grid(row=0, column=1, padx=6, sticky="w")

        label_nombre = tk.Label(lblframe, text="Productos: ", bg="#C6D9E3", font="sans 14 bold")
        label_nombre.grid(row=0, column=2, padx=(20, 0), sticky="w")

        self.entry_nombre = ttk.Combobox(lblframe, font="sans 14 bold", state="readonly")
        self.entry_nombre.grid(row=0, column=3, padx=6, sticky="ew")
        self.entry_nombre.bind("<<ComboboxSelected>>", self.actualizar_precio)
        self.cargar_productos()

        label_valor = tk.Label(lblframe, text="Precio de venta: ", bg="#C6D9E3", font="sans 14 bold")
        label_valor.grid(row=0, column=4, padx=(20, 0), sticky="w")

        self.entry_valor = ttk.Entry(lblframe, font="sans 14 bold", state="readonly", width=16)
        self.entry_valor.grid(row=0, column=5, padx=6, sticky="w")

        label_cantidad = tk.Label(lblframe, text="Cantidad: ", bg="#C6D9E3", font="sans 14 bold")
        label_cantidad.grid(row=0, column=6, padx=(20, 0), sticky="w")

        self.entry_cantidad = ttk.Entry(lblframe, font="sans 14 bold", width=8)
        self.entry_cantidad.grid(row=0, column=7, padx=(6, 10), sticky="w")

        label_cliente = tk.Label(lblframe, text="Cliente (opcional): ", bg="#C6D9E3", font="sans 14 bold")
        label_cliente.grid(row=1, column=0, padx=(10, 0), pady=(0, 12), sticky="w")

        self.combo_cliente = ttk.Combobox(lblframe, font="sans 12", state="readonly", width=38)
        self.combo_cliente.grid(row=1, column=1, columnspan=4, padx=6, pady=(0, 12), sticky="w")
        self.cargar_clientes_venta()

        # Barra de entrada manual de códigos de barras (scanner o teclado)
        label_codigo = tk.Label(lblframe, text="🏷️ Código: ", bg="#C6D9E3", font="sans 14 bold")
        label_codigo.grid(row=1, column=5, padx=(20, 0), pady=(0, 12), sticky="w")

        self.entry_codigo_barras = ttk.Entry(lblframe, font="sans 14 bold", width=22)
        self.entry_codigo_barras.grid(row=1, column=6, columnspan=2, padx=6, pady=(0, 12), sticky="w")
        self.entry_codigo_barras.bind("<Return>", self._desde_barra)

        lblframe.columnconfigure(3, weight=1)

        frame_categorias = tk.Frame(frame2, bg="#C6D9E3")
        frame_categorias.pack(fill="x", padx=10)
        tk.Label(frame_categorias, text="Categorías:", bg="#C6D9E3", font="sans 12 bold").pack(side="left", padx=(0, 8))
        self.frame_botones_categoria = frame_categorias
        self.crear_botones_categorias()

        treFrame = tk.Frame(frame2, bg="#C6D9E3")
        treFrame.pack(fill="both", expand=True, padx=150, pady=10)

        scrol_y = ttk.Scrollbar(treFrame, orient=VERTICAL)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_x = ttk.Scrollbar(treFrame, orient=HORIZONTAL)
        scrol_x.pack(side=BOTTOM, fill=X)

        self.tree = ttk.Treeview(treFrame, columns=("producto", "Precio", "Cantidad", "IVA", "Subtotal"), show="headings", height=10, yscrollcommand=scrol_y.set, xscrollcommand=scrol_x.set)
        scrol_y.config(command=self.tree.yview)
        scrol_x.config(command=self.tree.xview)

        self.tree.heading("producto", text="Producto")
        self.tree.heading("Precio", text="P. venta")
        self.tree.heading("Cantidad", text="Cantidad")
        self.tree.heading("IVA", text="IVA")
        self.tree.heading("Subtotal", text="Subtotal")

        self.tree.column("producto", anchor="center")
        self.tree.column("Precio", anchor="center")
        self.tree.column("Cantidad", anchor="center")
        self.tree.column("IVA", anchor="center", width=80)
        self.tree.column("Subtotal", anchor="center")

        self.tree.pack(expand=True, fill=BOTH)

        frame_total = tk.Frame(frame2, bg="#C6D9E3")
        frame_total.pack(fill="x", padx=20)
        self.label_base = tk.Label(frame_total, text=f"Base imponible: {mod_moneda.format_currency(0)}", bg="#C6D9E3", font="sans 13")
        self.label_base.pack(anchor="e")
        self.label_cuota = tk.Label(frame_total, text=f"Cuota IVA: {mod_moneda.format_currency(0)}", bg="#C6D9E3", font="sans 13")
        self.label_cuota.pack(anchor="e")
        self.label_suma_total = tk.Label(frame_total, text=f"Total a pagar: {mod_moneda.format_currency(0)}", bg="#C6D9E3", font="sans 25 bold")
        self.label_suma_total.pack(anchor="e")

        lblframe1 = LabelFrame(frame2, text="Opciones", bg="#C6D9E3", font="sans 14 bold")
        lblframe1.pack(fill="x", padx=10, pady=10)

        # Interruptor de escáner (persistente en config.json)
        self.var_escaner = tk.BooleanVar(
            value=bool(self.config_manager.get("escaner_activo", False))
        )
        self.toggle_escaner = tk.Checkbutton(
            lblframe1,
            variable=self.var_escaner,
            command=self._alternar_escaner,
            indicatoron=False,
            selectcolor="#C6D9E3",
            font="sans 13 bold",
            relief="ridge",
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.toggle_escaner.pack(side="left", padx=(10, 20), pady=10)
        self._pintar_toggle()

        boton_agregar = tk.Button(lblframe1, text="Agregar artículo", bg="#000CFF", fg="white", font="sans 14 bold", command=self.registrar)
        boton_agregar.pack(side="left", expand=True, fill="x", padx=10, pady=10, ipady=6)

        boton_pagar = tk.Button(lblframe1, text="Pagar", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_paga)
        boton_pagar.pack(side="left", expand=True, fill="x", padx=10, pady=10, ipady=6)

        boton_ver_factura = tk.Button(lblframe1, text="Ver Factura", bg="#000CFF", fg="white", font="sans 14 bold", command=self.abrir_ventana_factura)
        boton_ver_factura.pack(side="left", expand=True, fill="x", padx=10, pady=10, ipady=6)

        boton_cierre = tk.Button(lblframe1, text="Cierre de Caja", bg="#8B6914", fg="white", font="sans 14 bold", command=self.abrir_cierre_caja)
        boton_cierre.pack(side="left", expand=True, fill="x", padx=10, pady=10, ipady=6)

    def cargar_productos(self):
        try:
            filas = db.query(
                "SELECT i.nombre, i.precio, i.tipo_iva, COALESCE(c.nombre, 'General') "
                "FROM inventario i LEFT JOIN categorias c ON c.id = i.categoria_id"
            )
            nombres = []
            self.productos_info = {}
            self.productos_por_categoria = {}
            for fila in filas:
                nombre, precio, tipo_iva, categoria = fila["nombre"], fila["precio"], fila["tipo_iva"], fila[3]
                nombres.append(nombre)
                self.productos_info[nombre] = (
                    float(precio),
                    float(tipo_iva) if tipo_iva is not None else IVA_POR_DEFECTO,
                )
                self.productos_por_categoria.setdefault(categoria, []).append(nombre)
            self.entry_nombre["values"] = nombres
            if hasattr(self, "botones_categoria"):
                self.filtrar_por_categoria("Todos")
            if not nombres:
                print("Advertencia: La base de datos no contiene productos registrados")
        except Exception as ex:
            print(f"Error inesperado: {ex}")

    def _categorias_disponibles(self):
        try:
            filas = db.query(
                "SELECT nombre FROM categorias ORDER BY CASE WHEN nombre = 'General' THEN 0 ELSE 1 END, nombre"
            )
            return [fila["nombre"] for fila in filas]
        except Exception:
            return ["General"]

    def crear_botones_categorias(self):
        self.botones_categoria = {}
        for nombre in ["Todos"] + self._categorias_disponibles():
            btn = tk.Button(
                self.frame_botones_categoria, text=nombre, font="sans 11 bold",
                bg="#17A2B8", fg="white", relief="flat", cursor="hand2",
                command=lambda n=nombre: self.filtrar_por_categoria(n),
            )
            btn.pack(side="left", padx=(0, 6), pady=(0, 8), ipadx=8, ipady=3)
            self.botones_categoria[nombre] = btn
        self.filtrar_por_categoria("Todos")

    def filtrar_por_categoria(self, categoria):
        if categoria == "Todos":
            valores = list(self.productos_info.keys())
        else:
            valores = list(self.productos_por_categoria.get(categoria, []))
        self.entry_nombre["values"] = valores
        if self.entry_nombre.get() not in valores:
            self.entry_nombre.set("")
            self.entry_valor.config(state="normal")
            self.entry_valor.delete(0, tk.END)
            self.entry_valor.config(state="readonly")
        for nombre, btn in getattr(self, "botones_categoria", {}).items():
            btn.config(bg="#000CFF" if nombre == categoria else "#17A2B8")

    def cargar_clientes_venta(self):
        try:
            filas = db.query("SELECT nombre FROM clientes ORDER BY nombre")
            nombres = ["(Sin cliente)"] + [fila["nombre"] for fila in filas]
            self.combo_cliente["values"] = nombres
            self.combo_cliente.current(0)
        except Exception:
            self.combo_cliente["values"] = ["(Sin cliente)"]
            self.combo_cliente.current(0)

    def _tipo_iva_de(self, producto):
        info = self.productos_info.get(producto)
        return info[1] if info else IVA_POR_DEFECTO

    def actualizar_precio(self, event):
        nombre_producto = self.entry_nombre.get()
        try:
            fila = db.query_one("SELECT precio FROM inventario WHERE nombre = ?", (nombre_producto,))
            if fila:
                self.entry_valor.config(state="normal")
                self.entry_valor.delete(0, tk.END)
                self.entry_valor.insert(0, fila["precio"])
                self.entry_valor.config(state="readonly")
            else:
                self.entry_valor.config(state="normal")
                self.entry_valor.delete(0, tk.END)
                self.entry_valor.insert(0, "Precio no disponible")
                self.entry_valor.config(state="readonly")
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener el precio: {e}")

    def _lineas_carrito(self):
        """Devuelve las líneas del carrito como tuplas numéricas."""
        lineas = []
        for child in self.tree.get_children():
            valores = self.tree.item(child, "values")
            precio = float(valores[1])
            cantidad = int(valores[2])
            tipo_iva = float(str(valores[3]).replace("%", ""))
            subtotal = float(valores[4])
            lineas.append((producto := valores[0], precio, cantidad, tipo_iva, subtotal))
        return lineas

    def actualizar_total(self):
        lineas = [
            (precio, cantidad, tipo_iva)
            for _, precio, cantidad, tipo_iva, _ in self._lineas_carrito()
        ]
        total, base, cuota = desglose_total(lineas)
        self.label_base.config(text=f"Base imponible: {mod_moneda.format_currency(base)}")
        self.label_cuota.config(text=f"Cuota IVA: {mod_moneda.format_currency(cuota)}")
        self.label_suma_total.config(text=f"Total a pagar: {mod_moneda.format_currency(total)}")

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

            tipo_iva = self._tipo_iva_de(producto)
            subtotal = round(cantidad * precio, 2)
            self.tree.insert(
                "", "end",
                values=(producto, f"{precio:.2f}", cantidad, f"{tipo_iva:g}%", f"{subtotal:.2f}"),
            )

            self.entry_nombre.set("")
            self.entry_valor.config(state="normal")
            self.entry_valor.delete(0, tk.END)
            self.entry_valor.config(state="readonly")
            self.entry_cantidad.delete(0, tk.END)

            self.actualizar_total()
        except ValueError:
            messagebox.showerror("Error", "Cantidad o precio no válidos. Asegúrese de ingresar números válidos")

    # ------------------------------------------------------------------
    # Escáner de códigos de barras
    # ------------------------------------------------------------------

    def _pintar_toggle(self):
        if self.var_escaner.get():
            self.toggle_escaner.config(
                text="🟢 Escáner ACTIVO", bg="#27AE60", fg="white",
                selectcolor="#27AE60",
                activebackground="#27AE60", activeforeground="white",
            )
        else:
            self.toggle_escaner.config(
                text="⚫ Escáner INACTIVO", bg="#B0BEC5", fg="black",
                selectcolor="#B0BEC5",
                activebackground="#B0BEC5", activeforeground="black",
            )

    def _alternar_escaner(self):
        activo = self.var_escaner.get()
        self.config_manager.set("escaner_activo", activo)
        if activo:
            self.captura.iniciar()
            self.entry_codigo_barras.focus_set()
        else:
            self.captura.detener()
        self._pintar_toggle()

    def _desde_barra(self, _evento=None):
        """Entrada manual desde el campo de código (scanner apuntado o teclado)."""
        codigo = self.entry_codigo_barras.get().strip()
        if not codigo:
            return
        self.entry_codigo_barras.delete(0, tk.END)
        self._procesar_codigo(codigo)

    def _procesar_codigo(self, codigo):
        """Busca el código y añade el producto al carrito.

        Si el código no está registrado ofrece darlo de alta al vuelo;
        un anti-doble-disparo ignora repeticiones del mismo código en
        menos de 1.5 s (el scanner y el Enter del campo pueden solaparse).
        """
        ahora = time.monotonic()
        if (
            self._ult_codigo == codigo
            and (ahora - self._ult_momento) < 1.5
        ):
            return
        self._ult_codigo, self._ult_momento = codigo, ahora

        producto = self.escaner.buscar_producto_por_codigo(codigo)
        if producto is None:
            registrar = messagebox.askyesno(
                "Código no registrado",
                f"El código «{codigo}» no está registrado en el inventario.\n"
                "¿Desea registrar un producto nuevo con él?",
                parent=self,
            )
            if not registrar:
                return
            dialogo = DialogoRegistroRapido(self, codigo)
            producto = dialogo.resultado
            if producto is None:
                return
            self.cargar_productos()

        cantidad_texto = self.entry_cantidad.get().strip()
        try:
            cantidad = int(cantidad_texto) if cantidad_texto else 1
        except ValueError:
            cantidad = 1
        if cantidad < 1:
            cantidad = 1

        if not self.validar_stock(producto["nombre"], cantidad):
            messagebox.showerror(
                "Stock insuficiente",
                f"No hay stock suficiente de «{producto['nombre']}».",
                parent=self,
            )
            return

        tipo_iva = self._tipo_iva_de(producto["nombre"])
        subtotal = round(cantidad * float(producto["precio"]), 2)
        self.tree.insert(
            "", "end",
            values=(
                producto["nombre"],
                f"{float(producto['precio']):.2f}",
                cantidad,
                f"{tipo_iva:g}%",
                f"{subtotal:.2f}",
            ),
        )
        self.actualizar_total()

        if self.var_escaner.get():
            self.entry_codigo_barras.focus_set()

    def validar_stock(self, nombre_producto, cantidad):
        try:
            fila = db.query_one("SELECT stock FROM inventario WHERE nombre = ?", (nombre_producto,))
            if fila and fila["stock"] >= cantidad:
                return True
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Error al validar el stock: {e}")
            return False

    def obtener_total(self):
        total = 0.0
        for child in self.tree.get_children():
            subtotal = float(self.tree.item(child, "values")[4])
            total += subtotal
        return round(total, 2)

    def _actualizar_campos_pago(self, var_metodo, label_efe=None, entry_efe=None, label_tar=None, entry_tar=None):
        if label_efe is None:
            return
        metodo = var_metodo.get()
        if metodo == "Efectivo":
            label_efe.grid()
            entry_efe.grid()
            label_tar.grid_remove()
            entry_tar.grid_remove()
        elif metodo == "Tarjeta":
            label_efe.grid_remove()
            entry_efe.grid_remove()
            label_tar.grid()
            entry_tar.grid()
        else:
            label_efe.grid()
            entry_efe.grid()
            label_tar.grid()
            entry_tar.grid()

    def abrir_ventana_paga(self):
        if not self.tree.get_children():
            messagebox.showerror("Error", "No hay artículos para pagar")
            return

        ventana_pago = tk.Toplevel(self)
        ventana_pago.title("Realizar pago")
        ventana_pago.geometry("560x700")
        ventana_pago.config(bg="#C5D9E3")
        ventana_pago.resizable(True, True)
        ventana_pago.minsize(560, 700)

        total = self.obtener_total()
        lineas = [
            (precio, cantidad, tipo_iva)
            for _, precio, cantidad, tipo_iva, _ in self._lineas_carrito()
        ]
        _, base, cuota = desglose_total(lineas)
        label_total = tk.Label(
            ventana_pago, bg="#C6D9E3",
            text=(f"Total a pagar: {mod_moneda.format_currency(total)}\n"
                  f"Base imponible: {mod_moneda.format_currency(base)}   |   "
                  f"Cuota IVA: {mod_moneda.format_currency(cuota)}"),
            font="sans 16 bold", justify="left",
        )
        label_total.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))

        label_metodo = tk.Label(ventana_pago, bg="#C6D9E3", text="Método de pago:", font="sans 14 bold")
        label_metodo.grid(row=1, column=0, sticky="w", padx=20, pady=10)

        var_metodo = tk.StringVar(value="Efectivo")

        def actualizar_campos():
            self._actualizar_campos_pago(var_metodo, label_efectivo, entry_efectivo, label_tarjeta, entry_tarjeta)

        frame_radios = tk.Frame(ventana_pago, bg="#C6D9E3")
        frame_radios.grid(row=2, column=0, sticky="w", padx=20)

        radio_efectivo = tk.Radiobutton(frame_radios, text="Efectivo", variable=var_metodo, value="Efectivo", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_efectivo.pack(side="left", padx=(0, 30))

        radio_tarjeta = tk.Radiobutton(frame_radios, text="Tarjeta", variable=var_metodo, value="Tarjeta", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_tarjeta.pack(side="left", padx=(0, 30))

        radio_mixto = tk.Radiobutton(frame_radios, text="Mixto", variable=var_metodo, value="Mixto", bg="#C6D9E3", font="sans 12 bold", command=actualizar_campos)
        radio_mixto.pack(side="left")

        label_efectivo = tk.Label(ventana_pago, bg="#C6D9E3", text="Cantidad en efectivo:", font="sans 12 bold")
        label_efectivo.grid(row=3, column=0, sticky="w", padx=20, pady=(15, 2))
        entry_efectivo = ttk.Entry(ventana_pago, font="sans 12 bold")
        entry_efectivo.grid(row=4, column=0, sticky="ew", padx=20)

        label_tarjeta = tk.Label(ventana_pago, bg="#C6D9E3", text="Cantidad en tarjeta:", font="sans 12 bold")
        label_tarjeta.grid(row=5, column=0, sticky="w", padx=20, pady=(15, 2))
        entry_tarjeta = ttk.Entry(ventana_pago, font="sans 12 bold")
        entry_tarjeta.grid(row=6, column=0, sticky="ew", padx=20)
        label_tarjeta.grid_remove()
        entry_tarjeta.grid_remove()

        label_cambio = tk.Label(ventana_pago, bg="#C6D9E3", text="", font="sans 14 bold", fg="#27AE60")
        label_cambio.grid(row=7, column=0, sticky="w", padx=20, pady=15)

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
                    label_cambio.config(text=f"Vuelto: {mod_moneda.format_currency(cambio)}")
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
                    label_cambio.config(text=f"Vuelto: {mod_moneda.format_currency(cambio)} (del efectivo)")
            except ValueError:
                messagebox.showerror("Error", "Ingrese valores numericos validos")

        boton_calcular = tk.Button(ventana_pago, text="Calcular", bg="#0078D4", fg="white", font="sans 12 bold", command=calcular_cambio)
        boton_calcular.grid(row=8, column=0, sticky="ew", padx=20, pady=10, ipady=4)

        boton_pagar = tk.Button(ventana_pago, text="Confirmar pago", bg="#27AE60", fg="white", font="sans 14 bold", command=lambda: self.pagar(ventana_pago, entry_efectivo, entry_tarjeta, var_metodo, label_cambio, total))
        boton_pagar.grid(row=9, column=0, sticky="ew", padx=20, pady=10, ipady=6)

        boton_cancelar = tk.Button(ventana_pago, text="Cancelar", bg="#C0392B", fg="white", font="sans 12 bold", command=ventana_pago.destroy)
        boton_cancelar.grid(row=10, column=0, sticky="ew", padx=20, pady=(10, 20), ipady=4)

        ventana_pago.columnconfigure(0, weight=1)

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

            cliente_nombre = self.combo_cliente.get()
            cliente_id = None
            if cliente_nombre and cliente_nombre != "(Sin cliente)":
                fila_cliente = db.query_one(
                    "SELECT id FROM clientes WHERE nombre = ?", (cliente_nombre,)
                )
                cliente_id = fila_cliente["id"] if fila_cliente else None

            productos = []
            lineas_fiscales = []

            with db.transaccion() as conn:
                for i in self.tree.get_children():
                    item = self.tree.item(i, "values")
                    producto = item[0]
                    precio = float(item[1])
                    cantidad_vendida = int(item[2])
                    tipo_iva = float(str(item[3]).replace("%", ""))
                    subtotal_linea, base_linea, cuota_linea = desglose_linea(
                        precio, cantidad_vendida, tipo_iva
                    )
                    productos.append((
                        producto, precio, cantidad_vendida, subtotal_linea,
                        tipo_iva, base_linea, cuota_linea,
                    ))
                    lineas_fiscales.append((precio, cantidad_vendida, tipo_iva))

                    conn.execute("""
                        INSERT INTO ventas (factura, nombre_articulo, valor_articulo,
                            cantidad, subtotal, metodo_pago, cantidad_efectivo,
                            cantidad_tarjeta, cliente_id, tipo_iva, cuota_iva,
                            base_imponible)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.numero_factura_actual, producto, precio,
                        cantidad_vendida, subtotal_linea, metodo_pago,
                        cantidad_efectivo, cantidad_tarjeta, cliente_id,
                        tipo_iva, cuota_linea, base_linea,
                    ))

                    conn.execute("UPDATE inventario SET stock = stock - ? WHERE nombre = ?", (cantidad_vendida, producto))

                total, base_total, cuota_total = desglose_total(lineas_fiscales)
                numero_factura_emitida = self.numero_factura_actual
                messagebox.showinfo("Exito", f"La venta se ha completado\nMetodo de pago: {metodo_pago}")
                self.numero_factura_actual += 1
                self.mostrar_numero_factura()

                for i in self.tree.get_children():
                    self.tree.delete(i)
                self.label_base.config(text=f"Base imponible: {mod_moneda.format_currency(0)}")
                self.label_cuota.config(text=f"Cuota IVA: {mod_moneda.format_currency(0)}")
                self.label_suma_total.config(text=f"Total a pagar: {mod_moneda.format_currency(0)}")
                self.combo_cliente.current(0)
                ventana_pago.destroy()

                fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                self.generar_factura_pdf(
                    productos, total, numero_factura_emitida, fecha, metodo_pago,
                    base_imponible=base_total, cuota_iva=cuota_total,
                    cliente_nombre=None if cliente_id is None else cliente_nombre,
                )
                self._registrar_verifactu(
                    numero_factura_emitida, fecha, productos, total,
                    base_total, cuota_total,
                    nif_receptor=None, nombre_receptor=None if cliente_id is None else cliente_nombre,
                )
                self._imprimir_ticket_termico(
                    numero_factura_emitida, fecha, productos, total,
                    base_total, cuota_total, metodo_pago,
                    None if cliente_id is None else cliente_nombre,
                )
        except ValueError:
            messagebox.showerror("Error", "Valores ingresados no validos")

    def _imprimir_ticket_termico(self, numero_factura, fecha, productos, total,
                                 base, cuota, metodo_pago, cliente):
        """Imprime el ticket térmico si hay una impresora configurada.

        El envío al spooler/subproceso puede tardar segundos: corre en
        hilo demonio y el aviso vuelve por ``after`` si falla.
        """
        config = ConfigManager()
        impresora = config.get("impresora_termica")
        if not impresora:
            return
        ancho = ANCHO_58MM if config.get("ancho_ticket") == 58 else ANCHO_80MM
        letra = config.get("letra_ticket", "muy_grande")
        empresa = bp.nombre_empresa()
        logo = _resolver_logo(config)
        negocio = {
            "nombre": bp.obtener_campo("nombre"),
            "nombre_comercial": bp.obtener_campo("nombre_comercial"),
            "nif": bp.obtener_campo("nif"),
            "direccion": bp.obtener_campo("direccion"),
            "codigo_postal": bp.obtener_campo("codigo_postal"),
            "provincia": bp.obtener_campo("provincia"),
            "telefono": bp.obtener_campo("telefono"),
            "email": bp.obtener_campo("email"),
        }

        def trabajo():
            return imprimir_ticket_venta(
                numero_factura, fecha, productos, total, base, cuota,
                metodo_pago, cliente, empresa=empresa, ancho=ancho,
                letra=letra, impresora=impresora, logo=logo, negocio=negocio,
            )

        def al_terminar(resultado, error):
            if error is not None:
                messagebox.showwarning(
                    "Impresora térmica", f"No se pudo imprimir: {error}"
                )
                return
            ok, mensaje = resultado
            if not ok:
                messagebox.showwarning("Impresora térmica", mensaje)

        en_hilo(self, trabajo, al_terminar)

    def _registrar_verifactu(self, numero_factura, fecha, productos, total,
                             base_imponible, cuota_iva, nif_receptor,
                             nombre_receptor):
        """Registra la factura en facturas_verifactu con cadena hash AEAT."""
        try:
            from ..domain import facturas_verifactu as fv_mod
            from . import business_profile as bp

            generador = fv_mod.FacturaVeriFACTU()
            nif_emisor = bp.nif() or ""
            nif_rec = nif_receptor or ""
            nombre_rec = nombre_receptor or "(Consumidor final)"

            productos_dict = [
                {
                    "nombre_articulo": p[0],
                    "valor_articulo": p[1],
                    "cantidad": p[2],
                    "subtotal": p[3],
                }
                for p in productos
            ]

            generador.guardar_datos_factura_db(
                numero_factura=numero_factura,
                fecha=fecha,
                nif_emisor=nif_emisor,
                nif_receptor=nif_rec,
                nombre_receptor=nombre_rec,
                base_imponible=base_imponible,
                tipo_iva=IVA_POR_DEFECTO,
                total_iva=cuota_iva,
                total=total,
                productos=productos_dict,
            )
        except Exception:
            pass

    def generar_factura_pdf(self, productos, total, factura_numero, fecha,
                            metodo_pago="Efectivo", base_imponible=None,
                            cuota_iva=None, cliente_nombre=None):
        """Genera la factura en PDF A4 estandarizado con membrete del negocio.

        Las facturas NO se envían a la impresora térmica de tickets: se
        generan en PDF A4 (misma plantilla que albaranes y presupuestos) y
        se abren en el visor del sistema para su impresión estándar.
        """
        from ..domain.pdf_documento import PdfDocumento

        pdf = PdfDocumento(self.config_manager)
        pdf_dir = get_output_path("facturas")
        archivo_pdf = os.path.join(pdf_dir, f"factura_{factura_numero}.pdf")

        productos_tabla = []
        for p in productos:
            nombre = p[0]
            precio = p[1]
            cantidad = p[2]
            subtotal = p[3]
            productos_tabla.append({
                "nombre_articulo": nombre,
                "valor_articulo": precio,
                "cantidad": cantidad,
                "subtotal": subtotal,
            })

        pdf.generar(
            output_path=archivo_pdf,
            titulo_documento=bp.nombre_empresa(),
            subtitulo_documento="FACTURA",
            numero=str(factura_numero),
            fecha=fecha,
            cliente_nombre=cliente_nombre or "(Consumidor final)",
            productos=productos_tabla,
            base_imponible=base_imponible,
            tipo_iva=IVA_POR_DEFECTO,
            total_iva=cuota_iva,
            total=total,
            observaciones=f"Forma de pago: {metodo_pago}",
            campos_firma=False,
            pie_legal=(
                "<i>Esta factura cumple con los requisitos del artículo 34 de "
                "la Ley 37/1992, de 28 de diciembre, del Impuesto sobre el "
                "Valor Añadido. Registro de Facturas disponible en la empresa.</i>"
            ),
        )

        impresora_facturas = self.config_manager.get("impresora_facturas")
        if impresora_facturas:
            try:
                from ..resources import print_file
                print_file(archivo_pdf, impresora_facturas)
                messagebox.showinfo(
                    "Factura generada",
                    f"La factura #{factura_numero} se ha impreso en '{impresora_facturas}'.\n"
                    f"Archivo PDF: {archivo_pdf}",
                )
            except Exception:
                messagebox.showinfo(
                    "Factura generada",
                    f"La factura #{factura_numero} ha sido creada exitosamente en:\n{archivo_pdf}",
                )
        else:
            try:
                open_file(archivo_pdf)
            except Exception:
                messagebox.showinfo(
                    "Factura generada",
                    f"La factura #{factura_numero} ha sido creada exitosamente en:\n{archivo_pdf}",
                )

    def obtener_numero_factura_actual(self):
        try:
            fila = db.query_one("SELECT IFNULL(MAX(factura), 0) AS max_factura FROM ventas")
            return fila["max_factura"] + 1
        except Exception as e:
            messagebox.showerror("Error", f"Error al obtener el número de factura: {e}")
            return 1

    def mostrar_numero_factura(self):
        self.numero_factura.set(self.numero_factura_actual)

    def abrir_ventana_factura(self):
        ventana_facturas = tk.Toplevel(self)
        ventana_facturas.title("Facturas")
        ventana_facturas.geometry("1000x620")
        ventana_facturas.config(bg="#C6D9E3")
        ventana_facturas.resizable(True, True)
        ventana_facturas.minsize(800, 500)

        facturas_label = tk.Label(ventana_facturas, bg="#C6D9E3", text="Facturas registradas", font="sans 36 bold")
        facturas_label.pack(pady=15)

        treFrame = tk.Frame(ventana_facturas, bg="#C6D9E3")
        treFrame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
        tree_facturas.heading("Precio", text="P. venta")
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

        frame_botones = tk.Frame(ventana_facturas, bg="#C6D9E3")
        frame_botones.pack(fill="x", padx=10, pady=(0, 15))

        btn_reimprimir = tk.Button(
            frame_botones,
            text="🧾 Reimprimir ticket seleccionado",
            bg="#0078D4",
            fg="white",
            font="sans 12 bold",
            padx=15,
            pady=8,
            command=lambda: self._reimprimir_ticket(tree_facturas),
        )
        btn_reimprimir.pack(side="left", padx=5)

    def _reimprimir_ticket(self, tree):
        """Reimprime en la térmica configurada el ticket de una venta previa."""
        seleccion = tree.selection()
        if not seleccion:
            messagebox.showwarning(
                "Reimprimir ticket",
                "Seleccione una línea de la venta a reimprimir.",
            )
            return
        valores = tree.item(seleccion[0], "values")
        if not valores:
            return
        numero_factura = valores[1]
        try:
            numero_factura = int(numero_factura)
        except (TypeError, ValueError):
            messagebox.showerror("Error", "Número de factura no válido.")
            return

        filas = db.query(
            "SELECT * FROM ventas WHERE factura = ? "
            "ORDER BY id ASC",
            (numero_factura,),
        )
        if not filas:
            messagebox.showwarning(
                "Reimprimir ticket",
                f"No hay líneas para la factura #{numero_factura}.",
            )
            return

        productos = []
        total = 0.0
        base = None
        cuota = None
        metodo_pago = "Efectivo"
        fecha = None
        cliente = "(Consumidor final)"
        primera = dict(filas[0])
        metodo_pago = primera.get("metodo_pago") or "Efectivo"
        fecha = primera.get("fecha")
        cliente_id = primera.get("cliente_id")
        base = primera.get("base_imponible")
        cuota = primera.get("cuota_iva")
        for fila in filas:
            f = dict(fila)
            productos.append((
                f.get("nombre_articulo") or "",
                f.get("valor_articulo") or 0.0,
                f.get("cantidad") or 0,
                f.get("subtotal") or 0.0,
            ))
        total = sum(p[3] for p in productos)
        if fecha is None:
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if cliente_id is not None:
            try:
                cfila = db.query_one(
                    "SELECT nombre FROM clientes WHERE id = ?", (cliente_id,)
                )
                if cfila:
                    cliente = cfila["nombre"]
            except Exception:
                cliente = "(Consumidor final)"

        self._imprimir_ticket_termico(
            numero_factura, fecha, productos, total, base, cuota,
            metodo_pago, cliente,
        )

    def cargar_facturas(self, tree):
        try:
            filas = db.query("SELECT * FROM ventas")
            for fila in filas:
                tree.insert("", "end", values=tuple(fila))
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar las facturas: {e}")

    def abrir_cierre_caja(self):
        from .cierre_caja import CierreCaja
        CierreCaja(self)
