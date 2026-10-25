"""Ventana del informe de ventas por periodo (con exportación a Excel)."""

import logging
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox

from ..config import ConfigManager
from ..core import moneda as mod_moneda
from ..domain import informes

log = logging.getLogger(__name__)

FORMATO_FECHA = "%d/%m/%Y"


def _leer_fecha(texto):
    return datetime.strptime(texto.strip(), FORMATO_FECHA).date()


class VentanaInforme(tk.Toplevel):
    """Resumen de ventas emitidas entre dos fechas."""

    def __init__(self, padre):
        super().__init__(padre)
        self.colors = ConfigManager().get_colors()
        self.informe = None
        self.title("Informe de ventas")
        self.geometry("620x560")
        self.minsize(560, 480)
        self.configure(bg=self.colors["bg_principal"])
        self.transient(padre)
        self._widgets()
        self._este_mes()

    def _widgets(self):
        fondo = self.colors["bg_principal"]
        tk.Label(
            self, text="📊 Informe de ventas", font="sans 18 bold", bg=fondo,
        ).pack(pady=(14, 8))

        filtro = tk.Frame(self, bg=fondo)
        filtro.pack(fill="x", padx=16)
        tk.Label(filtro, text="Desde:", font="sans 12 bold", bg=fondo).grid(row=0, column=0, sticky="w")
        self.entry_desde = tk.Entry(filtro, font="sans 12", width=12)
        self.entry_desde.grid(row=0, column=1, padx=(4, 14))
        tk.Label(filtro, text="Hasta:", font="sans 12 bold", bg=fondo).grid(row=0, column=2, sticky="w")
        self.entry_hasta = tk.Entry(filtro, font="sans 12", width=12)
        self.entry_hasta.grid(row=0, column=3, padx=(4, 14))
        tk.Label(filtro, text="(dd/mm/aaaa)", font="sans 10", bg=fondo).grid(row=0, column=4, sticky="w")

        atajos = tk.Frame(self, bg=fondo)
        atajos.pack(fill="x", padx=16, pady=8)
        for texto, accion in (("Hoy", self._hoy), ("Este mes", self._este_mes)):
            tk.Button(
                atajos, text=texto, font="sans 11 bold", bg="#95A5A6", fg="white",
                command=accion,
            ).pack(side="left", padx=(0, 6))
        tk.Button(
            atajos, text="🔄 Calcular", font="sans 11 bold", bg="#0078D4", fg="white",
            command=self.calcular,
        ).pack(side="left", padx=(12, 0))

        self.texto = tk.Text(self, font="sans 11", height=16, wrap="word")
        self.texto.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.texto.config(state="disabled")

        self.boton_exportar = tk.Button(
            self, text="📥 Exportar a Excel…", font="sans 12 bold",
            bg="#27AE60", fg="white", command=self.exportar, state="disabled",
        )
        self.boton_exportar.pack(fill="x", padx=16, pady=(0, 14), ipady=4)

    # ----------------------------------------------------------- periodos
    def _fijar(self, desde, hasta):
        for entry, valor in ((self.entry_desde, desde), (self.entry_hasta, hasta)):
            entry.delete(0, "end")
            entry.insert(0, valor.strftime(FORMATO_FECHA))
        self.calcular()

    def _hoy(self):
        self._fijar(date.today(), date.today())

    def _este_mes(self):
        hoy = date.today()
        self._fijar(hoy.replace(day=1), hoy)

    # ------------------------------------------------------------ informe
    def calcular(self):
        try:
            desde = _leer_fecha(self.entry_desde.get())
            hasta = _leer_fecha(self.entry_hasta.get())
            self.informe = informes.informe_ventas(desde, hasta)
        except ValueError as e:
            self.informe = None
            self.boton_exportar.config(state="disabled")
            mensaje = str(e) if "posterior" in str(e) else "Introduce las fechas como dd/mm/aaaa."
            messagebox.showwarning("Informe de ventas", mensaje, parent=self)
            return
        self._mostrar(self.informe)
        self.boton_exportar.config(state="normal" if self.informe.documentos else "disabled")

    def _mostrar(self, inf):
        euros = mod_moneda.format_currency
        lineas = [
            f"Periodo: {inf.desde:%d/%m/%Y} – {inf.hasta:%d/%m/%Y}",
            "",
            f"Documentos emitidos: {inf.documentos}",
            f"Base imponible: {euros(inf.base)}",
            f"Cuota IVA: {euros(inf.cuota)}",
            f"TOTAL: {euros(inf.total)}",
        ]
        if inf.por_tipo:
            lineas += ["", "Por tipo:"] + [
                f"  {tipo.capitalize()}s: {docs} — {euros(total)}" for tipo, docs, total in inf.por_tipo
            ]
        if inf.por_metodo:
            lineas += ["", "Por método de pago:"] + [
                f"  {metodo}: {docs} — {euros(total)}" for metodo, docs, total in inf.por_metodo
            ]
        if inf.por_producto:
            lineas += ["", "Productos más vendidos:"] + [
                f"  {nombre}: {unidades} ud. — {euros(total)}"
                for nombre, unidades, total in inf.por_producto[:10]
            ]
        if not inf.documentos:
            lineas += ["", "No hay ventas emitidas en este periodo."]
        self.texto.config(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", "\n".join(lineas))
        self.texto.config(state="disabled")

    def exportar(self):
        if self.informe is None:
            return
        inf = self.informe
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar informe de ventas",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"ventas_{inf.desde:%Y%m%d}_{inf.hasta:%Y%m%d}.xlsx",
        )
        if not ruta:
            return
        try:
            informes.exportar_excel(inf, ruta)
        except Exception as e:
            log.exception("No se pudo exportar el informe de ventas")
            messagebox.showerror("Informe de ventas", f"No se pudo exportar: {e}", parent=self)
            return
        messagebox.showinfo("Informe de ventas", f"Informe guardado en:\n{ruta}", parent=self)
