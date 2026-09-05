"""Tests de los retoques finales: letra del ticket y scroll en Ajustes.

Cubre: escalas ESC/POS y ancho de columnas del ticket, propagación de la
preferencia desde Ventas, valores por defecto de config.json y el
scrollbar vertical de la ventana de ajustes.
"""

import os
import shutil
import sys
import tempfile
import time
import pytest
import tkinter as tk

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)
# Recursos y módulos del paquete (assets incluidos) para las pruebas
SCRIPT_DIR = os.path.join(SRC_DIR, "reyger")

AZUL = "\033[94m"
VERDE = "\033[92m"
ROJO = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

FALLOS = []
PLANTILLA = os.path.join(SCRIPT_DIR, "assets", "database.db")


def chequear(nombre, condicion, detalle=""):
    if condicion:
        print(f"  {VERDE}✓{RESET} {nombre}")
    else:
        print(f"  {ROJO}✗{RESET} {nombre}" + (f" -> {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def bombear(root, segundos):
    fin = time.time() + segundos
    while time.time() < fin:
        root.update()
        time.sleep(0.01)


def lineas_de_texto(datos):
    """Decodifica las líneas imprimibles del ticket (ignora comandos)."""
    texto = datos.decode("cp858", errors="ignore")
    return [
        linea for linea in
        (parte.strip() for parte in texto.split("\n"))
        if linea and not linea.startswith("\x1b") and not linea.startswith("\x1d")
    ]


def test_escalas_ticket():
    print(f"\n{BOLD}{AZUL}[TEST 1] Escalas de letra del ticket{RESET}")
    from reyger.hardware.impresion_termica import (
        ESCALAS_LETRA,
        TicketTermico,
        construir_ticket_venta,
    )

    productos = [("Coca Cola 1.5L", 1.50, 2, 3.00), ("Pan", 0.90, 1, 0.90)]
    comunes = dict(
        numero_factura="F-1", fecha="02/08/2026 10:00",
        total=3.90, base=3.22, cuota=0.68,
    )
    for clave in ESCALAS_LETRA:
        datos = construir_ticket_venta(
            productos=productos, metodo_pago="Efectivo",
            empresa="Pruebas", letra=clave, **comunes
        )
        chequear(f"Escala «{clave}» emite GS! correspondiente",
                 ESCALAS_LETRA[clave] in datos)
        ticket = TicketTermico(letra=clave)
        excede = [l for l in lineas_de_texto(datos) if len(l) > ticket.columnas]
        chequear(f"«{clave}»: ninguna línea supera {ticket.columnas} columnas",
                 not excede, str(excede[:2]))

    chequear("Letra desconocida cae a «muy_grande»",
             TicketTermico(letra="inventada").letra == "muy_grande")
    chequear("«muy_grande» parte el ancho en dos (80 mm → 21)",
             TicketTermico(ancho=42, letra="muy_grande").columnas == 21)


@pytest.mark.orden_dependiente
def test_preferencia_en_ventas():
    print(f"\n{BOLD}{AZUL}[TEST 2] Ventas pasa la letra configurada{RESET}")
    from unittest.mock import patch

    import reyger.ui.ventas as mod_ventas
    import reyger.ui.business_profile as mod_bp

    capturadas = []
    raiz = tk.Tk()
    raiz.withdraw()
    try:
        ventas = object.__new__(mod_ventas.Ventas)
        ventas.after = raiz.after

        def espiar(*args, **kwargs):
            capturadas.append(kwargs)
            return True, "ok"

        with patch.object(mod_ventas.ConfigManager, "get",
                          side_effect=lambda k, d=None: {
                              "impresora_termica": "POS-80",
                              "ancho_ticket": 58,
                              "letra_ticket": "pequena",
                          }.get(k, d)), \
             patch.object(mod_ventas, "imprimir_ticket_venta", espiar), \
             patch.object(mod_bp, "nombre_empresa", return_value="Test SA"):
            ventas._imprimir_ticket_termico(
                "F-9", "hoy", [], 5.0, 4.13, 0.87, "Efectivo", None
            )
        bombear(raiz, 1.0)
        chequear("Se llamó a imprimir exactamente una vez",
                 len(capturadas) == 1, str(len(capturadas)))
        if capturadas:
            kw = capturadas[0]
            chequear("ancho 58 mm propagado", kw.get("ancho") == 32, str(kw))
            chequear("letra «pequena» propagada",
                     kw.get("letra") == "pequena", str(kw))
    finally:
        raiz.destroy()


def test_defaults_config():
    print(f"\n{BOLD}{AZUL}[TEST 3] Defaults de config.json{RESET}")
    import reyger.config as mod_config

    tmpdir = tempfile.mkdtemp(prefix="reyger_ret_config_")
    original_path = mod_config.get_user_data_path
    mod_config.get_user_data_path = lambda: tmpdir
    try:
        gestor = mod_config.ConfigManager()
        chequear("ancho_ticket por defecto 80",
                 gestor.get("ancho_ticket") == 80)
        chequear("letra_ticket por defecto «muy_grande»",
                 gestor.get("letra_ticket") == "muy_grande")
    finally:
        mod_config.get_user_data_path = original_path
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_scroll_ajustes():
    print(f"\n{BOLD}{AZUL}[TEST 4] Scrollbar vertical en Ajustes{RESET}")
    import reyger.ui.ajustes as mod_ajustes
    from reyger.core import db as modulo_db

    tmp_dir = tempfile.mkdtemp(prefix="reyger_ret_scroll_")
    ruta = os.path.join(tmp_dir, "scroll_test.db")
    shutil.copyfile(PLANTILLA, ruta)
    original_get_db_path = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()

    raiz = tk.Tk()
    raiz.geometry("1100x600+10+10")
    toplevel = tk.Toplevel(raiz)
    try:
        panel = mod_ajustes.Ajustes(toplevel)

        def descendientes(widget):
            for hijo in widget.winfo_children():
                yield hijo
                yield from descendientes(hijo)

        familia = list(descendientes(panel))
        lienzos = [w for w in familia if isinstance(w, tk.Canvas)]
        barras = [w for w in familia if w.winfo_class() == "TScrollbar"]
        chequear("Hay un lienzo desplazable", len(lienzos) == 1)
        chequear("Hay barra vertical conectada al lienzo",
                 len(barras) >= 1
                 and bool(lienzos[0].cget("yscrollcommand")))
        lienzo = lienzos[0]

        bombear(raiz, 0.6)
        region = lienzo.cget("scrollregion").split()
        alto_contenido = float(region[3]) if len(region) == 4 else 0
        chequear("El contenido mide más que la ventana (hace falta scroll)",
                 alto_contenido > lienzo.winfo_height(),
                 f"{alto_contenido:.0f}px vs {lienzo.winfo_height()}px")

        # La rueda del ratón mueve la vista
        antes = lienzo.yview()
        evento = tk.Event()
        evento.delta = -120
        evento.num = 0
        toplevel.event_generate("<MouseWheel>", delta=-120)
        bombear(raiz, 0.3)
        despues = lienzo.yview()
        chequear("La rueda desplaza la vista", antes != despues,
                 f"{antes} -> {despues}")

        # Selector de letra presente y con tres opciones
        combo = getattr(panel, "combo_letra_ticket", None)
        chequear("Selector de letra existe", combo is not None)
        if combo is not None:
            chequear("Tres tamaños ofrecidos",
                     list(combo["values"]) == ["Pequeña", "Grande", "Muy grande"],
                     str(list(combo["values"])))
            chequear("Valor por defecto «Grande»", combo.get() == "Grande")
        panel.destroy()
    finally:
        toplevel.destroy()
        raiz.destroy()
        modulo_db.close()
        modulo_db.get_db_path = original_get_db_path
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_perfil_empresa():
    print(f"\n{BOLD}{AZUL}[TEST 5] Sección Perfil de Empresa en Ajustes{RESET}")
    import reyger.ui.ajustes as mod_ajustes
    import reyger.ui.business_profile as bp
    from reyger.core import db as modulo_db

    tmp_dir = tempfile.mkdtemp(prefix="reyger_ret_bp_")
    ruta = os.path.join(tmp_dir, "bp_test.db")
    shutil.copyfile(PLANTILLA, ruta)
    original_get_db_path = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta
    modulo_db.close()

    raiz = tk.Tk()
    raiz.geometry("1100x600+10+10")
    toplevel = tk.Toplevel(raiz)
    try:
        panel = mod_ajustes.Ajustes(toplevel)

        # Verificar que existen los campos del perfil
        bp_entries = getattr(panel, "bp_entries", None)
        chequear("bp_entries existe en el panel", bp_entries is not None)

        campos_esperados = [
            "nombre", "nif", "direccion", "codigo_postal",
            "provincia", "telefono", "email", "actividad_economica",
            "numero_series",
        ]
        if bp_entries:
            for campo in campos_esperados:
                chequear(f"Campo '{campo}' presente", campo in bp_entries)
            chequear(
                "Nombre por defecto 'Mi Empresa'",
                bp_entries["nombre"].get() == "Mi Empresa",
            )

            # Modificar valores y guardar
            bp_entries["nombre"].delete(0, "end")
            bp_entries["nombre"].insert(0, "Test SL")
            bp_entries["nif"].insert(0, "B99999999")
            bp_entries["numero_series"].delete(0, "end")
            bp_entries["numero_series"].insert(0, "C")

            # Llamar guardar_cambios
            import reyger.ui.ajustes as mod_ajustes_mod
            import types
            silenciar = types.SimpleNamespace(
                showinfo=lambda *a, **k: None,
                showerror=lambda *a, **k: None,
            )
            old_msgbox = mod_ajustes_mod.messagebox
            mod_ajustes_mod.messagebox = silenciar
            try:
                panel.guardar_cambios()
            finally:
                mod_ajustes_mod.messagebox = old_msgbox

            # Verificar que se guardó en la BD
            perfil = bp.obtener()
            chequear(
                "Nombre guardado en BD",
                perfil is not None and perfil["nombre"] == "Test SL",
            )
            chequear(
                "NIF guardado en BD",
                perfil is not None and perfil["nif"] == "B99999999",
            )
            chequear(
                "Numero series guardado en BD",
                perfil is not None and perfil["numero_series"] == "C",
            )

        panel.destroy()
    finally:
        toplevel.destroy()
        raiz.destroy()
        modulo_db.close()
        modulo_db.get_db_path = original_get_db_path
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    test_escalas_ticket()
    test_preferencia_en_ventas()
    test_defaults_config()
    test_scroll_ajustes()
    test_perfil_empresa()

    print()
    if FALLOS:
        print(f"{ROJO}{BOLD}FALLARON {len(FALLOS)} comprobaciones:{RESET}")
        for nombre in FALLOS:
            print(f"  - {nombre}")
        return 1
    print(f"{VERDE}{BOLD}Todos los tests de los retoques pasaron.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
