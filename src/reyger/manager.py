import os

from tkinter import Tk, Frame, PhotoImage, ttk

try:
    from ttkthemes import ThemedStyle
except ImportError:
    ThemedStyle = None

from .container import Container
from .config import ConfigManager
from .resources import get_bundled_path
from .ui import GEOMETRIA_PRINCIPAL, MINIMO_PRINCIPAL


class Manager(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()

        self.title("Reyger versión BETA")
        self.resizable(True, True)
        self.minsize(*MINIMO_PRINCIPAL)
        self.configure(bg=self.colors["bg_principal"])
        self.geometry(GEOMETRIA_PRINCIPAL)

        self._set_icon()

        self.usuario_actual = None
        self.sesion_actual = None
        self.Container = None
        self.mostrar_login()

    def _set_icon(self):
        for name in ("assets/icono.png", "assets/icono.ico"):
            path = get_bundled_path(name)
            if not os.path.exists(path):
                continue
            try:
                if name.endswith(".png"):
                    icono = PhotoImage(file=path)
                    self.iconphoto(True, icono)
                else:
                    self.iconbitmap(path)
                return
            except Exception:
                continue

    def mostrar_login(self):
        from .login import DialogoLogin

        DialogoLogin(self, al_acceder=self._iniciar_sesion)

    def _iniciar_sesion(self, usuario):
        from .sesiones import abrir_sesion

        self.usuario_actual = usuario
        try:
            self.sesion_actual = abrir_sesion(usuario["id"])
        except Exception:
            self.sesion_actual = None
        datos_sesion = dict(usuario)
        datos_sesion["sesion_id"] = self.sesion_actual
        self.construir_container(datos_sesion)

    def construir_container(self, usuario):
        if self.Container is not None:
            self.Container.destroy()
        self.Container = Frame(self, bg=self.colors["bg_principal"])
        self.Container.pack(fill="both", expand=True)
        Container(self.Container, self, usuario=usuario)
        self.set_theme()

    def cerrar_sesion(self):
        from .sesiones import cerrar_sesion

        cerrar_sesion(self.sesion_actual)
        self.sesion_actual = None
        self.usuario_actual = None
        self.mostrar_login()

    def set_theme(self):
        if ThemedStyle is not None:
            style = ThemedStyle(self)
            if self.config_manager.get("tema") == "oscuro":
                style.set_theme("equilux")
            else:
                style.set_theme("breeze")
        else:
            style = ttk.Style(self)
            style.theme_use("clam")


def main():
    app = Manager()
    app.mainloop()


if __name__ == "__main__":
    main()
