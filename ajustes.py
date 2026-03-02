import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
from config import ConfigManager

class Ajustes(tk.Frame):
    """Ventana de configuración y ajustes del sistema"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.pack(fill="both", expand=True)
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        
        self.logo_image_preview = None
        self.widgets()
    
    def rutas(self, ruta):
        try:
            rutabase = sys._MEIPASS
        except Exception:
            rutabase = os.path.abspath(".")
        return os.path.join(rutabase, ruta)
    
    def widgets(self):
        """Crea los widgets de la ventana de ajustes"""
        
        # Frame superior con título
        frame_titulo = tk.Frame(self, bg="#0078D4", height=80)
        frame_titulo.pack(fill="x")
        frame_titulo.pack_propagate(False)
        
        titulo = tk.Label(
            frame_titulo, 
            text="⚙️ AJUSTES Y CONFIGURACIÓN",
            bg="#0078D4",
            fg="white",
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold"
        )
        titulo.pack(pady=10)
        
        # Frame principal con scroll
        main_frame = tk.Frame(self, bg=self.colors["bg_principal"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
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
            width=50
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
                logo_dir = os.path.dirname(self.config_manager.config_file)
                logo_filename = os.path.join(logo_dir, "logo.png")
                
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
    
    def guardar_cambios(self):
        """Guarda todos los cambios de configuración"""
        try:
            self.config_manager.set("tema", self.var_tema.get())
            self.config_manager.set("tamaño_fuente", int(self.scale_tamaño.get()))
            self.config_manager.set("nombre_empresa", self.entry_nombre.get())
            self.config_manager.set("mostrar_hora", self.var_hora.get())
            self.config_manager.set("redondear_decimales", self.var_decimales.get())
            
            messagebox.showinfo(
                "Éxito",
                "Cambios guardados correctamente.\n\n"
                "⚠️ Nota: Reinicia la aplicación para aplicar todos los cambios."
            )
            
            # Cerrar la ventana
            self.master.master.withdraw()
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
                "redondear_decimales": 2
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
            self.logo_label.config(image="", text="📷\nSin logo")
            self.logo_image_preview = None
            
            messagebox.showinfo("Éxito", "Valores restablecidos correctamente")



