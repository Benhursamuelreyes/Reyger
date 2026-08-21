"""Diálogo de inicio de sesión modal."""

import tkinter as tk
from tkinter import ttk, messagebox

from . import auth

INTENTOS_MAXIMOS = 3


class DialogoLogin(tk.Toplevel):
    """Ventana modal de credenciales.

    Llama a ``al_acceder(usuario)`` con el dict del usuario autenticado.
    Tras ``INTENTOS_MAXIMOS`` fallos cierra la aplicación.
    """

    def __init__(self, root, al_acceder):
        super().__init__(root)
        self.root = root
        self.al_acceder = al_acceder
        self.intentos = INTENTOS_MAXIMOS

        self.title("Iniciar sesión - Reyger")
        self.geometry("440x360")
        self.resizable(False, False)
        self.configure(bg="#C6D9E3")
        self.transient(root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._salir)

        tk.Label(
            self, text="Reyger", bg="#C6D9E3", fg="#2C3E50",
            font="sans 28 bold",
        ).pack(pady=(30, 5))
        tk.Label(
            self, text="Introduzca sus credenciales", bg="#C6D9E3",
            font="sans 12",
        ).pack(pady=(0, 20))

        frame_form = tk.Frame(self, bg="#C6D9E3")
        frame_form.pack()

        tk.Label(
            frame_form, text="Usuario:", bg="#C6D9E3",
            font="sans 13 bold",
        ).grid(row=0, column=0, sticky="e", padx=10, pady=10)
        self.entry_usuario = ttk.Entry(frame_form, font="sans 13", width=22)
        self.entry_usuario.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(
            frame_form, text="Contraseña:", bg="#C6D9E3",
            font="sans 13 bold",
        ).grid(row=1, column=0, sticky="e", padx=10, pady=10)
        self.entry_password = ttk.Entry(
            frame_form, show="•", font="sans 13", width=22
        )
        self.entry_password.grid(row=1, column=1, padx=10, pady=10)

        self.boton_entrar = tk.Button(
            self, text="Entrar", command=self.intentar_acceder,
            bg="#27AE60", fg="white", font="sans 14 bold",
        )
        self.boton_entrar.pack(fill="x", padx=60, pady=(25, 5), ipady=6)

        self.bind("<Return>", lambda e: self.intentar_acceder())
        self.bind("<Escape>", lambda e: self._salir())

        self._centrar()
        self.entry_usuario.focus_set()

    def _centrar(self):
        self.update_idletasks()
        ancho, alto = 440, 360
        x = (self.winfo_screenwidth() - ancho) // 2
        y = (self.winfo_screenheight() - alto) // 3
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

    def intentar_acceder(self):
        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get()
        if not usuario or not password:
            messagebox.showwarning(
                "Iniciar sesión", "Introduzca usuario y contraseña"
            )
            return
        datos = auth.autenticar(usuario, password)
        if datos is None:
            self.intentos -= 1
            if self.intentos <= 0:
                messagebox.showerror(
                    "Iniciar sesión",
                    "Se han agotado los intentos. La aplicación se cerrará.",
                )
                self.root.destroy()
                return
            messagebox.showwarning(
                "Iniciar sesión",
                f"Credenciales incorrectas.\n"
                f"Intentos restantes: {self.intentos}",
            )
            self.entry_password.delete(0, tk.END)
            return
        self.grab_release()
        self.destroy()
        self.al_acceder(datos)

    def _salir(self):
        if messagebox.askyesno("Salir", "¿Desea salir de Reyger?"):
            self.root.destroy()
