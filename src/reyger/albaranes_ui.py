# albaranes_ui.py
"""Ventana de gestión de albaranes de entrega.

Lista los albaranes guardados en la base de datos y permite crear
nuevos (PDF + registro), así como cambiar su estado. La generación del
documento corre en hilo demonio para no congelar la interfaz.
"""

import os
import sqlite3
from datetime import datetime
from tkinter import Toplevel, LabelFrame, Label, Entry, Button, Listbox, END
import tkinter as tk
from tkinter import ttk, messagebox

from .albaranes import AlbaranEntrega
from .config import ConfigManager
from .hilos import en_hilo
from .resources import get_db_path, open_file

ESTADOS_ALBARAN = ("Abierto", "Entregado", "Rechazado")


class VentanaAlbaranes(Toplevel):
    """Gestión de albaranes conectada a la base de datos."""

    def __init__(self, padre, db_path=None, config_manager=None):
        super().__init__(padre)
        self.db_path = db_path or get_db_path()
        self.config_manager = config_manager or ConfigManager()
        self.generador = AlbaranEntrega(self.config_manager)
        self.lineas = []

        self.title("Albaranes de entrega")
        self.geometry("960x640")
        self.minsize(860, 560)
        self.configure(bg="#C6D9E3")
        self.transient(padre)

        self.widgets()
        self.cargar_clientes()
        self.cargar_albaranes()
        self.entry_numero.insert(0, self.siguiente_numero())
        self.entry_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))

    # ---------------------------------------------------------- interfaz
    def widgets(self):
        # Listado existente
        frame_listado = LabelFrame(
            self, text="Albaranes registrados",
            font="sans 14 bold", bg="#C6D9E3",
        )
        frame_listado.pack(fill="both", expand=True, padx=15, pady=(15, 8))

        columnas = ("numero", "fecha", "cliente", "estado")
        self.tree = ttk.Treeview(frame_listado, columns=columnas, show="headings", height=7)
        self.tree.heading("numero", text="Número")
        self.tree.heading("fecha", text="Fecha")
        self.tree.heading("cliente", text="Cliente")
        self.tree.heading("estado", text="Estado")
        self.tree.column("numero", width=130, anchor="center")
        self.tree.column("fecha", width=140, anchor="center")
        self.tree.column("cliente", width=380)
        self.tree.column("estado", width=110, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        scroll = ttk.Scrollbar(frame_listado, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y", pady=10)

        frame_estados = tk.Frame(frame_listado, bg="#C6D9E3")
        frame_estados.pack(side="left", fill="y", padx=(0, 10))
        Button(
            frame_estados, text="✔ Entregado", font="sans 12 bold",
            bg="#2ECC71", fg="white", command=lambda: self.cambiar_estado("Entregado"),
        ).pack(fill="x", pady=4)
        Button(
            frame_estados, text="✖ Rechazar", font="sans 12 bold",
            bg="#c62e26", fg="white", command=lambda: self.cambiar_estado("Rechazado"),
        ).pack(fill="x", pady=4)
        Button(
            frame_estados, text="↩ Reabrir", font="sans 12 bold",
            bg="#95A5A6", fg="white", command=lambda: self.cambiar_estado("Abierto"),
        ).pack(fill="x", pady=4)
        Button(
            frame_estados, text="📂 Abrir PDFs", font="sans 12 bold",
            bg="#0078D4", fg="white", command=self.abrir_carpeta,
        ).pack(fill="x", pady=(20, 4))

        # Formulario de creación
        frame_nuevo = LabelFrame(
            self, text="Nuevo albarán", font="sans 14 bold", bg="#C6D9E3",
        )
        frame_nuevo.pack(fill="x", padx=15, pady=(0, 15))

        fila1 = tk.Frame(frame_nuevo, bg="#C6D9E3")
        fila1.pack(fill="x", padx=10, pady=(10, 0))
        Label(fila1, text="Número:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_numero = Entry(fila1, font="sans 12", width=14)
        self.entry_numero.pack(side="left", padx=(6, 20))
        Label(fila1, text="Fecha:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_fecha = Entry(fila1, font="sans 12", width=14)
        self.entry_fecha.pack(side="left", padx=6)

        fila2 = tk.Frame(frame_nuevo, bg="#C6D9E3")
        fila2.pack(fill="x", padx=10, pady=8)
        Label(fila2, text="Cliente:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.combo_cliente = ttk.Combobox(fila2, font="sans 12", state="readonly", width=28)
        self.combo_cliente.pack(side="left", padx=(6, 20))
        self.combo_cliente.bind("<<ComboboxSelected>>", self._cliente_elegido)
        Label(fila2, text="Dirección:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_direccion = Entry(fila2, font="sans 12")
        self.entry_direccion.pack(side="left", fill="x", expand=True, padx=6)

        fila3 = tk.Frame(frame_nuevo, bg="#C6D9E3")
        fila3.pack(fill="x", padx=10)
        Label(fila3, text="Observaciones:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_observaciones = Entry(fila3, font="sans 12")
        self.entry_observaciones.pack(side="left", fill="x", expand=True, padx=6, pady=(0, 8))

        fila4 = tk.Frame(frame_nuevo, bg="#C6D9E3")
        fila4.pack(fill="x", padx=10, pady=(0, 8))
        Label(fila4, text="Producto:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_producto = Entry(fila4, font="sans 12", width=26)
        self.entry_producto.pack(side="left", padx=(6, 12))
        Label(fila4, text="Cant.:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_cantidad = Entry(fila4, font="sans 12", width=5)
        self.entry_cantidad.pack(side="left", padx=6)
        Label(fila4, text="Descripción:", font="sans 12 bold", bg="#C6D9E3").pack(side="left")
        self.entry_descripcion = Entry(fila4, font="sans 12", width=22)
        self.entry_descripcion.pack(side="left", padx=6)
        Button(
            fila4, text="➕ Añadir", font="sans 11 bold",
            bg="#17A2B8", fg="white", command=self.agregar_linea,
        ).pack(side="left", padx=(8, 0))

        fila5 = tk.Frame(frame_nuevo, bg="#C6D9E3")
        fila5.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.listbox_lineas = Listbox(fila5, font="sans 11", height=4)
        self.listbox_lineas.pack(side="left", fill="both", expand=True)
        scroll_lineas = ttk.Scrollbar(
            fila5, orient="vertical", command=self.listbox_lineas.yview
        )
        self.listbox_lineas.configure(yscrollcommand=scroll_lineas.set)
        scroll_lineas.pack(side="left", fill="y")

        frame_acciones = tk.Frame(frame_nuevo, bg="#C6D9E3")
        frame_acciones.pack(fill="x", padx=10, pady=(0, 12))
        Button(
            frame_acciones, text="🗑 Quitar línea", font="sans 11 bold",
            bg="#95A5A6", fg="white", command=self.quitar_linea,
        ).pack(side="left")
        Button(
            frame_acciones, text="📄 Generar PDF y guardar", font="sans 13 bold",
            bg="#000CFF", fg="white", command=self.generar_albaran,
        ).pack(side="right")

    # ------------------------------------------------------------- datos
    def _conexion(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def siguiente_numero(self):
        """Propone el número correlativo siguiente (ALB-0001…)."""
        try:
            conn = self._conexion()
            fila = conn.execute(
                "SELECT numero_albaran FROM albaranes"
                " ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()
        except sqlite3.Error:
            fila = None
        ultimo = 0
        if fila and fila[0]:
            digitos = "".join(c for c in str(fila[0]) if c.isdigit())
            if digitos:
                ultimo = int(digitos)
        return f"ALB-{ultimo + 1:04d}"

    def cargar_clientes(self):
        try:
            conn = self._conexion()
            filas = conn.execute(
                "SELECT nombre, direccion FROM clientes ORDER BY nombre"
            ).fetchall()
            conn.close()
        except sqlite3.Error:
            filas = []
        self._clientes = {nombre: (direccion or "") for nombre, direccion in filas}
        self.combo_cliente["values"] = list(self._clientes)

    def _cliente_elegido(self, _evento=None):
        direccion = self._clientes.get(self.combo_cliente.get(), "")
        self.entry_direccion.delete(0, END)
        self.entry_direccion.insert(0, direccion)

    def cargar_albaranes(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            conn = self._conexion()
            filas = conn.execute(
                "SELECT numero_albaran, fecha, cliente_nombre, estado"
                " FROM albaranes ORDER BY id DESC"
            ).fetchall()
            conn.close()
        except sqlite3.Error:
            filas = []
        for numero, fecha, cliente, estado in filas:
            self.tree.insert("", END, values=(numero, fecha, cliente, estado))

    # ----------------------------------------------------------- líneas
    def agregar_linea(self):
        nombre = self.entry_producto.get().strip()
        cantidad = self.entry_cantidad.get().strip()
        descripcion = self.entry_descripcion.get().strip()
        if not nombre or not cantidad.isdigit() or int(cantidad) < 1:
            messagebox.showwarning(
                "Nuevo albarán",
                "Indique el producto y una cantidad válida (entero > 0).",
                parent=self,
            )
            return
        linea = {
            "nombre_articulo": nombre,
            "cantidad": int(cantidad),
            "descripcion": descripcion,
        }
        self.lineas.append(linea)
        texto = f"{nombre}  × {cantidad}" + (f"  — {descripcion}" if descripcion else "")
        self.listbox_lineas.insert(END, texto)
        self.entry_producto.delete(0, END)
        self.entry_cantidad.delete(0, END)
        self.entry_descripcion.delete(0, END)
        self.entry_producto.focus_set()

    def quitar_linea(self):
        seleccion = self.listbox_lineas.curselection()
        if not seleccion:
            return
        indice = seleccion[0]
        self.listbox_lineas.delete(indice)
        del self.lineas[indice]

    # -------------------------------------------------------- generación
    def generar_albaran(self):
        numero = self.entry_numero.get().strip()
        fecha = self.entry_fecha.get().strip()
        cliente = self.combo_cliente.get().strip()
        direccion = self.entry_direccion.get().strip()

        if not (numero and fecha and cliente and direccion):
            messagebox.showwarning(
                "Nuevo albarán",
                "Complete número, fecha, cliente y dirección.",
                parent=self,
            )
            return
        if not self.lineas:
            messagebox.showwarning(
                "Nuevo albarán", "Añada al menos un producto.", parent=self
            )
            return

        productos = list(self.lineas)
        observaciones = self.entry_observaciones.get().strip()

        def trabajo():
            ruta_pdf = self.generador.crear_albaran(
                numero, fecha, cliente, direccion, productos,
                observaciones=observaciones,
            )
            guardado = self.generador.guardar_albaran_db(
                numero, fecha, cliente, direccion, productos,
                observaciones=observaciones,
            )
            return ruta_pdf, guardado

        def al_terminar(resultado, error):
            if error is not None:
                messagebox.showerror(
                    "Nuevo albarán", f"No se pudo generar el albarán:\n{error}",
                    parent=self,
                )
                return
            ruta_pdf, guardado = resultado
            if not guardado:
                messagebox.showwarning(
                    "Nuevo albarán",
                    f"El número {numero} ya existe en la base de datos.",
                    parent=self,
                )
                return
            self.limpiar_formulario()
            self.cargar_albaranes()
            messagebox.showinfo(
                "Nuevo albarán", f"Albarán {numero} generado en:\n{ruta_pdf}",
                parent=self,
            )

        en_hilo(self, trabajo, al_terminar)

    def limpiar_formulario(self):
        for entrada in (
            self.entry_numero, self.entry_fecha, self.entry_direccion,
            self.entry_observaciones, self.entry_producto,
            self.entry_cantidad, self.entry_descripcion,
        ):
            entrada.delete(0, END)
        self.combo_cliente.set("")
        self.listbox_lineas.delete(0, END)
        self.lineas.clear()
        self.entry_numero.insert(0, self.siguiente_numero())
        self.entry_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))

    # ------------------------------------------------------------ estados
    def _numero_seleccionado(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning(
                "Albaranes", "Seleccione un albarán del listado.", parent=self
            )
            return None
        return self.tree.item(seleccion)["values"][0]

    def cambiar_estado(self, estado):
        numero = self._numero_seleccionado()
        if numero is None:
            return
        if self.generador.cambiar_estado_albaran(str(numero), estado):
            self.cargar_albaranes()

    def abrir_carpeta(self):
        from .resources import get_output_path

        carpeta = get_output_path("albaranes")
        os.makedirs(carpeta, exist_ok=True)
        open_file(carpeta)
