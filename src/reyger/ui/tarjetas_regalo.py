"""Vista de gestión de Tarjetas Regalo / Vales de compra.

Permite crear tarjetas regalo (con código único y saldo inicial), listar
las existentes (código, saldo, estado) y recargar su saldo.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ..core import tarjetas_regalo as tr
from ..core import moneda as mod_moneda
from ..config import ConfigManager


class TarjetasRegalo(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.title("Tarjetas Regalo")
        self.configure(bg=self.colors["bg_principal"])
        self.geometry("780x640")
        self.minsize(680, 520)
        self.transient(master)
        self.grab_set()

        self.var_saldo = tk.StringVar()
        self.var_cargo_recarga = tk.StringVar()

        self._construir()
        self._recargar_lista()

    def _construir(self):
        bg = self.colors["bg_principal"]
        fg = self.colors["fg_texto"]
        fuente = f"sans {self.config_manager.get_tamaño_fuente()}"

        contenedor = tk.Frame(self, bg=bg)
        contenedor.pack(fill="both", expand=True, padx=15, pady=10)

        tk.Label(
            contenedor, text="TARJETAS REGALO / VALES", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold",
        ).pack(pady=(0, 8))

        # ── Crear nueva ──────────────────────────────────────────────────
        frame_nueva = tk.LabelFrame(
            contenedor, text="Crear nueva tarjeta", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_nueva.pack(fill="x", pady=6)

        tk.Label(frame_nueva, text="Saldo inicial:", bg=bg, fg=fg, font=fuente).pack(side="left")
        tk.Entry(
            frame_nueva, textvariable=self.var_saldo, width=12, font=fuente,
            bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
        ).pack(side="left", padx=8, ipady=3)
        btn_crear = tk.Button(
            frame_nueva, text="➕ Crear", bg="#27AE60", fg="white",
            font=fuente + " bold", command=self._crear,
        )
        btn_crear.pack(side="left", padx=8)

        # ── Listado ──────────────────────────────────────────────────────
        frame_lista = tk.LabelFrame(
            contenedor, text="Tarjetas emitidas", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_lista.pack(fill="both", expand=True, pady=6)

        columnas = ("codigo", "saldo_inicial", "saldo_actual", "estado", "fecha")
        self.tree = ttk.Treeview(
            frame_lista, columns=columnas, show="headings", height=10,
        )
        for col, titulo, ancho in [
            ("codigo", "Código", 200), ("saldo_inicial", "Saldo inicial", 120),
            ("saldo_actual", "Saldo actual", 120), ("estado", "Estado", 100),
            ("fecha", "Fecha", 160),
        ]:
            self.tree.heading(col, text=titulo)
            self.tree.column(col, width=ancho, anchor="center")
        self.tree.pack(fill="both", expand=True)

        # ── Recarga de la seleccionada ───────────────────────────────────
        frame_recarga = tk.LabelFrame(
            contenedor, text="Recargar tarjeta seleccionada", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_recarga.pack(fill="x", pady=6)

        tk.Label(frame_recarga, text="Importe a añadir:", bg=bg, fg=fg, font=fuente).pack(side="left")
        tk.Entry(
            frame_recarga, textvariable=self.var_cargo_recarga, width=12, font=fuente,
            bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
        ).pack(side="left", padx=8, ipady=3)
        btn_recargar = tk.Button(
            frame_recarga, text="💳 Recargar", bg="#0078D4", fg="white",
            font=fuente + " bold", command=self._recargar,
        )
        btn_recargar.pack(side="left", padx=8)

        btn_cerrar = tk.Button(
            contenedor, text="Cerrar", bg="#E74C3C", fg="white",
            font=fuente + " bold", padx=12, pady=8, command=self.destroy,
        )
        btn_cerrar.pack(side="right", pady=6)

    def _crear(self):
        try:
            saldo = float(self.var_saldo.get())
        except (TypeError, ValueError):
            messagebox.showerror("Error", "Ingrese un saldo inicial válido.")
            return
        if saldo <= 0:
            messagebox.showerror("Error", "El saldo inicial debe ser mayor que cero.")
            return
        tarjeta_id, codigo = tr.crear(saldo)
        messagebox.showinfo(
            "Tarjeta creada",
            f"Tarjeta regalo creada con código:\n{codigo}\n\nSaldo inicial: "
            f"{mod_moneda.format_currency(saldo)}",
        )
        self.var_saldo.set("")
        self._recargar_lista()

    def _recargar_lista(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for fila in tr.listar():
            self.tree.insert("", "end", values=(
                fila["codigo"],
                mod_moneda.format_currency(fila["saldo_inicial"] or 0),
                mod_moneda.format_currency(fila["saldo_actual"] or 0),
                fila["estado"],
                str(fila["fecha"])[:16],
            ))

    def _codigo_seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Recargar", "Seleccione una tarjeta de la lista.")
            return None
        return self.tree.item(sel[0], "values")[0]

    def _recargar(self):
        codigo = self._codigo_seleccionado()
        if codigo is None:
            return
        try:
            importe = float(self.var_cargo_recarga.get())
        except (TypeError, ValueError):
            messagebox.showerror("Error", "Ingrese un importe válido.")
            return
        if importe <= 0:
            messagebox.showerror("Error", "El importe debe ser mayor que cero.")
            return
        ok, mensaje = tr.recargar(codigo, importe)
        if not ok:
            messagebox.showerror("Error", mensaje)
            return
        messagebox.showinfo(
            "Recarga", f"Tarjeta {codigo} recargada.\nNuevo saldo: "
            f"{mod_moneda.format_currency(tr.saldo(codigo))}"
        )
        self.var_cargo_recarga.set("")
        self._recargar_lista()
