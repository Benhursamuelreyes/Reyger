import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
from datetime import datetime

from . import backup as mod_backup
from . import categorias as mod_categorias
from .config import ConfigManager
from .hilos import en_hilo
from .impresion_termica import (
    ANCHO_80MM,
    construir_ticket_venta,
    enviar_bytes,
    listar_impresoras_termicas,
)
from .resources import get_user_data_path, get_bundled_path

#: Etiquetas visibles del selector de letra ↔ claves de ESCALAS_LETRA
ETIQUETAS_LETRA = {
    "pequena": "Pequeña",
    "grande": "Grande",
    "muy_grande": "Muy grande",
}

class Ajustes(tk.Frame):
    """Ventana de configuración y ajustes del sistema"""
    
    def __init__(self, parent, usuario=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.pack(fill="both", expand=True)
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        
        self.logo_image_preview = None
        self.widgets()
    
    def widgets(self):
        """Crea los widgets de la ventana de ajustes"""
        
        # Frame superior con título (alto dinámico según la fuente elegida)
        frame_titulo = tk.Frame(self, bg="#0078D4")
        frame_titulo.pack(fill="x")
        
        titulo = tk.Label(
            frame_titulo, 
            text="⚙️ AJUSTES Y CONFIGURACIÓN",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold"
        )
        titulo.pack(pady=14)
        
        # Frame principal con scroll vertical (el contenido excede la
        # altura de la ventana en pantallas pequeñas)
        contenedor = tk.Frame(self, bg=self.colors["bg_principal"])
        contenedor.pack(fill="both", expand=True, padx=20, pady=20)

        barra = ttk.Scrollbar(contenedor, orient="vertical")
        barra.pack(side="right", fill="y")

        lienzo = tk.Canvas(
            contenedor,
            bg=self.colors["bg_principal"],
            highlightthickness=0,
            yscrollcommand=barra.set,
        )
        lienzo.pack(side="left", fill="both", expand=True)
        barra.config(command=lienzo.yview)

        main_frame = tk.Frame(lienzo, bg=self.colors["bg_principal"])
        ventana_contenido = lienzo.create_window(
            (0, 0), window=main_frame, anchor="nw"
        )

        main_frame.bind(
            "<Configure>",
            lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")),
        )

        def _ajustar_ancho(evento):
            lienzo.itemconfigure(ventana_contenido, width=evento.width)

        lienzo.bind("<Configure>", _ajustar_ancho)

        def _rueda(evento):
            # Linux: Button-4/5; Windows/macOS: MouseWheel con delta
            if getattr(evento, "num", None) == 4 or evento.delta > 0:
                lienzo.yview_scroll(-2, "units")
            elif getattr(evento, "num", None) == 5 or evento.delta < 0:
                lienzo.yview_scroll(2, "units")

        toplevel = self.winfo_toplevel()
        for secuencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            toplevel.bind(secuencia, _rueda)
        
        # Sección 1: Tema
        self.crear_seccion_tema(main_frame)
        
        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)
        
        # Sección 2: Tamaño de fuente
        self.crear_seccion_tamaño_fuente(main_frame)
        
        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)
        
        # Sección 3: Logo
        self.crear_seccion_logo(main_frame)
        
        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)
        
        # Sección 4: Información de la empresa
        self.crear_seccion_empresa(main_frame)
        
        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)
        
        # Sección 5: Opciones adicionales
        self.crear_seccion_opciones(main_frame)

        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)

        # Sección 6: Impresora térmica
        self.crear_seccion_impresora_termica(main_frame)

        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)

        # Sección 7: Categorías de productos
        self.crear_seccion_categorias(main_frame)

        # Separador
        tk.Frame(main_frame, bg="#CCCCCC", height=2).pack(fill="x", pady=15)

        # Sección 8: Base de datos (exportar/importar)
        self.crear_seccion_base_datos(main_frame)

        # Frame de botones
        frame_botones = tk.Frame(main_frame, bg=self.colors["bg_principal"])
        frame_botones.pack(fill="x", pady=20)
        
        btn_guardar = tk.Button(
            frame_botones,
            text="💾 Guardar cambios",
            bg="#28A745",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.guardar_cambios,
            padx=20,
            pady=10
        )
        btn_guardar.pack(side="left", padx=10)
        
        btn_restablecer = tk.Button(
            frame_botones,
            text="🔄 Restablecer",
            bg="#FFC107",
            fg="black",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.restablecer_defaults,
            padx=20,
            pady=10
        )
        btn_restablecer.pack(side="left", padx=10)
    
    def crear_seccion_tema(self, parent):
        """Crea la sección de selección de tema"""
        frame = tk.LabelFrame(
            parent,
            text="🎨 Tema",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)
        
        frame_radio = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_radio.pack(fill="x", pady=10)
        
        self.var_tema = tk.StringVar(value=self.config_manager.get("tema"))
        
        radio_claro = tk.Radiobutton(
            frame_radio,
            text="☀️ Tema Claro",
            variable=self.var_tema,
            value="claro",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.preview_tema
        )
        radio_claro.pack(anchor="w", padx=20, pady=5)
        
        radio_oscuro = tk.Radiobutton(
            frame_radio,
            text="🌙 Tema Oscuro",
            variable=self.var_tema,
            value="oscuro",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.preview_tema
        )
        radio_oscuro.pack(anchor="w", padx=20, pady=5)
    
    def crear_seccion_tamaño_fuente(self, parent):
        """Crea la sección de tamaño de fuente"""
        frame = tk.LabelFrame(
            parent,
            text="📏 Tamaño de Fuente",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)
        
        frame_slider = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_slider.pack(fill="x", pady=10, padx=20)
        
        label_tamaño = tk.Label(
            frame_slider,
            text=f"Tamaño actual: {self.config_manager.get('tamaño_fuente')}px",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_tamaño.pack(anchor="w")
        
        self.scale_tamaño = tk.Scale(
            frame_slider,
            from_=10,
            to=18,
            orient="horizontal",
            bg=self.colors["bg_secundario"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=lambda v: label_tamaño.config(text=f"Tamaño actual: {v}px")
        )
        self.scale_tamaño.set(self.config_manager.get("tamaño_fuente"))
        self.scale_tamaño.pack(fill="x", pady=10)
    
    def crear_seccion_logo(self, parent):
        """Crea la sección de carga de logo"""
        frame = tk.LabelFrame(
            parent,
            text="🖼️ Logo de la Empresa",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)
        
        # Frame para mostrar preview del logo
        preview_frame = tk.Frame(frame, bg=self.colors["bg_secundario"], width=150, height=150)
        preview_frame.pack(side="left", padx=20, pady=20)
        preview_frame.pack_propagate(False)
        
        self.logo_label = tk.Label(
            preview_frame,
            text="📷\nSin logo",
            bg=self.colors["bg_secundario"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('pequeño')} bold"
        )
        self.logo_label.pack(fill="both", expand=True)
        
        # Cargar logo actual si existe
        logo_path = self.config_manager.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            self.mostrar_preview_logo(logo_path)
        
        # Frame de botones para logo
        frame_logo_botones = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_logo_botones.pack(side="left", fill="y", padx=20, pady=20)
        
        btn_cargar = tk.Button(
            frame_logo_botones,
            text="📁 Cargar Logo",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.cargar_logo,
            padx=15,
            pady=10
        )
        btn_cargar.pack(pady=5)
        
        btn_eliminar = tk.Button(
            frame_logo_botones,
            text="🗑️ Eliminar Logo",
            bg="#C0392B",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.eliminar_logo,
            padx=15,
            pady=10
        )
        btn_eliminar.pack(pady=5)
    
    def crear_seccion_empresa(self, parent):
        """Crea la sección de información de la empresa"""
        frame = tk.LabelFrame(
            parent,
            text="🏢 Información de la Empresa",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)
        
        # Nombre de la empresa
        label_nombre = tk.Label(
            frame,
            text="Nombre de la empresa:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_nombre.pack(anchor="w", padx=20, pady=(10, 5))
        
        self.entry_nombre = tk.Entry(
            frame,
            bg=self.colors["entry_bg"],
            fg=self.colors["entry_fg"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            width=40
        )
        self.entry_nombre.insert(0, self.config_manager.get("nombre_empresa"))
        self.entry_nombre.pack(anchor="w", padx=20, pady=(0, 15), ipady=5)
    
    def crear_seccion_opciones(self, parent):
        """Crea la sección de opciones adicionales"""
        frame = tk.LabelFrame(
            parent,
            text="⚙️ Opciones Adicionales",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)
        
        # Mostrar hora en facturas
        self.var_hora = tk.BooleanVar(value=self.config_manager.get("mostrar_hora"))
        check_hora = tk.Checkbutton(
            frame,
            text="⏰ Mostrar hora en facturas",
            variable=self.var_hora,
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            selectcolor=self.colors["bg_secundario"]
        )
        check_hora.pack(anchor="w", padx=20, pady=5)
        
        # Decimales en precios
        label_decimales = tk.Label(
            frame,
            text="Decimales en precios:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_decimales.pack(anchor="w", padx=20, pady=(10, 5))
        
        self.var_decimales = tk.IntVar(value=self.config_manager.get("redondear_decimales"))
        
        frame_decimales = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_decimales.pack(anchor="w", padx=20, pady=(0, 15))
        
        for decimales in [2, 3, 4]:
            radio = tk.Radiobutton(
                frame_decimales,
                text=f"{decimales} decimales",
                variable=self.var_decimales,
                value=decimales,
                bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"],
                font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
            )
            radio.pack(side="left", padx=10)
    
    def crear_seccion_impresora_termica(self, parent):
        """Sección de configuración de la impresora de tickets."""
        frame = tk.LabelFrame(
            parent,
            text="🖨️ Impresora Térmica (tickets)",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)

        label_impresora = tk.Label(
            frame,
            text="Impresora de tickets:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_impresora.pack(anchor="w", padx=20, pady=(10, 5))

        impresoras = ["(Desactivada)"] + listar_impresoras_termicas()
        self.combo_impresora = ttk.Combobox(
            frame,
            values=impresoras,
            state="readonly",
            font=f"sans {self.config_manager.get_tamaño_fuente()}",
            width=38
        )
        actual = self.config_manager.get("impresora_termica")
        if actual and actual not in impresoras:
            # Guardada pero hoy no conectada: se conserva y se avisa,
            # en vez de borrarla silenciosamente al guardar.
            etiqueta = f"{actual} (no detectada)"
            self.combo_impresora["values"] = impresoras + [etiqueta]
            self.combo_impresora.set(etiqueta)
        elif actual in impresoras:
            self.combo_impresora.set(actual)
        else:
            self.combo_impresora.current(0)
        self.combo_impresora.pack(anchor="w", padx=20, pady=(0, 10))

        label_ancho = tk.Label(
            frame,
            text="Ancho del papel:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_ancho.pack(anchor="w", padx=20, pady=(5, 5))

        self.var_ancho_ticket = tk.IntVar(
            value=self.config_manager.get("ancho_ticket", 80)
        )
        frame_anchos = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_anchos.pack(anchor="w", padx=20, pady=(0, 10))
        for ancho in (80, 58):
            radio = tk.Radiobutton(
                frame_anchos,
                text=f"{ancho} mm",
                variable=self.var_ancho_ticket,
                value=ancho,
                bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"],
                font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
                selectcolor=self.colors["bg_secundario"]
            )
            radio.pack(side="left", padx=10)

        label_letra = tk.Label(
            frame,
            text="Tamaño de la letra del ticket:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold"
        )
        label_letra.pack(anchor="w", padx=20, pady=(5, 5))

        self.var_letra_ticket = tk.StringVar(
            value=ETIQUETAS_LETRA.get(
                self.config_manager.get("letra_ticket", "muy_grande"), "Muy grande"
            )
        )
        self.combo_letra_ticket = ttk.Combobox(
            frame,
            textvariable=self.var_letra_ticket,
            values=list(ETIQUETAS_LETRA.values()),
            state="readonly",
            font=f"sans {self.config_manager.get_tamaño_fuente()}",
            width=20
        )
        self.combo_letra_ticket.pack(anchor="w", padx=20, pady=(0, 10))

        btn_prueba = tk.Button(
            frame,
            text="🧾 Imprimir página de prueba",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.imprimir_pagina_prueba,
            padx=15,
            pady=8
        )
        btn_prueba.pack(anchor="w", padx=20, pady=(0, 10))

    def imprimir_pagina_prueba(self):
        """Envía un ticket de ejemplo a la impresora seleccionada."""
        impresora = self.combo_impresora.get().removesuffix(" (no detectada)")
        if impresora == "(Desactivada)":
            messagebox.showwarning(
                "Impresora térmica",
                "Seleccione una impresora antes de imprimir la prueba."
            )
            return
        ancho = ANCHO_80MM if self.var_ancho_ticket.get() == 80 else 32
        letra = next(
            clave for clave, etiqueta in ETIQUETAS_LETRA.items()
            if etiqueta == self.var_letra_ticket.get()
        )
        logo = None
        ruta_logo = self.config_manager.get("logo_path")
        if ruta_logo and os.path.exists(ruta_logo):
            logo = ruta_logo
        else:
            integrado = get_bundled_path(os.path.join("assets", "img", "logo.png"))
            if os.path.exists(integrado):
                logo = integrado
        datos = construir_ticket_venta(
            numero_factura="PRUEBA",
            fecha="01/01/2026 12:00",
            productos=[("Producto de prueba", 1.10, 1, 1.10)],
            total=1.10,
            base=0.91,
            cuota=0.19,
            metodo_pago="Efectivo",
            empresa=self.entry_nombre.get() or "Mi Empresa",
            ancho=ancho,
            letra=letra,
            logo=logo,
        )
        if enviar_bytes(datos, None if impresora == "" else impresora):
            messagebox.showinfo(
                "Impresora térmica",
                f"Página de prueba enviada a:\n{impresora}"
            )
        else:
            messagebox.showerror(
                "Impresora térmica",
                "No se pudo imprimir la página de prueba.\n"
                "Compruebe que la impresora está conectada y encendida."
            )

    def cargar_logo(self):
        """Abre el diálogo para cargar una imagen como logo"""
        filetypes = [("Imágenes", "*.png *.jpg *.jpeg *.bmp"), ("Todos", "*.*")]
        filepath = filedialog.askopenfilename(
            title="Seleccionar logo",
            filetypes=filetypes
        )
        
        if filepath:
            # Copiar imagen a la carpeta del proyecto
            from shutil import copy
            try:
                logo_filename = os.path.join(str(get_user_data_path()), "logo.png")
                
                # Convertir a PNG si es necesario
                img = Image.open(filepath)
                img.save(logo_filename, "PNG")
                
                self.config_manager.set("logo_path", logo_filename)
                self.mostrar_preview_logo(logo_filename)
                messagebox.showinfo("Éxito", "Logo cargado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el logo: {e}")
    
    def mostrar_preview_logo(self, logo_path):
        """Muestra un preview del logo cargado"""
        try:
            img = Image.open(logo_path)
            img.thumbnail((150, 150), Image.Resampling.LANCZOS)
            self.logo_image_preview = ImageTk.PhotoImage(img)
            
            self.logo_label.config(image=self.logo_image_preview, text="")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo mostrar el preview: {e}")
    
    def eliminar_logo(self):
        """Elimina el logo configurado"""
        if messagebox.askyesno("Confirmar", "¿Eliminar el logo actual?"):
            logo_path = self.config_manager.get("logo_path")
            if logo_path and os.path.exists(logo_path):
                try:
                    os.remove(logo_path)
                except:
                    pass
            
            self.config_manager.set("logo_path", None)
            self.logo_label.config(image="", text="📷\nSin logo")
            self.logo_image_preview = None
    
    def preview_tema(self):
        """Actualiza el preview del tema seleccionado"""
        # Aquí podrías agregar una vista previa actual del tema
        pass

    def crear_seccion_categorias(self, parent):
        """Sección de gestión de categorías de productos."""
        frame = tk.LabelFrame(
            parent,
            text="🗂️ Categorías de productos",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)

        tk.Label(
            frame,
            text="Agrupa tus productos (frutas, carnes, informática, móviles...).\n"
                 "Al eliminar una categoría, sus productos pasan a «General».",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10",
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        frame_lista = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_lista.pack(fill="x")

        scrol = ttk.Scrollbar(frame_lista, orient="vertical")
        self.lista_categorias = tk.Listbox(
            frame_lista, height=6, font="sans 12",
            yscrollcommand=scrol.set, exportselection=False,
        )
        scrol.config(command=self.lista_categorias.yview)
        scrol.pack(side="right", fill="y")
        self.lista_categorias.pack(side="left", fill="both", expand=True)
        self.refrescar_categorias()

        frame_acciones = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_acciones.pack(fill="x", pady=(10, 0))

        self.entry_categoria_nombre = ttk.Entry(frame_acciones, font="sans 12")
        self.entry_categoria_nombre.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

        btn_añadir = tk.Button(
            frame_acciones, text="➕ Añadir",
            bg="#28A745", fg="white", font="sans 11 bold",
            command=self.categoria_añadir,
        )
        btn_añadir.pack(side="left", padx=(0, 6))

        btn_renombra = tk.Button(
            frame_acciones, text="✏️ Renombrar",
            bg="#17A2B8", fg="white", font="sans 11 bold",
            command=self.categoria_renombrar,
        )
        btn_renombra.pack(side="left", padx=(0, 6))

        btn_elimina = tk.Button(
            frame_acciones, text="🗑️ Eliminar",
            bg="#DC3545", fg="white", font="sans 11 bold",
            command=self.categoria_eliminar,
        )
        btn_elimina.pack(side="left")

    def _categoria_seleccionada(self):
        seleccion = self.lista_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Categorías", "Seleccione una categoría de la lista.")
            return None
        return mod_categorias.listar()[seleccion[0]]

    def refrescar_categorias(self):
        self.lista_categorias.delete(0, "end")
        for _, nombre in mod_categorias.listar():
            self.lista_categorias.insert("end", nombre)

    def categoria_añadir(self):
        try:
            nuevo_id = mod_categorias.crear(self.entry_categoria_nombre.get())
        except ValueError as e:
            messagebox.showwarning("Categorías", str(e))
            return
        if nuevo_id is None:
            messagebox.showwarning("Categorías", "Esa categoría ya existe.")
            return
        self.entry_categoria_nombre.delete(0, "end")
        self.refrescar_categorias()

    def categoria_renombrar(self):
        sel = self._categoria_seleccionada()
        if not sel:
            return
        categoria_id, nombre_actual = sel
        nombre_nuevo = self.entry_categoria_nombre.get().strip()
        if not nombre_nuevo:
            messagebox.showwarning(
                "Categorías",
                f"Escriba el nuevo nombre en el campo de texto y pulse Renombrar.\n"
                f"(Categoría seleccionada: {nombre_actual})",
            )
            return
        try:
            ok = mod_categorias.renombrar(categoria_id, nombre_nuevo)
        except ValueError as e:
            messagebox.showwarning("Categorías", str(e))
            return
        if not ok:
            messagebox.showwarning("Categorías", "Ese nombre ya existe en otra categoría.")
            return
        self.entry_categoria_nombre.delete(0, "end")
        self.refrescar_categorias()

    def categoria_eliminar(self):
        sel = self._categoria_seleccionada()
        if not sel:
            return
        categoria_id, nombre = sel
        if nombre == mod_categorias.GENERAL:
            messagebox.showinfo("Categorías", "La categoría «General» no se puede eliminar.")
            return
        if not messagebox.askyesno(
            "Eliminar categoría",
            f"¿Eliminar «{nombre}»? Sus productos pasarán a «General».",
        ):
            return
        mod_categorias.eliminar(categoria_id)
        self.refrescar_categorias()

    def crear_seccion_base_datos(self, parent):
        """Sección de exportación/importación de la base de datos."""
        frame = tk.LabelFrame(
            parent,
            text="🗄️ Base de datos",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=15,
            pady=10
        )
        frame.pack(fill="x", pady=10)

        tk.Label(
            frame,
            text="Lleva tus datos a otro equipo o haz copias de seguridad.\n"
                 "Al importar se crea automáticamente una copia de seguridad "
                 "de la base actual.",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10",
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        frame_formatos = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_formatos.pack(anchor="w", padx=20, pady=(0, 10))

        self.var_formato_bd = tk.StringVar(value="db")
        for valor, texto in (
            ("db", "Base SQLite (.db) — copia completa"),
            ("excel", "Excel (.xlsx) — una hoja por tabla"),
            ("csv", "CSV comprimido (.zip) — un CSV por tabla"),
        ):
            radio = tk.Radiobutton(
                frame_formatos,
                text=texto,
                variable=self.var_formato_bd,
                value=valor,
                bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"],
                font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
                selectcolor=self.colors["bg_secundario"],
            )
            if valor == "excel" and not mod_backup.EXCEL_DISPONIBLE:
                radio.config(state="disabled")
            radio.pack(side="left", padx=(0, 15))

        frame_acciones = tk.Frame(frame, bg=self.colors["bg_principal"])
        frame_acciones.pack(fill="x", padx=20, pady=(0, 5))

        btn_exportar = tk.Button(
            frame_acciones,
            text="📤 Exportar base de datos…",
            bg="#28A745",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.exportar_base_datos,
            padx=15,
            pady=8
        )
        btn_exportar.pack(side="left", padx=(0, 10))
        self.btn_exportar_bd = btn_exportar

        btn_importar = tk.Button(
            frame_acciones,
            text="📥 Importar base de datos…",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente()} bold",
            command=self.importar_base_datos,
            padx=15,
            pady=8
        )
        btn_importar.pack(side="left")
        self.btn_importar_bd = btn_importar

    def _ocupar_botones_bd(self, ocupado):
        """Deshabilita la botonera de BD mientras hay una tarea en hilo."""
        estado = "disabled" if ocupado else "normal"
        self.btn_exportar_bd.config(
            state=estado,
            text="⏳ Exportando…" if ocupado else "📤 Exportar base de datos…",
        )
        self.btn_importar_bd.config(state=estado)

    def exportar_base_datos(self):
        """Exporta la base en el formato seleccionado.

        El trabajo pesado corre fuera del hilo de la interfaz para que
        la ventana no se congele durante la escritura del fichero.
        """
        formato = self.var_formato_bd.get()
        descripcion, extension = mod_backup.FORMATOS_EXPORTACION[formato]
        ruta = filedialog.asksaveasfilename(
            title=f"Exportar base de datos — {descripcion}",
            defaultextension=extension,
            initialfile=f"reyger_{datetime.now():%Y%m%d}{extension}",
            filetypes=[(descripcion, f"*{extension}")],
        )
        if not ruta:
            return

        if formato == "db":
            trabajo = lambda: mod_backup.exportar_sqlite(ruta)  # noqa: E731
        elif formato == "excel":
            trabajo = lambda: mod_backup.exportar_excel(ruta)  # noqa: E731
        else:
            trabajo = lambda: mod_backup.exportar_csv_zip(ruta)  # noqa: E731

        def al_terminar(final, error):
            self._ocupar_botones_bd(False)
            if error is not None:
                messagebox.showerror(
                    "Exportar base de datos", f"No se pudo exportar: {error}"
                )
                return
            messagebox.showinfo(
                "Exportar base de datos",
                f"Exportación completada correctamente:\n{final}"
            )

        self._ocupar_botones_bd(True)
        en_hilo(self, trabajo, al_terminar)

    def importar_base_datos(self):
        """Importa la base desde .db, .xlsx o .zip con confirmación previa."""
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

        extension = os.path.splitext(ruta)[1].lower()
        if extension in (".db", ".sqlite", ".sqlite3"):
            aviso = (
                "Se SUSTITUIRÁ la base de datos completa por el fichero "
                "seleccionado."
            )
        else:
            aviso = (
                "Se sustituirá el CONTENIDO de las tablas incluidas en el "
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
                if isinstance(error, mod_backup.BackupError):
                    messagebox.showerror(
                        "Importar base de datos", str(error)
                    )
                else:
                    messagebox.showerror(
                        "Importar base de datos",
                        f"No se pudo importar (no se cambió nada):\n{error}"
                    )
                return
            if resultado["modo"] == "completa":
                texto = "Base de datos importada y sustituida correctamente."
            else:
                lineas = [
                    f"• {tabla}: {filas} fila(s)"
                    for tabla, filas in sorted(
                        resultado["resumen"].items()
                    )
                ]
                texto = (
                    "Datos importados:\n"
                    + ("\n".join(lineas) or "(sin datos)")
                )
                if resultado["ignoradas"]:
                    texto += (
                        "\n\nTablas ignoradas (no existen en el esquema "
                        "actual): "
                        + ", ".join(sorted(resultado["ignoradas"]))
                    )

            if resultado["respaldo"]:
                texto += (
                    f"\n\nCopia de seguridad previa:\n{resultado['respaldo']}"
                )
            texto += (
                "\n\n⚠️ Reinicie la aplicación para que todos los módulos "
                "vean los datos actualizados."
            )
            messagebox.showinfo("Importación completada", texto)

        self._ocupar_botones_bd(True)
        en_hilo(self, lambda: mod_backup.importar_datos(ruta), al_terminar)
    
    def guardar_cambios(self):
        """Guarda todos los cambios de configuración"""
        try:
            self.config_manager.config_data.update({
                "tema": self.var_tema.get(),
                "tamaño_fuente": int(self.scale_tamaño.get()),
                "nombre_empresa": self.entry_nombre.get(),
                "mostrar_hora": self.var_hora.get(),
                "redondear_decimales": self.var_decimales.get(),
                "impresora_termica": (
                    None
                    if self.combo_impresora.get() in ("", "(Desactivada)")
                    else self.combo_impresora.get().removesuffix(" (no detectada)")
                ),
                "ancho_ticket": int(self.var_ancho_ticket.get()),
                "letra_ticket": next(
                    clave for clave, etiqueta in ETIQUETAS_LETRA.items()
                    if etiqueta == self.var_letra_ticket.get()
                ),
            })
            self.config_manager.save_config()
            
            messagebox.showinfo(
                "Éxito",
                "Cambios guardados correctamente.\n\n"
                "⚠️ Nota: Reinicia la aplicación para aplicar todos los cambios."
            )
            
            # Cerrar la ventana
            self.master.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar los cambios: {e}")
    
    def restablecer_defaults(self):
        """Restablece los valores por defecto"""
        if messagebox.askyesno("Confirmar", "¿Restablecer todos los valores a los predeterminados?"):
            default_config = {
                "tema": "claro",
                "tamaño_fuente": 14,
                "logo_path": None,
                "nombre_empresa": "Mi Empresa",
                "mostrar_hora": True,
                "redondear_decimales": 2,
                "escaner_activo": False,
                "impresora_termica": None,
                "ancho_ticket": 80,
                "letra_ticket": "muy_grande"
            }
            
            self.config_manager.config_data = default_config
            self.config_manager.save_config()
            
            # Actualizar controles
            self.var_tema.set("claro")
            self.scale_tamaño.set(14)
            self.entry_nombre.delete(0, "end")
            self.entry_nombre.insert(0, "Mi Empresa")
            self.var_hora.set(True)
            self.var_decimales.set(2)
            self.combo_impresora.current(0)
            self.var_ancho_ticket.set(80)
            self.var_letra_ticket.set(ETIQUETAS_LETRA["muy_grande"])
            self.logo_label.config(image="", text="📷\nSin logo")
            self.logo_image_preview = None
            
            messagebox.showinfo("Éxito", "Valores restablecidos correctamente")



