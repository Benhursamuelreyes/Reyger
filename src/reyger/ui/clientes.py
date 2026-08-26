"""Gestión de clientes: CRUD con datos personales y fiscales.

Incluye la validación de documentos españoles (NIF, NIE y CIF) usada
tanto desde la interfaz como desde otros módulos (facturación).
"""

import tkinter as tk
from tkinter import ttk, messagebox

from ..core import db
from ..config import ConfigManager
from .ui import configurar_ventana

LETRAS_NIF = "TRWAGMYFPDXBNJZSQVHLCKE"
LETRAS_CONTROL_CIF = "JABCDEFGHI"
TIPOS_DOCUMENTO = ("NIF", "NIE", "CIF", "Otro")


def validar_documento(documento):
    """Valida un documento español.

    Devuelve una tupla ``(es_valido, tipo)`` donde *tipo* es ``"NIF"``,
    ``"NIE"``, ``"CIF"`` o ``None`` si el formato no se reconoce.
    """
    doc = (documento or "").strip().upper()
    if len(doc) == 9 and doc[:8].isdigit() and doc[8].isalpha():
        letra = LETRAS_NIF[int(doc[:8]) % 23]
        return doc[8] == letra, "NIF"
    if (
        len(doc) == 9
        and doc[0] in "XYZ"
        and doc[1:8].isdigit()
        and doc[8].isalpha()
    ):
        prefijo = {"X": "0", "Y": "1", "Z": "2"}[doc[0]]
        letra = LETRAS_NIF[int(prefijo + doc[1:8]) % 23]
        return doc[8] == letra, "NIE"
    if len(doc) == 9 and doc[0].isalpha() and doc[1:8].isdigit() and doc[8].isalnum():
        return _validar_cif(doc), "CIF"
    return False, None


