from tkinter import Tk, Frame
from container import Container
from ttkthemes import ThemedStyle
import sys
import os

class Manager(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, ** kwargs)
        self.title("Caja registradora veersion 1.0")
        self.resizable(False, False)
        self.configure(bg="#C6D9E3")
        self.geometry("800x400+120+20")
        # ruta = self.rutas(r"icono.ico")
        # self.iconbitmap(ruta)
        
        self.Container = Frame(self, bg="#C6D9E3")
        self.Container.pack(fill="both", expand=True)
        
        self.frames = {
            Container: None
        }
        
        self.load_frames()
        
        self.show_frame(Container)
        
        self.set_theme()
        
    # def rutas(self, ruta):
    #     try:
    #         rutabase = sys.__MEIPASS
    #     except Exception:
    #         rutabase = os.path.abspath(".")
    #     return os.path.join(rutabase, ruta)

    def load_frames(self):
        for FrameClass in self.frames.keys():
            frame = FrameClass(self.Container, self)
            self.frames[FrameClass] = frame
            
    def show_frame(self, frame_class):
        frame = self.frames[frame_class]
        frame.tkraise()
        
    def set_theme(self):
        style = ThemedStyle(self)
        style.set_theme("breeze")
    
def main():
    app = Manager()
    app.mainloop()
    
if __name__ == "__main__":
    main()