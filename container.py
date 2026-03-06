import os
import sys
from tkinter import *
import tkinter as tk
from ventas import Ventas
from inventario import Inventario
from ajustes import Ajustes
from PIL import Image, ImageTk
from config import ConfigManager

class Container(tk.Frame):
    def __init__(self, padre, controlador):
        super().__init__(padre)
        self.controlador = controlador
        self.config_manager = ConfigManager()
        self.pack()
        self.place(x=0, y=0, width=800, height=400)
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        self.widgets()
    
    def rutas(self, ruta):
        try:
            rutabase = sys._MEIPASS
        except Exception:
            rutabase = os.path.abspath(".")
        return os.path.join(rutabase, ruta)
        
    def show_frames(self, container):
        top_level = tk.Toplevel(self)
        frame = container(top_level)
        frame.pack(fill="both", expand=True)
        top_level.geometry("1100x650+120+20")
        top_level.resizable(False, False)
        ruta = self.rutas(r"icono.ico")
        top_level.iconbitmap(ruta)
        
        top_level.transient(self.master)
        top_level.grab_set()
        top_level.focus_set()
        top_level.lift()
        
    def ventas(self):
        self.show_frames(Ventas)
        
    def inventario(self):
        self.show_frames(Inventario)
    
    def ajustes(self):
        self.show_frames(Ajustes)
        
    def widgets(self):
        frame1 = tk.Frame(self, bg=self.colors["bg_principal"])
        frame1.pack()
        frame1.place(x=0, y=0, width=800, height=400)
        
        # Logo
        ruta = self.rutas(r"img/logo.png")
        if os.path.exists(ruta):
            self.logo_image = Image.open(ruta)
            self.logo_image = self.logo_image.resize((300, 80))
            self.logo_image = ImageTk.PhotoImage(self.logo_image)
            self.logo_label = tk.Label(frame1, image=self.logo_image, bg=self.colors["bg_principal"])
            self.logo_label.place(x=250, y=20)
        
        # Botón de Ventas
        btnVentas = Button(
            frame1, 
            bg="#f4b400", 
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold", 
            text="🛒 Ir a ventas", 
            command=self.ventas
        )
        btnVentas.place(x=30, y=200, width=230, height=70)
        
        # Botón de Inventario
        btnInventario = Button(
            frame1, 
            bg="#c62e26", 
            fg="white", 
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold", 
            text="📦 Ir a inventario", 
            command=self.inventario
        )
        btnInventario.place(x=285, y=200, width=230, height=70)
        
        # Botón de Ajustes
        btnAjustes = Button(
            frame1, 
            bg="#17A2B8", 
            fg="white", 
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold", 
            text="⚙️ Ajustes", 
            command=self.ajustes
        )
        btnAjustes.place(x=540, y=200, width=230, height=70)
        
        # Logo personalizado si existe
        logo_path = self.config_manager.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            try:
                self.custom_logo_image = Image.open(logo_path)
                self.custom_logo_image = self.custom_logo_image.resize((300, 80))
                self.custom_logo_image = ImageTk.PhotoImage(self.custom_logo_image)
                
                # Crear un Frame sobre el logo para mostrar el personalizado
                logo_frame = tk.Frame(frame1, bg=self.colors["bg_principal"])
                logo_frame.place(x=250, y=20, width=300, height=80)
                
                logo_label_custom = tk.Label(
                    logo_frame, 
                    image=self.custom_logo_image, 
                    bg=self.colors["bg_principal"]
                )
                logo_label_custom.pack(fill="both", expand=True)
            except:
                pass