def _validar_cif(cif):
    """Dígito/letra de control de un CIF (Real Decreto 1065/2007)."""
    digitos = [int(c) for c in cif[1:8]]
    suma_pares = digitos[1] + digitos[3] + digitos[5]
    suma_impares = 0
    for d in digitos[0::2]:
        doble = d * 2
        suma_impares += (doble // 10) + (doble % 10)
    control = (10 - (suma_pares + suma_impares) % 10) % 10
    letra = LETRAS_CONTROL_CIF[control]
    if cif[0] in "PQSNWR":
        return cif[8] == letra
    if cif[8].isdigit():
        return int(cif[8]) == control
    return cif[8] == letra


class Clientes(tk.Frame):
    """Ventana de administración de clientes."""

    def __init__(self, parent):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        self.cliente_id_actual = None
        self.widgets()
        self.cargar_clientes()

    # ------------------------------------------------------------------ UI
    def widgets(self):
        frame_titulo = tk.Frame(self, bg="#2ECC71")
        frame_titulo.pack(fill="x")
        tk.Label(
            frame_titulo,
            text="👥 CLIENTES",
            bg="#2ECC71",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold",
        ).pack(pady=14)

        frame_busqueda = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_busqueda.pack(fill="x", padx=20, pady=(15, 5))
        tk.Label(
            frame_busqueda,
            text="Buscar:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 12 bold",
        ).pack(side="left", padx=(0, 8))
        self.entry_buscar = ttk.Entry(frame_busqueda, font="sans 12", width=40)
        self.entry_buscar.pack(side="left")
        self.entry_buscar.bind("<Return>", lambda e: self.buscar())
        tk.Button(
            frame_busqueda,
            text="🔍 Buscar",
            bg="#0078D4",
            fg="white",
            font="sans 11 bold",
            command=self.buscar,
        ).pack(side="left", padx=8)
        tk.Button(
            frame_busqueda,
            text="✖ Limpiar búsqueda",
            bg="#95A5A6",
            fg="white",
            font="sans 11 bold",
            command=self.limpiar_busqueda,
        ).pack(side="left")

        frame_contenido = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_contenido.pack(fill="both", expand=True, padx=20, pady=10)

        # --- Formulario (izquierda) ---------------------------------------
        frame_form = tk.LabelFrame(
            frame_contenido,
            text="Datos del cliente",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 12 bold",
            padx=15,
            pady=10,
        )
        frame_form.pack(side="left", fill="both", padx=(0, 15))

        self.campos = {}
        filas = [
            ("nombre", "Nombre *:", None),
            ("tipo_documento", "Tipo doc.:", TIPOS_DOCUMENTO),
            ("documento", "NIF/NIE/CIF:", None),
            ("direccion", "Dirección:", None),
            ("codigo_postal", "Código postal:", None),
            ("provincia", "Provincia:", None),
            ("telefono", "Teléfono:", None),
            ("email", "Correo electrónico:", None),
            ("notas", "Notas:", None),
        ]
        for fila, (clave, etiqueta, valores) in enumerate(filas):
            tk.Label(
                frame_form,
                text=etiqueta,
                bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"],
                font="sans 11 bold",
            ).grid(row=fila, column=0, sticky="w", pady=4)
            if valores:
                widget = ttk.Combobox(
                    frame_form, values=valores, state="readonly",
                    font="sans 11", width=28,
                )
                widget.current(0)
            else:
                widget = ttk.Entry(frame_form, font="sans 11", width=30)
            widget.grid(row=fila, column=1, pady=4, sticky="ew")
            self.campos[clave] = widget

        # Sin esto los campos no crecen al maximizar la ventana
        frame_form.columnconfigure(1, weight=1)

        frame_botones_form = tk.Frame(
            frame_form, bg=self.colors["bg_principal"]
        )
        frame_botones_form.grid(
            row=len(filas), column=0, columnspan=2, pady=(15, 5)
        )
        tk.Button(
            frame_botones_form,
            text="💾 Guardar",
            bg="#27AE60",
            fg="white",
            font="sans 11 bold",
            command=self.guardar,
        ).pack(side="left", padx=5)
        tk.Button(
            frame_botones_form,
            text="🧹 Nuevo / Limpiar",
            bg="#0078D4",
            fg="white",
            font="sans 11 bold",
            command=self.limpiar_formulario,
        ).pack(side="left", padx=5)
        tk.Button(
            frame_botones_form,
            text="🗑️ Eliminar",
            bg="#C0392B",
            fg="white",
            font="sans 11 bold",
            command=self.eliminar,
        ).pack(side="left", padx=5)

        # --- Listado (derecha) --------------------------------------------
        frame_lista = tk.Frame(frame_contenido, bg=self.colors["bg_principal"])
        frame_lista.pack(side="left", fill="both", expand=True)

        frame_tree = tk.Frame(frame_lista, bg=self.colors["bg_principal"])
        frame_tree.pack(fill="both", expand=True)
        scrol_y = ttk.Scrollbar(frame_tree, orient="vertical")
        scrol_y.pack(side="right", fill="y")
        self.tree = ttk.Treeview(
            frame_tree,
            columns=("ID", "Nombre", "Documento", "Teléfono", "Email", "CP"),
            show="headings",
            yscrollcommand=scrol_y.set,
        )
        scrol_y.config(command=self.tree.yview)
        for col, texto, ancho in (
            ("ID", "ID", 50),
            ("Nombre", "Nombre", 220),
            ("Documento", "NIF/NIE/CIF", 120),
            ("Teléfono", "Teléfono", 110),
            ("Email", "Email", 200),
            ("CP", "CP", 70),
        ):
            self.tree.heading(col, text=texto)
            self.tree.column(col, width=ancho, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.al_seleccionar)

        tk.Label(
            frame_lista,
            text="Seleccione un cliente para editar sus datos.",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10",
        ).pack(anchor="w", pady=(6, 0))

    # ------------------------------------------------------------- datos
    def cargar_clientes(self, filtro=""):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if filtro:
            patron = f"%{filtro}%"
            filas = db.query(
                """
                SELECT id, nombre, tipo_documento, documento, telefono, email,
                       codigo_postal
                FROM clientes
                WHERE nombre LIKE ? OR documento LIKE ? OR email LIKE ?
                      OR telefono LIKE ?
                ORDER BY nombre
                """,
                (patron, patron, patron, patron),
            )
        else:
            filas = db.query(
                """
                SELECT id, nombre, tipo_documento, documento, telefono, email,
                       codigo_postal
                FROM clientes ORDER BY nombre
                """
            )
        for fila in filas:
            documento = ""
            if fila["documento"]:
                documento = (
                    f"{fila['documento']}"
                    if fila["tipo_documento"] in (None, "", "Otro")
                    else f"{fila['documento']} ({fila['tipo_documento']})"
                )
            self.tree.insert(
                "", "end",
                values=(
                    fila["id"], fila["nombre"], documento,
                    fila["telefono"] or "", fila["email"] or "",
                    fila["codigo_postal"] or "",
                ),
            )

    def buscar(self):
        self.cargar_clientes(self.entry_buscar.get().strip())

    def limpiar_busqueda(self):
        self.entry_buscar.delete(0, "end")
        self.cargar_clientes()

    def al_seleccionar(self, _evento=None):
        seleccion = self.tree.selection()
        if not seleccion:
            return
        valores = self.tree.item(seleccion[0])["values"]
        cliente_id = int(valores[0])
        fila = db.query_one("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
        if fila is None:
            return
        self.cliente_id_actual = cliente_id
        self.campos["nombre"].delete(0, "end")
        self.campos["nombre"].insert(0, fila["nombre"] or "")
        tipo = fila["tipo_documento"] or "NIF"
        if tipo in TIPOS_DOCUMENTO:
            self.campos["tipo_documento"].set(tipo)
        for clave in (
            "documento", "direccion", "codigo_postal", "provincia",
            "telefono", "email", "notas",
        ):
            self.campos[clave].delete(0, "end")
            self.campos[clave].insert(0, fila[clave] or "")

    def guardar(self):
        nombre = self.campos["nombre"].get().strip()
        if not nombre:
            messagebox.showwarning(
                "Guardar cliente", "El nombre del cliente es obligatorio."
            )
            return

        tipo_documento = self.campos["tipo_documento"].get()
        documento = self.campos["documento"].get().strip().upper()
        if documento and tipo_documento != "Otro":
            valido, tipo_detectado = validar_documento(documento)
            if not valido:
                messagebox.showwarning(
                    "Documento no válido",
                    f"'{documento}' no es un {tipo_documento} español válido.\n"
                    "Revise el número o seleccione 'Otro'.",
                )
                return
            tipo_documento = tipo_detectado
        elif documento and tipo_documento == "Otro":
            pass

        datos = (
            nombre,
            tipo_documento,
            documento,
            self.campos["direccion"].get().strip(),
            self.campos["codigo_postal"].get().strip(),
            self.campos["provincia"].get().strip(),
            self.campos["telefono"].get().strip(),
            self.campos["email"].get().strip(),
            self.campos["notas"].get().strip(),
        )
        if self.cliente_id_actual is None:
            db.execute(
                """
                INSERT INTO clientes (nombre, tipo_documento, documento,
                    direccion, codigo_postal, provincia, telefono, email, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                datos,
            )
        else:
            db.execute(
                """
                UPDATE clientes SET nombre=?, tipo_documento=?, documento=?,
                    direccion=?, codigo_postal=?, provincia=?, telefono=?,
                    email=?, notas=?
                WHERE id=?
                """,
                datos + (self.cliente_id_actual,),
            )
        self.limpiar_formulario()
        self.cargar_clientes()

    def eliminar(self):
        if self.cliente_id_actual is None:
            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showwarning(
                    "Eliminar cliente", "Seleccione un cliente de la lista."
                )
                return
            self.cliente_id_actual = int(
                self.tree.item(seleccion[0])["values"][0]
            )
        fila = db.query_one(
            "SELECT nombre FROM clientes WHERE id = ?", (self.cliente_id_actual,)
        )
        nombre = fila["nombre"] if fila else str(self.cliente_id_actual)
        if messagebox.askyesno(
            "Eliminar cliente", f"¿Eliminar el cliente '{nombre}'?"
        ):
            db.execute("DELETE FROM clientes WHERE id = ?", (self.cliente_id_actual,))
            self.limpiar_formulario()
            self.cargar_clientes()

    def limpiar_formulario(self):
        self.cliente_id_actual = None
        self.campos["nombre"].delete(0, "end")
        self.campos["tipo_documento"].current(0)
        for clave in (
            "documento", "direccion", "codigo_postal", "provincia",
            "telefono", "email", "notas",
        ):
            self.campos[clave].delete(0, "end")


def abrir_clientes(parent=None):
    """Abre la gestión de clientes en una ventana modal independiente."""
    top = tk.Toplevel(parent)
    configurar_ventana(top, titulo="Clientes")
    Clientes(top).pack(fill="both", expand=True)
    return top
