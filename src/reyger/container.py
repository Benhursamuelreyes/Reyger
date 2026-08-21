import os
from tkinter import *
import tkinter as tk
from PIL import Image, ImageTk

from .ventas import Ventas
from .inventario import Inventario
from .clientes import Clientes
from .ajustes import Ajustes
from .presupuestos import Presupuestos
from .config import ConfigManager
from .resources import get_bundled_path


class Container(tk.Frame):
    def __init__(self, padre, controlador):
        super().__init__(padre)
        self.controlador = controlador
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        self.pack(fill="both", expand=True)
        self.widgets()

    def show_frames(self, container):
        top_level = tk.Toplevel(self)
        frame = container(top_level)
        frame.pack(fill="both", expand=True)
        top_level.geometry("1280x800")
        top_level.resizable(True, True)
        top_level.minsize(1100, 700)
        self._set_window_icon(top_level)
        top_level.transient(self.master)
        top_level.grab_set()
        top_level.focus_set()
        top_level.lift()

    @staticmethod
    def _set_window_icon(ventana):
        for name in ("assets/icono.png", "assets/icono.ico"):
            path = get_bundled_path(name)
            if not os.path.exists(path):
                continue
            try:
                if name.endswith(".png"):
                    icono = tk.PhotoImage(file=path)
                    ventana.iconphoto(True, icono)
                else:
                    ventana.iconbitmap(path)
                return
            except Exception:
                continue

    def ventas(self):
        self.show_frames(Ventas)

    def inventario(self):
        self.show_frames(Inventario)

    def clientes(self):
        self.show_frames(Clientes)

    def ajustes(self):
        self.show_frames(Ajustes)

    def presupuestos(self):
        self.show_frames(Presupuestos)

    def widgets(self):
        # Zona superior: logos
        frame_top = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_top.pack(fill="x", pady=30, padx=20)

        ruta = get_bundled_path("assets/img/logo.png")
        if os.path.exists(ruta):
            self.logo_image = Image.open(ruta)
            self.logo_image.thumbnail((760, 200), Image.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(self.logo_image)
            self.logo_label = tk.Label(
                frame_top, image=self.logo_image, bg=self.colors["bg_principal"]
            )
            self.logo_label.pack(side="left", padx=20)

        logo_path = self.config_manager.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            try:
                self.custom_logo_image = Image.open(logo_path)
                self.custom_logo_image.thumbnail((300, 80), Image.LANCZOS)
                self.custom_logo_image = ImageTk.PhotoImage(self.custom_logo_image)
                logo_label_custom = tk.Label(
                    frame_top,
                    image=self.custom_logo_image,
                    bg=self.colors["bg_principal"],
                )
                logo_label_custom.pack(side="right", padx=20)
            except Exception:
                pass

        # Zona central elástica
        frame_centro = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_centro.pack(fill="both", expand=True)

        # Zona inferior: botones de navegación (se reparten el ancho)
        frame_botones = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_botones.pack(fill="x", side="bottom", pady=40, padx=20)

        botones = [
            ("Ventas", "#f4b400", None, self.ventas),
            ("Inventario", "#c62e26", "white", self.inventario),
            ("Clientes", "#2ECC71", "white", self.clientes),
            ("Presupuestos", "#9B59B6", "white", self.presupuestos),
            ("Ajustes", "#17A2B8", "white", self.ajustes),
        ]
        for texto, bg, fg, comando in botones:
            boton = Button(
                frame_botones,
                bg=bg,
                fg=fg or "black",
                font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
                text=texto,
                command=comando,
            )
            boton.pack(side="left", expand=True, fill="x", padx=8, ipady=18)
