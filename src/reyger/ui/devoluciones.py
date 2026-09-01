"""Vista de Devoluciones / Rectificaciones de ventas.

Permite seleccionar una factura emitida, ver sus productos y la cantidad
disponible, elegir cuánto devolver (parcial o total), el método de
reembolso (Efectivo, Tarjeta o Vale/Tarjeta regalo) y confirmar, lo que
reintegra el stock y emite el ticket de rectificación.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ..core import db
from ..core import devoluciones
from ..config import ConfigManager
from ..core.hilos import en_hilo
from . import business_profile as bp


class Devoluciones(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.title("Devoluciones")
        self.configure(bg=self.colors["bg_principal"])
        self.geometry("820x680")
        self.minsize(700, 560)
        self.transient(master)
        self.grab_set()

        self.var_factura = tk.StringVar()
        self.var_metodo = tk.StringVar(value="Efectivo")
        self.var_usuario = tk.StringVar()
        self.var_motivo = tk.StringVar()
        self.productos = []
        self.entries_cantidad = {}

        self._construir()

    def _construir(self):
        bg = self.colors["bg_principal"]
        fg = self.colors["fg_texto"]
        fuente = f"sans {self.config_manager.get_tamaño_fuente()}"

        contenedor = tk.Frame(self, bg=bg)
        contenedor.pack(fill="both", expand=True, padx=15, pady=10)

        tk.Label(
            contenedor, text="DEVOLUCIONES / RECTIFICACIONES", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold",
        ).pack(pady=(0, 8))

        # ── Selección de factura ─────────────────────────────────────────
        frame_sel = tk.LabelFrame(
            contenedor, text="Seleccionar venta", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_sel.pack(fill="x", pady=6)

        facturas = [str(r["factura"]) for r in db.query(
            "SELECT DISTINCT factura FROM ventas ORDER BY factura DESC"
        )]
        tk.Label(frame_sel, text="Nº de factura:", bg=bg, fg=fg, font=fuente).pack(side="left")
        combo = ttk.Combobox(
            frame_sel, textvariable=self.var_factura, values=facturas,
            state="readonly", width=14, font=fuente,
        )
        combo.pack(side="left", padx=10)
        btn_cargar = tk.Button(
            frame_sel, text="Cargar productos", bg="#0078D4", fg="white",
            font=fuente + " bold", command=self._cargar,
        )
        btn_cargar.pack(side="left", padx=10)

        # ── Productos de la factura ──────────────────────────────────────
        frame_prod = tk.LabelFrame(
            contenedor, text="Productos a devolver", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_prod.pack(fill="both", expand=True, pady=6)

        cab = tk.Frame(frame_prod, bg=bg)
        cab.pack(fill="x")
        tk.Label(cab, text="Producto", bg=bg, fg=fg, font=fuente + " bold",
                 width=30, anchor="w").pack(side="left", padx=6)
        tk.Label(cab, text="Disponible", bg=bg, fg=fg, font=fuente + " bold",
                 width=12, anchor="center").pack(side="left")
        tk.Label(cab, text="A devolver", bg=bg, fg=fg, font=fuente + " bold",
                 width=12, anchor="center").pack(side="left")

        self.frame_lineas = tk.Frame(frame_prod, bg=bg)
        self.frame_lineas.pack(fill="both", expand=True)
        tk.Label(
            self.frame_lineas, text="Seleccione una factura para ver sus productos.",
            bg=bg, fg=fg, font=fuente, pady=20,
        ).pack()

        # ── Datos de la devolución ───────────────────────────────────────
        frame_datos = tk.LabelFrame(
            contenedor, text="Datos de la devolución", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_datos.pack(fill="x", pady=6)

        tk.Label(frame_datos, text="Usuario:", bg=bg, fg=fg, font=fuente).grid(
            row=0, column=0, sticky="w", padx=6, pady=2)
        tk.Entry(frame_datos, textvariable=self.var_usuario, width=24, font=fuente,
                 bg=self.colors["entry_bg"], fg=self.colors["entry_fg"]).grid(
            row=0, column=1, sticky="ew", padx=6, pady=2, ipady=3)

        tk.Label(frame_datos, text="Motivo:", bg=bg, fg=fg, font=fuente).grid(
            row=1, column=0, sticky="w", padx=6, pady=2)
        tk.Entry(frame_datos, textvariable=self.var_motivo, width=40, font=fuente,
                 bg=self.colors["entry_bg"], fg=self.colors["entry_fg"]).grid(
            row=1, column=1, sticky="ew", padx=6, pady=2, ipady=3)

        tk.Label(frame_datos, text="Reembolso:", bg=bg, fg=fg, font=fuente).grid(
            row=2, column=0, sticky="w", padx=6, pady=2)
        frame_met = tk.Frame(frame_datos, bg=bg)
        frame_met.grid(row=2, column=1, sticky="w", padx=6)
        for texto, valor in [("Efectivo", "Efectivo"), ("Tarjeta", "Tarjeta"), ("Vale / Tarjeta Regalo", "Vale")]:
            tk.Radiobutton(
                frame_met, text=texto, value=valor, variable=self.var_metodo,
                bg=bg, fg=fg, font=fuente + " bold", selectcolor=self.colors["bg_secundario"],
            ).pack(side="left", padx=(0, 14))

        frame_acciones = tk.Frame(contenedor, bg=bg)
        frame_acciones.pack(fill="x", pady=10)
        btn_confirmar = tk.Button(
            frame_acciones, text="🔄 Procesar devolución", bg="#27AE60",
            fg="white", font=fuente + " bold", padx=12, pady=8,
            command=self._confirmar,
        )
        btn_confirmar.pack(side="left", padx=4)
        btn_cerrar = tk.Button(
            frame_acciones, text="Cerrar", bg="#E74C3C", fg="white",
            font=fuente + " bold", padx=12, pady=8, command=self.destroy,
        )
        btn_cerrar.pack(side="right", padx=4)

    def _cargar(self):
        factura = self.var_factura.get().strip()
        if not factura:
            messagebox.showwarning("Devoluciones", "Seleccione una factura.")
            return
        try:
            self.productos = devoluciones.productos_de_factura(int(factura))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la factura: {e}")
            return

        for w in self.frame_lineas.winfo_children():
            w.destroy()
        self.entries_cantidad.clear()

        if not self.productos:
            messagebox.showinfo(
                "Devoluciones",
                "La factura no tiene productos devolvibles.",
            )
            return

        for fila in self.productos:
            row = tk.Frame(self.frame_lineas, bg=self.colors["bg_principal"])
            row.pack(fill="x", pady=1)
            tk.Label(
                row, text=fila["nombre"], bg=self.colors["bg_principal"],
                fg=self.colors["fg_texto"], width=30, anchor="w",
                font=f"sans {self.config_manager.get_tamaño_fuente()}",
            ).pack(side="left", padx=6)
            tk.Label(
                row, text=str(fila["disponible"]), width=12, anchor="center",
                bg=self.colors["bg_principal"], fg=self.colors["fg_texto"],
                font=f"sans {self.config_manager.get_tamaño_fuente()}",
            ).pack(side="left")
            var = tk.StringVar()
            tk.Entry(
                row, textvariable=var, width=10, justify="center",
                bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
                font=f"sans {self.config_manager.get_tamaño_fuente()}",
            ).pack(side="left", padx=6, ipady=2)
            self.entries_cantidad[fila["nombre"]] = (var, fila["disponible"])

    def _lineas_seleccionadas(self):
        devolver = []
        for nombre, (var, _disp) in self.entries_cantidad.items():
            texto = var.get().strip()
            if texto:
                try:
                    cantidad = int(float(texto))
                except (TypeError, ValueError):
                    cantidad = 0
                if cantidad > 0:
                    devolver.append((nombre, cantidad))
        return devolver

    def _confirmar(self):
        lineas = self._lineas_seleccionadas()
        if not lineas:
            messagebox.showwarning(
                "Devoluciones", "Indique al menos un producto y su cantidad a devolver."
            )
            return
        total_a_devolver = sum(
            p["precio"] * c for p in self.productos
            for n, c in lineas if n == p["nombre"]
        )
        ok = messagebox.askyesno(
            "Confirmar devolución",
            f"Factura: {self.var_factura.get()}\n"
            f"Productos a devolver: {len(lineas)}\n"
            f"Importe a devolver: {total_a_devolver:.2f}\n"
            f"Reembolso: {self.var_metodo.get()}\n\n"
            "¿Confirmar la devolución?",
        )
        if not ok:
            return
        try:
            resultado = devoluciones.procesar_devolucion(
                int(self.var_factura.get()),
                lineas,
                metodo_reembolso=self.var_metodo.get(),
                usuario=self.var_usuario.get(),
                motivo=self.var_motivo.get(),
            )
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo procesar la devolución: {e}")
            return

        self._imprimir(resultado)

        texto = (
            f"Devolución registrada correctamente.\n"
            f"Factura original: {resultado['factura_original']}\n"
            f"Importe devuelto: {resultado['importe_devuelto']:.2f}\n"
            f"Reembolso: {resultado['metodo_reembolso']}"
        )
        if resultado.get("codigo_vale"):
            texto += f"\nVale emitido: {resultado['codigo_vale']}"
        messagebox.showinfo("Devolución registrada", texto)
        self.destroy()

    def _imprimir(self, resultado):
        config = ConfigManager()
        impresora = config.get("impresora_termica")
        if not impresora:
            return
        from ..hardware.impresion_termica import (
            ANCHO_58MM, ANCHO_80MM, imprimir_ticket_devolucion,
        )
        ancho = ANCHO_58MM if config.get("ancho_ticket") == 58 else ANCHO_80MM
        letra = config.get("letra_ticket", "muy_grande")
        empresa = bp.nombre_empresa()
        logo = None
        negocio = {
            "nombre": bp.obtener_campo("nombre"),
            "nombre_comercial": bp.obtener_campo("nombre_comercial"),
            "nif": bp.obtener_campo("nif"),
            "direccion": bp.obtener_campo("direccion"),
            "codigo_postal": bp.obtener_campo("codigo_postal"),
            "provincia": bp.obtener_campo("provincia"),
            "telefono": bp.obtener_campo("telefono"),
            "email": bp.obtener_campo("email"),
        }
        resumen = {
            "factura_original": resultado["factura_original"],
            "fecha": resultado["fecha"],
            "lineas": resultado["lineas"],
            "importe_devuelto": resultado["importe_devuelto"],
            "metodo_reembolso": resultado["metodo_reembolso"],
            "codigo_vale": resultado.get("codigo_vale"),
            "usuario": self.var_usuario.get(),
        }

        def trabajo():
            return imprimir_ticket_devolucion(
                resumen, empresa=empresa, ancho=ancho, letra=letra,
                impresora=impresora, logo=logo, negocio=negocio,
            )

        def al_terminar(res, error):
            if error is not None:
                messagebox.showwarning("Impresora térmica", f"No se pudo imprimir: {error}")

        en_hilo(self, trabajo, al_terminar)
