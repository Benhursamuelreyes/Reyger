import os

from tkinter import Tk, Frame, PhotoImage, ttk

try:
    from ttkthemes import ThemedStyle
except ImportError:
    ThemedStyle = None

from .container import Container
from .config import ConfigManager
from .resources import get_bundled_path


class Manager(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()

        self.title("Reyger versión BETA")
        self.resizable(False, False)
        self.configure(bg=self.colors["bg_principal"])
        self.geometry("800x400+120+20")

        self._set_icon()

        self.Container = Frame(self, bg=self.colors["bg_principal"])
        self.Container.pack(fill="both", expand=True)

        self.frames = {Container: None}
        self.load_frames()
        self.show_frame(Container)
        self.set_theme()

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

    def load_frames(self):
        for FrameClass in self.frames:
            frame = FrameClass(self.Container, self)
            self.frames[FrameClass] = frame

    def show_frame(self, frame_class):
        self.frames[frame_class].tkraise()

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
