from tkinter import Tk, Frame
from container import Container
from ttkthemes import ThemedStyle
from config import ConfigManager
import sys
import os

class Manager(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, ** kwargs)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        
        self.title("Caja registradora versión 1.0")
        self.resizable(False, False)
        self.configure(bg=self.colors["bg_principal"])
        self.geometry("800x400+120+20")
        ruta = self.rutas(r"icono.ico")
        self.iconbitmap(ruta)
        
        self.Container = Frame(self, bg=self.colors["bg_principal"])
        self.Container.pack(fill="both", expand=True)
        
        self.frames = {
            Container: None
        }
        
        self.load_frames()
        
        self.show_frame(Container)
        
        self.set_theme()
        
    def rutas(self, ruta):
        try:
            rutabase = sys.__MEIPASS
        except Exception:
            rutabase = os.path.abspath(".")
        return os.path.join(rutabase, ruta)

    def load_frames(self):
        for FrameClass in self.frames.keys():
            frame = FrameClass(self.Container, self)
            self.frames[FrameClass] = frame
            
    def show_frame(self, frame_class):
        frame = self.frames[frame_class]
        frame.tkraise()
        
    def set_theme(self):
        style = ThemedStyle(self)
        if self.config_manager.get("tema") == "oscuro":
            style.set_theme("equilux")  # Tema oscuro
        else:
            style.set_theme("breeze")  # Tema claro
    
def main():
    app = Manager()
    app.mainloop()
    
if __name__ == "__main__":
    main()