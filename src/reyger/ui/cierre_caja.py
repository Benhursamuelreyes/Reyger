"""Vista de Cierre de Caja y Conteo de Caja (arqueo).

Permite seleccionar el período de ventas a arquear, contar el efectivo
físico desglosado por denominaciones, contrastarlo con el total esperado
y guardar/imprimir el informe de cierre en la impresora térmica.
"""
import datetime
import time
import tkinter as tk
from tkinter import ttk, messagebox

from ..core import cierre_caja
from ..core import moneda as mod_moneda
from ..config import ConfigManager
from ..core.hilos import en_hilo
from ..hardware.impresion_termica import (
    ANCHO_58MM,
    ANCHO_80MM,
    imprimir_ticket_arqueo,
)
from . import business_profile as bp


def _a_iso_utc(dt_local):
    """Convierte un datetime local a string ISO en UTC (formato BD)."""
    offset = -time.timezone
    if time.localtime().tm_isdst:
        offset += time.altzone - time.timezone
    utc = dt_local + datetime.timedelta(seconds=offset)
    return utc.strftime("%Y-%m-%d %H:%M:%S")


class CierreCaja(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.title("Cierre de Caja · Arqueo")
        self.configure(bg=self.colors["bg_principal"])
        self.geometry("820x780")
        self.minsize(700, 600)
        self.transient(master)
        self.grab_set()

        self.var_usuario = tk.StringVar()
        self.var_desde = tk.StringVar()
        self.var_hasta = tk.StringVar()
        self.var_notas = tk.StringVar()

        self.resumen = None
        self.ingreso_manual = 0.0
        self.retiro_manual = 0.0
        self.entries_conteo = {}

        self._inicial_fechas()
        self._construir()

    def _inicial_fechas(self):
        ahora = datetime.datetime.now()
        hoy = ahora.strftime("%d/%m/%Y")
        self.var_desde.set(f"{hoy} 00:00")
        self.var_hasta.set(ahora.strftime("%d/%m/%Y %H:%M"))

    def _crear_scrollable(self, padre):
        """Envuelve el contenido en un contenedor con scrollbar vertical.

        Devuelve el ``Frame`` interior en el que se empaqueta el contenido.
        El scroll se recalcula en cada ``<Configure>`` para responder al
        cambio de tamaño de la ventana.
        """
        bg = self.colors["bg_principal"]
        lienzo = tk.Canvas(padre, bg=bg, highlightthickness=0, bd=0)
        barra = ttk.Scrollbar(padre, orient="vertical", command=lienzo.yview)
        interior = tk.Frame(lienzo, bg=bg)
        interior.bind(
            "<Configure>",
            lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")),
        )
        ventana = lienzo.create_window((0, 0), window=interior, anchor="nw")

        def _ajustar_ancho(_evento=None):
            lienzo.itemconfigure(ventana, width=lienzo.winfo_width())

        lienzo.bind("<Configure>", _ajustar_ancho)
        interior.bind("<Configure>", lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        return interior

    def _construir(self):
        bg = self.colors["bg_principal"]
        fg = self.colors["fg_texto"]
        fuente = f"sans {self.config_manager.get_tamaño_fuente()}"

        contenedor = tk.Frame(self, bg=bg)
        contenedor.pack(fill="both", expand=True, padx=15, pady=(10, 0))

        titulo = tk.Label(
            contenedor, text="CIERRE DE CAJA · ARQUEO",
            bg=bg, fg=fg, font=f"sans {self.config_manager.get_tamaño_fuente('titulo')} bold",
        )
        titulo.pack(pady=(0, 6))

        # ── Área central con scroll vertical dinámico ───────────────────
        area_scroll = tk.Frame(contenedor, bg=bg)
        area_scroll.pack(fill="both", expand=True)
        cuerpo = self._crear_scrollable(area_scroll)

        # ── Datos del arqueo ────────────────────────────────────────────
        frame_datos = tk.LabelFrame(
            cuerpo, text="Datos del arqueo", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_datos.pack(fill="x", pady=6, padx=6)

        self._fila_entry(frame_datos, "Usuario:", self.var_usuario, 0, 22)
        self._fila_entry(frame_datos, "Desde (DD/MM/AAAA HH:MM):", self.var_desde, 1, 18)
        self._fila_entry(frame_datos, "Hasta (DD/MM/AAAA HH:MM):", self.var_hasta, 2, 18)

        frame_botones_datos = tk.Frame(frame_datos, bg=bg)
        frame_botones_datos.grid(row=3, column=1, sticky="w", pady=(6, 0))
        btn_hoy = tk.Button(
            frame_botones_datos, text="Hoy", bg=self.colors["bg_boton"], fg="white",
            font=fuente + " bold", command=self._fijar_hoy, padx=10,
        )
        btn_hoy.pack(side="left", padx=(0, 6))
        btn_calcular = tk.Button(
            frame_botones_datos, text="Calcular resumen", bg="#0078D4", fg="white",
            font=fuente + " bold", command=self._calcular, padx=10,
        )
        btn_calcular.pack(side="left")

        # ── Resumen de ventas ───────────────────────────────────────────
        frame_resumen = tk.LabelFrame(
            cuerpo, text="Resumen de ventas del período", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_resumen.pack(fill="x", pady=6, padx=6)
        self.labels_resumen = {}
        for fila, (clave, etiqueta) in enumerate([
            ("total_ventas", "Total de ventas"),
            ("efectivo_neto", "Efectivo (neto esperado)"),
            ("tarjeta", "Tarjeta"),
            ("ingreso_manual", "Ingresos manuales"),
            ("retiro_manual", "Retiros manuales"),
            ("total_esperado", "TOTAL ESPERADO EN CAJA"),
        ]):
            row = tk.Frame(frame_resumen, bg=bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=etiqueta, bg=bg, fg=fg, font=fuente, anchor="w").pack(side="left")
            val = tk.Label(row, text="-", bg=bg, fg=fg, font=fuente + " bold", anchor="e")
            val.pack(side="right")
            self.labels_resumen[clave] = val

        # ── Conteo por denominaciones (tabla vertical) ──────────────────
        frame_conteo = tk.LabelFrame(
            cuerpo, text="Conteo de efectivo físico", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_conteo.pack(fill="x", pady=6, padx=6)

        # Cabecera de la tabla (Denominación | Cantidad | Subtotal), fila 0
        # del mismo grid que las denominaciones para alinear las columnas.
        tk.Label(frame_conteo, text="Denominación", bg=bg, fg=fg, font=fuente + " bold",
                 width=20, anchor="w").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        tk.Label(frame_conteo, text="Cantidad", bg=bg, fg=fg, font=fuente + " bold",
                 width=14, anchor="w").grid(row=0, column=1, sticky="w", padx=6, pady=2)
        tk.Label(frame_conteo, text="Subtotal", bg=bg, fg=fg, font=fuente + " bold",
                 width=18, anchor="e").grid(row=0, column=2, sticky="e", padx=6, pady=2)
        frame_conteo.grid_columnconfigure(0, weight=0)
        frame_conteo.grid_columnconfigure(1, weight=1, minsize=80)
        frame_conteo.grid_columnconfigure(2, weight=0)

        # Cada denominación en su propia fila vertical (nunca una fila ancha)
        for denom in cierre_caja.denominaciones():
            self._fila_denominacion(frame_conteo, denom)

        # ── Notas y movimientos ─────────────────────────────────────────
        frame_notas = tk.LabelFrame(
            cuerpo, text="Notas y movimientos", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=8,
        )
        frame_notas.pack(fill="x", pady=6, padx=6)
        tk.Label(frame_notas, text="Notas:", bg=bg, fg=fg, font=fuente).pack(anchor="w")
        entrada_notas = tk.Entry(frame_notas, textvariable=self.var_notas,
                                 font=fuente, bg=self.colors["entry_bg"], fg=self.colors["entry_fg"])
        entrada_notas.pack(fill="x", pady=(2, 0), ipady=3)
        txt = ("Para registrar un ingreso o retiro manual, agrégalo en movimientos "
               "de caja y vuelve a calcular el resumen para que se refleje en el total esperado.")
        tk.Label(frame_notas, text=txt, bg=bg, fg=fg,
                 font=f"sans {self.config_manager.get_tamaño_fuente('pequeño')}",
                 justify="left", wraplength=700).pack(anchor="w", pady=(4, 0))

        # ── Barra fija inferior: totales, descuadre y acciones ──────────
        frame_bottom = tk.Frame(contenedor, bg=bg)
        frame_bottom.pack(fill="x", pady=(6, 0))

        resumen_bottom = tk.LabelFrame(
            frame_bottom, text="Resultado del arqueo", bg=bg, fg=fg,
            font=f"sans {self.config_manager.get_tamaño_fuente('subtitulo')} bold",
            padx=10, pady=6,
        )
        resumen_bottom.pack(fill="x")

        col_izq = tk.Frame(resumen_bottom, bg=bg)
        col_izq.pack(side="left", fill="y")
        tk.Label(col_izq, text="Total contado:", bg=bg, fg=fg, font=fuente,
                 anchor="w").pack(anchor="w")
        tk.Label(col_izq, text="Diferencia (descuadre):", bg=bg, fg=fg, font=fuente,
                 anchor="w").pack(anchor="w")

        col_der = tk.Frame(resumen_bottom, bg=bg)
        col_der.pack(side="right", fill="y")
        self.label_total_contado = tk.Label(
            col_der, text="-", bg=bg, fg=fg, font=fuente + " bold", anchor="e",
        )
        self.label_total_contado.pack(anchor="e")
        self.label_diferencia = tk.Label(
            col_der, text="-", bg=bg, fg=fg, font=fuente + " bold", anchor="e",
        )
        self.label_diferencia.pack(anchor="e")

        frame_acciones = tk.Frame(frame_bottom, bg=bg)
        frame_acciones.pack(fill="x", pady=(8, 10))
        btn_guardar = tk.Button(
            frame_acciones, text="✔ Finalizar y Guardar Cierre de Caja", bg="#27AE60",
            fg="white", font=fuente + " bold", padx=12, pady=10,
            command=self._guardar_y_imprimir,
        )
        btn_guardar.pack(side="left", padx=4)
        btn_imprimir = tk.Button(
            frame_acciones, text="🖨️ Imprimir informe", bg="#0078D4",
            fg="white", font=fuente + " bold", padx=12, pady=8,
            command=self._solo_imprimir,
        )
        btn_imprimir.pack(side="left", padx=4)
        btn_cerrar = tk.Button(
            frame_acciones, text="Cerrar", bg="#E74C3C", fg="white",
            font=fuente + " bold", padx=12, pady=8, command=self.destroy,
        )
        btn_cerrar.pack(side="right", padx=4)

    def _fila_entry(self, padre, etiqueta, var, fila, ancho):
        bg = self.colors["bg_principal"]
        fg = self.colors["fg_texto"]
        fuente = f"sans {self.config_manager.get_tamaño_fuente()}"
        tk.Label(padre, text=etiqueta, bg=bg, fg=fg, font=fuente, anchor="w").grid(
            row=fila, column=0, sticky="w", padx=6, pady=2
        )
        tk.Entry(
            padre, textvariable=var, width=ancho, font=fuente,
            bg=self.colors["entry_bg"], fg=self.colors["entry_fg"],
        ).grid(row=fila, column=1, sticky="ew", padx=6, pady=2, ipady=3)

    def _fila_denominacion(self, padre, denom):
        bg = self.colors["bg_principal"]
        fg = self.colors["fg_texto"]
        fuente = f"sans {self.config_manager.get_tamaño_fuente()}"
        etiqueta = f"{mod_moneda.format_currency(denom, 0 if denom == int(denom) else 2)}"
        fila = len(self.entries_conteo) + 1  # la fila 0 es la cabecera
        tk.Label(padre, text=etiqueta, bg=bg, fg=fg, font=fuente,
                 width=20, anchor="w").grid(
            row=fila, column=0, sticky="w", padx=6, pady=1)
        var = tk.StringVar()
        var.trace_add("write", self._recalcular_contado)
        tk.Entry(padre, textvariable=var, width=12, font=fuente,
                 bg=self.colors["entry_bg"], fg=self.colors["entry_fg"]).grid(
            row=fila, column=1, sticky="w", padx=6, pady=1, ipady=2,
        )
        sub = tk.Label(padre, text="", bg=bg, fg=fg, font=fuente,
                       width=18, anchor="e")
        sub.grid(row=fila, column=2, sticky="e", padx=6)
        self.entries_conteo[denom] = (var, sub)

    def _fijar_hoy(self):
        ahora = datetime.datetime.now()
        hoy = ahora.strftime("%d/%m/%Y")
        self.var_desde.set(f"{hoy} 00:00")
        self.var_hasta.set(ahora.strftime("%d/%m/%Y %H:%M"))

    @staticmethod
    def _parsear_fecha(texto, por_defecto):
        try:
            return datetime.datetime.strptime(texto.strip(), "%d/%m/%Y %H:%M")
        except ValueError:
            return por_defecto

    def _calcular(self):
        ahora = datetime.datetime.now()
        desde = self._parsear_fecha(self.var_desde.get(), ahora)
        hasta = self._parsear_fecha(self.var_hasta.get(), ahora)
        desde_iso = _a_iso_utc(desde)
        hasta_iso = _a_iso_utc(hasta)

        try:
            resumen = cierre_caja.resumen_ventas(desde_iso, hasta_iso)
            ingreso, retiro = cierre_caja.total_movimientos(desde_iso, hasta_iso)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo calcular el resumen: {e}")
            return

        self.resumen = {
            **resumen,
            "ingreso_manual": ingreso,
            "retiro_manual": retiro,
        }
        self.ingreso_manual = ingreso
        self.retiro_manual = retiro
        esperado = cierre_caja.total_esperado(self.resumen, ingreso, retiro)
        self.resumen["total_esperado"] = esperado

        self.labels_resumen["total_ventas"].config(
            text=mod_moneda.format_currency(self.resumen["total_ventas"])
        )
        self.labels_resumen["efectivo_neto"].config(
            text=mod_moneda.format_currency(self.resumen["efectivo_neto"])
        )
        self.labels_resumen["tarjeta"].config(
            text=mod_moneda.format_currency(self.resumen["tarjeta"])
        )
        self.labels_resumen["ingreso_manual"].config(
            text=mod_moneda.format_currency(ingreso)
        )
        self.labels_resumen["retiro_manual"].config(
            text=mod_moneda.format_currency(retiro)
        )
        self.labels_resumen["total_esperado"].config(
            text=mod_moneda.format_currency(esperado)
        )
        self._recalcular_contado()

    def _conteo_actual(self):
        conteo = {}
        for denom, (var, _sub) in self.entries_conteo.items():
            texto = var.get().strip()
            if texto:
                try:
                    cant = int(float(texto))
                except (TypeError, ValueError):
                    cant = 0
                if cant:
                    conteo[denom] = cant
        return conteo

    def _recalcular_contado(self, *_):
        total = 0.0
        for denom, (var, sub) in self.entries_conteo.items():
            texto = var.get().strip()
            valor = 0
            if texto:
                try:
                    cant = int(float(texto))
                except (TypeError, ValueError):
                    cant = 0
                valor = cant * denom
            sub.config(text=mod_moneda.format_currency(round(valor, 2)))
            total += valor
        self.label_total_contado.config(
            text=mod_moneda.format_currency(round(total, 2))
        )
        if self.resumen is not None:
            esperado = self.resumen["total_esperado"]
            diff = cierre_caja.calcular_diferencia(round(total, 2), esperado)
            texto = mod_moneda.format_currency(diff)
            if diff > 0:
                texto += "  (a favor)"
                color = "#27AE60"
            elif diff < 0:
                texto += "  (en contra)"
                color = "#E74C3C"
            else:
                color = self.colors["fg_texto"]
            self.label_diferencia.config(text=texto, fg=color)

    def _datos_insumo(self, total_contado):
        esperado = self.resumen["total_esperado"]
        diferencia = cierre_caja.calcular_diferencia(total_contado, esperado)
        return self.resumen, esperado, total_contado, diferencia

    def _imprimir(self, total_contado):
        if self.resumen is None:
            messagebox.showwarning("Cierre de caja", "Calcule el resumen antes de imprimir.")
            return False
        config = ConfigManager()
        impresora = config.get("impresora_termica")
        if not impresora:
            messagebox.showwarning(
                "Impresora térmica",
                "No hay impresora de tickets configurada. Configúrala en Ajustes.",
            )
            return False
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
        resumen, esperado, contado, diferencia = self._datos_insumo(total_contado)
        desde = self.var_desde.get()
        hasta = self.var_hasta.get()
        usuario = self.var_usuario.get()

        def trabajo():
            return imprimir_ticket_arqueo(
                resumen, esperado, contado, diferencia,
                fecha_apertura=desde, fecha_cierre=hasta, usuario=usuario,
                empresa=empresa, ancho=ancho, letra=letra, impresora=impresora,
                logo=logo, negocio=negocio,
            )

        def al_terminar(resultado, error):
            if error is not None:
                messagebox.showwarning("Impresora térmica", f"No se pudo imprimir: {error}")
                return
            ok, mensaje = resultado
            if not ok:
                messagebox.showwarning("Impresora térmica", mensaje)

        en_hilo(self, trabajo, al_terminar)
        return True

    def _guardar_y_imprimir(self):
        if self.resumen is None:
            messagebox.showwarning("Cierre de caja", "Calcule el resumen primero.")
            return
        total_contado = cierre_caja.calcular_total_contado(self._conteo_actual())
        resumen, esperado, contado, diferencia = self._datos_insumo(total_contado)

        ok = messagebox.askyesno(
            "Confirmar cierre de caja",
            "¿Desea guardar el cierre de caja e imprimir el informe?\n\n"
            f"Total esperado: {mod_moneda.format_currency(esperado)}\n"
            f"Total contado: {mod_moneda.format_currency(contado)}\n"
            f"Diferencia: {mod_moneda.format_currency(diferencia)}",
        )
        if not ok:
            return

        try:
            cierre_caja.guardar_cierre({
                "fecha_apertura": self.var_desde.get(),
                "fecha_cierre": self.var_hasta.get(),
                "usuario": self.var_usuario.get(),
                "notas": self.var_notas.get(),
                "total_ventas": resumen["total_ventas"],
                "total_efectivo_esperado": resumen["efectivo_neto"],
                "total_tarjeta": resumen["tarjeta"],
                "num_facturas_mixtas": resumen["num_facturas_mixtas"],
                "ingreso_manual": self.ingreso_manual,
                "retiro_manual": self.retiro_manual,
                "total_esperado": esperado,
                "total_contado": contado,
                "diferencia": diferencia,
                "desglose": self._conteo_actual(),
            })
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el cierre: {e}")
            return

        self._imprimir(contado)
        messagebox.showinfo("Cierre de caja", "Cierre de caja guardado correctamente.")

    def _solo_imprimir(self):
        total_contado = cierre_caja.calcular_total_contado(self._conteo_actual())
        self._imprimir(total_contado)
