import gc
import os
from tkinter import *
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

from .ui.ventas import Ventas
from .ui.inventario import Inventario
from .ui.clientes import Clientes
from .ui.ajustes import Ajustes
from .ui.presupuestos import Presupuestos
from .ui.albaranes_ui import VentanaAlbaranes
from .config import ConfigManager
from .resources import get_bundled_path

#: Margen del logotipo respecto a los botones colindantes (5–10 px).
MARGEN_LOGO = 8


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

        def _al_destruir(evento):
            if evento.widget is not top_level:
                return
            # Recolección inmediata de los widgets e imágenes que el
            # frame dejó referenciados, sin esperar al ciclo de GC.
            self.after_idle(gc.collect)

        def _cerrar():
            captura = getattr(frame, "captura", None)
            if captura is not None:
                try:
                    captura.detener()
                except Exception:
                    pass
            try:
                top_level.grab_release()
            except Exception:
                pass
            top_level.destroy()

        top_level.protocol("WM_DELETE_WINDOW", _cerrar)
        top_level.bind("<Destroy>", _al_destruir)

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

    def presupuestos(self):
        self.show_frames(Presupuestos)

    def albaranes(self):
        ventana = getattr(self, "_ventana_albaranes", None)
        if ventana is not None and bool(ventana.winfo_exists()):
            ventana.deiconify()
            ventana.lift()
            ventana.focus_set()
            return
        self._ventana_albaranes = VentanaAlbaranes(self.winfo_toplevel())

    def ajustes(self):
        self.show_frames(Ajustes)

    def widgets(self):
        # Zona superior: logo personalizado de la empresa (si existe)
        frame_top = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_top.pack(fill="x", padx=20, pady=(30, 0))

        logo_path = self.config_manager.get("logo_path")
        if logo_path and os.path.exists(logo_path):
            try:
                self.custom_logo_original = Image.open(logo_path).convert("RGBA")
                self.custom_logo_original.thumbnail((300, 80), Image.LANCZOS)
                self.custom_logo_image = ImageTk.PhotoImage(self.custom_logo_original)
                logo_label_custom = tk.Label(
                    frame_top,
                    image=self.custom_logo_image,
                    bg=self.colors["bg_principal"],
                )
                logo_label_custom.pack(side="right", padx=20)
            except Exception:
                pass

        # Zona central elástica: el logotipo se escala para rellenarla
        frame_centro = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_centro.pack(fill="both", expand=True, padx=20)

        ruta = get_bundled_path("assets/img/logo.png")
        if os.path.exists(ruta):
            try:
                self.logo_original = Image.open(ruta).convert("RGBA")
            except Exception:
                self.logo_original = None
            if self.logo_original is not None:
                # Tamaño inicial acotado a 760x200 sin copiar el original
                escala0 = min(
                    760 / self.logo_original.width,
                    200 / self.logo_original.height,
                    1.0,
                )
                tamano0 = (
                    max(1, round(self.logo_original.width * escala0)),
                    max(1, round(self.logo_original.height * escala0)),
                )
                self.logo_image = self._render_logo(tamano0)
                self._tamano_logo_actual = tamano0
                self._redibujo_pendiente = None
                self.logo_label = tk.Label(
                    frame_centro,
                    image=self.logo_image,
                    bg=self.colors["bg_principal"],
                )
                self.logo_label.place(relx=0.5, rely=0.5, anchor="center")
                frame_centro.bind("<Configure>", self._ajustar_logo)

        # Zona inferior: botones de navegación (se reparten el ancho).
        # El hueco con el logotipo lo fija MARGEN_LOGO al escalarlo.
        self.frame_botones = tk.Frame(self, bg=self.colors["bg_principal"])
        self.frame_botones.pack(fill="x", side="bottom", padx=20, pady=(0, 10))

        botones = [
            ("Ventas", "#f4b400", None, self.ventas),
            ("Inventario", "#c62e26", "white", self.inventario),
            ("Clientes", "#2ECC71", "white", self.clientes),
            ("Presupuestos", "#9B59B6", "white", self.presupuestos),
            ("Albaranes", "#E67E22", "white", self.albaranes),
            ("Ajustes", "#17A2B8", "white", self.ajustes),
        ]
        for texto, bg, fg, comando in botones:
            boton = Button(
                self.frame_botones,
                bg=bg,
                fg=fg or "black",
                font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
                text=texto,
                command=comando,
            )
            boton.pack(side="left", expand=True, fill="x", padx=8, ipady=18)

    def _render_logo(self, tamano):
        """Genera el PhotoImage al tamaño pedido con consumo mínimo de RAM.

        Para reducciones grandes baja primero por factores enteros
        (``reduce``), de modo que el LANCZOS final opera sobre pocos
        píxeles. El llamador es dueño del objeto devuelto.
        """
        origen = self.logo_original
        factor = min(
            max(1, origen.width // max(1, tamano[0])),
            max(1, origen.height // max(1, tamano[1])),
        )
        if factor > 1:
            origen = origen.reduce(factor)
        return ImageTk.PhotoImage(origen.resize(tamano, Image.LANCZOS))

    def _ajustar_logo(self, evento=None):
        """Reacciona al redimensionado con debounce para no repintar en ráfaga."""
        if getattr(self, "logo_original", None) is None:
            return
        if evento is not None:
            self._configure_ancho = evento.width
            self._configure_alto = evento.height
        self._autoverificaciones = 0
        if self._redibujo_pendiente is not None:
            self.after_cancel(self._redibujo_pendiente)
        self._redibujo_pendiente = self.after(120, self._aplicar_escala_logo)

    def _aplicar_escala_logo(self):
        """Escala el logotipo (conservando ratio y canal alfa) para rellenar
        el espacio libre, dejando MARGEN_LOGO hasta los bordes del área."""
        self._redibujo_pendiente = None
        contenedor = self.logo_label.master
        # Medida más conservadora entre el último <Configure> y el tamaño
        # real vigente: evita solapes con la botonera durante transiciones
        # de redimensionado, cuando ambas medidas pueden no coincidir.
        ancho_actual = contenedor.winfo_width()
        alto_actual = contenedor.winfo_height()
        disponible_w = (
            min(ancho_actual, getattr(self, "_configure_ancho", ancho_actual))
            - 2 * MARGEN_LOGO
        )
        disponible_h = (
            min(alto_actual, getattr(self, "_configure_alto", alto_actual))
            - 2 * MARGEN_LOGO
        )
        if disponible_w <= 0 or disponible_h <= 0:
            return
        escala = min(
            disponible_w / self.logo_original.width,
            disponible_h / self.logo_original.height,
        )
        nuevo_tamano = (
            max(1, round(self.logo_original.width * escala)),
            max(1, round(self.logo_original.height * escala)),
        )
        if nuevo_tamano == self._tamano_logo_actual:
            return
        self._tamano_logo_actual = nuevo_tamano
        imagen_anterior = self.logo_image
        self.logo_image = self._render_logo(nuevo_tamano)
        self.logo_label.config(image=self.logo_image)
        # Libera en el acto el buffer PIL y la imagen Tcl anteriores
        # (ImageTk solo la borra al pasar por el recolector de basura).
        del imagen_anterior
        # Auto-verificación: si la geometría siguió moviéndose tras aplicar,
        # hasta dos pasadas extra corrigen el tamaño definitivo.
        self._autoverificaciones = getattr(self, "_autoverificaciones", 0)
        if self._autoverificaciones < 2:
            self._autoverificaciones += 1
            self.after(200, self._aplicar_escala_logo)
