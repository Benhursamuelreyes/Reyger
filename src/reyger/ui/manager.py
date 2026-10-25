import logging
import os

from tkinter import Tk, Frame, PhotoImage, messagebox, ttk

try:
    from ttkthemes import ThemedStyle
except ImportError:
    ThemedStyle = None

from ..container import Container
from ..config import ConfigManager
from ..resources import get_bundled_path
from .ui import GEOMETRIA_PRINCIPAL, MINIMO_PRINCIPAL, aplicar_colores_por_defecto


log = logging.getLogger(__name__)


class Manager(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        aplicar_colores_por_defecto(self, self.colors)

        self.title("Reyger versión BETA")
        self.resizable(True, True)
        self.minsize(*MINIMO_PRINCIPAL)
        self.configure(bg=self.colors["bg_principal"])
        self.geometry(GEOMETRIA_PRINCIPAL)

        self._set_icon()

        self.Container = None
        self.construir_container()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    def _al_cerrar(self):
        """Hace la copia automática del día y cierra la aplicación.

        Un fallo en la copia se registra pero nunca impide cerrar.
        """
        from ..core import db
        from ..core.backup import BackupError

        try:
            db.optimizar()
        except Exception:
            log.warning("PRAGMA optimize falló al cerrar", exc_info=True)
        if ConfigManager().get("respaldo_automatico", True):
            try:
                from ..core.backup import respaldo_automatico

                ruta = respaldo_automatico()
                log.info("Copia automática guardada en %s", ruta)
            except BackupError as e:
                # Base dañada: es lo único que el usuario debe saber al cerrar.
                log.error("Copia automática no válida: %s", e)
                try:
                    messagebox.showwarning("Copia de seguridad", str(e), parent=self)
                except Exception:
                    pass
            except Exception:
                log.exception("No se pudo hacer la copia automática al cerrar")
        self.destroy()

    def _set_icon(self):
        # PNG pequeño para iconphoto (evita cargar el master 1024×1024).
        for size in ("assets/icono.png-32.png", "assets/icono.png-16.png"):
            path = get_bundled_path(size)
            if not os.path.exists(path):
                continue
            try:
                icono = PhotoImage(file=path)
                self.iconphoto(True, icono)
                return
            except Exception:
                continue
        ico = get_bundled_path("assets/icono.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def report_callback_exception(self, exc_type, exc_value, exc_tb):
        # Por defecto Tk imprime la traza en stderr, que en la app
        # empaquetada (sin consola) se pierde: se registra y se avisa.
        log.error("Error en un evento de la interfaz", exc_info=(exc_type, exc_value, exc_tb))
        try:
            messagebox.showerror(
                "Error",
                f"Ocurrió un error inesperado:\n\n{exc_value}\n\n"
                "El detalle se ha guardado en reyger.log.",
                parent=self,
            )
        except Exception:
            pass

    def construir_container(self):
        if self.Container is not None:
            self.Container.destroy()
        self.Container = Frame(self, bg=self.colors["bg_principal"])
        self.Container.pack(fill="both", expand=True)
        Container(self.Container, self)
        self.set_theme()

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
