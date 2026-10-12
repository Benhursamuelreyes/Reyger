"""
Módulo para gestión de impresoras multiplataforma.
Permite seleccionar y imprimir documentos a cualquier impresora disponible.

* Windows: usa pywin32 (``win32print``); si no está instalado, intenta
  una vía alternativa por ``wmic``.
* Linux y macOS: usa CUPS (``lpstat`` / ``lp``), presente en ambas
  plataformas; si las herramientas CUPS no existen, devuelve lista vacía.
"""

import os
import platform
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from ..config import ConfigManager

SISTEMA = platform.system()

# Intentar importar win32print
try:
    import win32print
    WINDOWS_PRINTING_AVAILABLE = True
except ImportError:
    WINDOWS_PRINTING_AVAILABLE = False
    if SISTEMA == "Windows":
        print("Advertencia: pywin32 no está instalado. La funcionalidad de impresoras estará limitada.")


class GestorImpresoras:
    """
    Gestor de impresoras para Windows.
    Permite obtener lista de impresoras y enviar documentos a imprimir.
    """
    
    def __init__(self, config_manager=None):
        """
        Inicializa el gestor de impresoras.
        
        Args:
            config_manager: Instancia de ConfigManager
        """
        self.config_manager = config_manager or ConfigManager()
        self.impresora_predeterminada = None
        self.limitar_impresoras = False
    
    def obtener_impresoras_disponibles(self):
        """
        Obtiene la lista de impresoras disponibles en el sistema.

        Returns:
            Lista de nombres de impresoras o lista vacía si no hay disponibles
        """
        self.impresora_predeterminada = None

        if SISTEMA != "Windows":
            # Linux y macOS se apoyan en CUPS (lpstat / lp).
            impresoras, predeterminada = self._obtener_impresoras_cups()
            self.impresora_predeterminada = predeterminada
            return impresoras

        if not WINDOWS_PRINTING_AVAILABLE:
            # Si no está disponible pywin32, intentar métodos alternativos
            return self._obtener_impresoras_wmic()

        impresoras = []
        try:
            # Obtener impresora predeterminada
            try:
                self.impresora_predeterminada = win32print.GetDefaultPrinter()
            except Exception:
                self.impresora_predeterminada = None

            # Enumerar todas las impresoras
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_NETWORK
            printers = win32print.EnumPrinters(flags)

            for printer_info in printers:
                if printer_info[2] and printer_info[2].strip():
                    impresoras.append(printer_info[2])

        except Exception as e:
            print(f"Error obteniendo impresoras: {e}")

        return impresoras

    def _obtener_impresoras_cups(self):
        """
        Impresoras vía CUPS (Linux y macOS).

        Usa ``lpstat -e`` (lista) y ``lpstat -d`` (predeterminada), cuyo
        formato de salida es estable e independiente del locale.

        Returns:
            Tupla (lista de impresoras, nombre de la predeterminada o None).
        """
        if shutil.which("lpstat") is None:
            return [], None

        impresoras = []
        predeterminada = None

        try:
            salida = subprocess.run(
                ["lpstat", "-e"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            if salida.returncode == 0:
                impresoras = [
                    linea.strip()
                    for linea in salida.stdout.splitlines()
                    if linea.strip()
                ]
        except Exception as e:
            print(f"Error listando impresoras CUPS: {e}")

        try:
            salida = subprocess.run(
                ["lpstat", "-d"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
            )
            linea = salida.stdout.strip() if salida.returncode == 0 else ""
            if ":" in linea:
                predeterminada = linea.split(":", 1)[1].strip() or None
        except Exception:
            predeterminada = None

        return impresoras, predeterminada

    def _obtener_impresoras_wmic(self):
        """
        Método alternativo para obtener impresoras si pywin32 no está disponible.

        ``wmic`` devuelve el texto en la página de códigos de consola
        (cp850/cp1252 en un Windows español), no en UTF-8: decodificarlo
        como UTF-8 lanzaba ``UnicodeDecodeError`` en cuanto un nombre de
        impresora contenía «ñ», «á» o «€», y el ``except`` devolvía una
        lista vacía aunque las impresoras estuvieran instaladas. Además
        ``wmic`` está obsoleto desde Windows 10 21H1 y ya no está presente
        en Windows 11 actual, por lo que esta vía no devuelve nada.
        """
        try:
            salida = subprocess.run(
                ["wmic", "printer", "list", "brief"],
                capture_output=True, timeout=10,
            )
            if salida.returncode != 0:
                print(
                    "wmic no disponible; no se pudieron listar las impresoras "
                    f"({salida.returncode})"
                )
                return []
            texto = salida.stdout.decode("mbcs", errors="replace")
            lineas = texto.splitlines()[1:]  # Saltar encabezado
            return [
                partes[0]
                for linea in lineas
                if linea.strip() and (partes := linea.split())
            ]
        except FileNotFoundError:
            print(
                "wmic no está instalado; instale pywin32 para listar y usar "
                "las impresoras de Windows."
            )
            return []
        except Exception as e:
            print(f"Error listando impresoras con wmic: {e}")
            return []
    
    def imprimir_archivo(self, ruta_archivo, nombre_impresora=None):
        """
        Imprime un archivo en la impresora especificada.
        
        Args:
            ruta_archivo: Ruta del archivo a imprimir
            nombre_impresora: Nombre de la impresora (si es None usa la predeterminada)
        
        Returns:
            Boolean indicando éxito
        """
        if not os.path.exists(ruta_archivo):
            print(f"Error: El archivo {ruta_archivo} no existe")
            return False
        
        if nombre_impresora is None:
            nombre_impresora = self.impresora_predeterminada
        
        if nombre_impresora is None:
            print("Error: No hay impresora especificada")
            return False
        
        try:
            if SISTEMA == "Windows":
                if WINDOWS_PRINTING_AVAILABLE:
                    # Usar win32print
                    return self._imprimir_con_win32(ruta_archivo, nombre_impresora)
                # Usar fallback
                return self._imprimir_fallback(ruta_archivo, nombre_impresora)
            # Linux y macOS: CUPS
            return self._imprimir_con_cups(ruta_archivo, nombre_impresora)
        except Exception as e:
            print(f"Error imprimiendo: {e}")
            return False

    def _imprimir_con_cups(self, ruta_archivo, nombre_impresora):
        """Imprime un archivo con ``lp`` (Linux/macOS) en la impresora dada."""
        if shutil.which("lp") is None:
            print("Error: CUPS (lp) no está disponible en este sistema")
            return False

        comando = ["lp"]
        if nombre_impresora:
            comando += ["-d", nombre_impresora]
        comando.append(ruta_archivo)
        try:
            resultado = subprocess.run(
                comando, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
            )
            return resultado.returncode == 0
        except Exception as e:
            print(f"Error imprimiendo con CUPS: {e}")
            return False
    
    def _imprimir_con_win32(self, ruta_archivo, nombre_impresora):
        """Imprime en *nombre_impresora* mediante el verbo ``printto``.

        Antes se lanzaba ``notepad /p <archivo>``, lo que tenía cuatro
        fallos encadenados: ``notepad /p`` imprime siempre en la
        impresora **predeterminada** (la elegida en el diálogo se
        ignoraba), no sabe renderizar un PDF, el conmutador está
        obsoleto en las versiones actuales de Windows, y el ``Popen`` no
        se esperaba, así que el proceso nunca se recogía. Encima se
        devolvía ``True`` incondicionalmente, de modo que el usuario veía
        el aviso de éxito aunque no se hubiera impreso nada.

        ``ShellExecute`` con el verbo ``printto`` sí acepta la impresora
        de destino, y ``-Wait``/``-PassThru`` permiten conocer el
        resultado real.
        """
        try:
            if WINDOWS_PRINTING_AVAILABLE:
                win32api = __import__("win32api")
                win32api.ShellExecute(
                    0, "printto", ruta_archivo, f'"{nombre_impresora}"', ".", 0
                )
                return True
            return self._imprimir_fallback(ruta_archivo, nombre_impresora)
        except Exception as e:
            print(f"Error imprimiendo con win32print: {e}")
            return False

    def _imprimir_fallback(self, ruta_archivo, nombre_impresora):
        """Impresión en Windows sin pywin32, vía PowerShell.

        Se usa ``Start-Process -Verb PrintTo`` pasando la impresora como
        argumento, que es la forma documentada de respetar la impresora
        elegida. La alternativa anterior (``rundll32 printui.dll
        /PrintUIEntry /p /n <impr> /pt <archivo>``) usaba conmutadores no
        documentados en los que ``/pt`` es además la opción de *página de
        prueba*, no de archivo: imprimía como mucho una página de prueba en
        la impresora predeterminada.
        """
        comando = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Start-Process -FilePath $args[0] -Verb PrintTo "
            "-ArgumentList ('\"' + $args[1] + '\"') -Wait -PassThru",
            ruta_archivo, nombre_impresora,
        ]
        try:
            proceso = subprocess.run(
                comando, capture_output=True, timeout=120
            )
            if proceso.returncode != 0:
                print(
                    "Error imprimiendo con PowerShell "
                    f"({proceso.returncode}): "
                    f"{proceso.stderr.decode(errors='replace').strip()}"
                )
                return False
            return True
        except FileNotFoundError:
            print(
                "No se encontró PowerShell ni pywin32: no se puede imprimir "
                "en Windows."
            )
            return False
        except Exception as e:
            print(f"Error imprimiendo: {e}")
            return False
    
    def obtener_impresora_predeterminada(self):
        """
        Obtiene el nombre de la impresora predeterminada.
        
        Returns:
            Nombre de la impresora predeterminada
        """
        if self.impresora_predeterminada is None:
            self.obtener_impresoras_disponibles()
        return self.impresora_predeterminada


class DialogoSeleccionImpresora(tk.Toplevel):
    """
    Diálogo para seleccionar una impresora y configurar opciones de impresión.
    """
    
    def __init__(self, parent, ruta_archivo, gestor_impresoras=None):
        """
        Inicializa el diálogo de selección de impresora.
        
        Args:
            parent: Ventana padre
            ruta_archivo: Ruta del archivo a imprimir
            gestor_impresoras: Instancia de GestorImpresoras
        """
        super().__init__(parent)
        self.title("Seleccionar Impresora")
        self.geometry("640x480")
        self.resizable(True, True)
        self.minsize(560, 420)
        self.ruta_archivo = ruta_archivo
        self.gestor = gestor_impresoras or GestorImpresoras()
        self.impresora_seleccionada = None
        self.resultado = False
        
        self.config_manager = ConfigManager()
        self.colors = self.config_manager.get_colors()
        self.configure(bg=self.colors["bg_principal"])
        
        self._crear_widgets()
        self._cargar_impresoras()
        
        # Hacer modal
        self.transient(parent)
        self.grab_set()
    
    def _crear_widgets(self):
        """Crea los widgets del diálogo"""
        
        # Título
        titulo = tk.Label(
            self,
            text="Seleccionar Impresora",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 14 bold"
        )
        titulo.pack(pady=10)
        
        # Lista de impresoras
        frame_lista = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_lista.pack(fill="both", expand=True, padx=20, pady=10)
        
        tk.Label(
            frame_lista,
            text="Impresoras disponibles:",
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10 bold"
        ).pack(anchor="w", pady=(0, 5))
        
        scrollbar = ttk.Scrollbar(frame_lista)
        scrollbar.pack(side="right", fill="y")
        
        self.listbox_impresoras = tk.Listbox(
            frame_lista,
            bg=self.colors["entry_bg"],
            fg=self.colors["entry_fg"],
            font="sans 10",
            yscrollcommand=scrollbar.set,
            height=8
        )
        self.listbox_impresoras.pack(fill="both", expand=True, side="left")
        scrollbar.config(command=self.listbox_impresoras.yview)
        
        # Opciones
        frame_opciones = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_opciones.pack(fill="x", padx=20, pady=10)
        
        self.var_color = tk.BooleanVar(value=False)
        check_color = tk.Checkbutton(
            frame_opciones,
            text="Impresión a color",
            variable=self.var_color,
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10",
            selectcolor=self.colors["bg_secundario"]
        )
        check_color.pack(anchor="w")
        
        self.var_dos_lados = tk.BooleanVar(value=False)
        check_dos_lados = tk.Checkbutton(
            frame_opciones,
            text="Impresion a doble cara",
            variable=self.var_dos_lados,
            bg=self.colors["bg_principal"],
            fg=self.colors["fg_texto"],
            font="sans 10",
            selectcolor=self.colors["bg_secundario"]
        )
        check_dos_lados.pack(anchor="w")
        
        # Botones
        frame_botones = tk.Frame(self, bg=self.colors["bg_principal"])
        frame_botones.pack(fill="x", padx=20, pady=10)
        
        btn_imprimir = tk.Button(
            frame_botones,
            text="Imprimir",
            bg="#27AE60",
            fg="white",
            font="sans 10 bold",
            command=self._imprimir
        )
        btn_imprimir.pack(side="left", padx=5)
        
        btn_cancelar = tk.Button(
            frame_botones,
            text="Cancelar",
            bg="#C0392B",
            fg="white",
            font="sans 10 bold",
            command=self.destroy
        )
        btn_cancelar.pack(side="left", padx=5)
    
    def _cargar_impresoras(self):
        """Carga el listado de impresoras disponibles"""
        impresoras = self.gestor.obtener_impresoras_disponibles()
        
        if not impresoras:
            messagebox.showwarning(
                "Advertencia",
                "No se encontraron impresoras disponibles"
            )
            return
        
        for impresora in impresoras:
            self.listbox_impresoras.insert("end", impresora)
        
        # Seleccionar la impresora predeterminada
        impresora_predeterminada = self.gestor.obtener_impresora_predeterminada()
        if impresora_predeterminada:
            try:
                idx = impresoras.index(impresora_predeterminada)
                self.listbox_impresoras.selection_set(idx)
                self.listbox_impresoras.see(idx)
            except ValueError:
                self.listbox_impresoras.selection_set(0)
        else:
            self.listbox_impresoras.selection_set(0)
    
    def _imprimir(self):
        """Realiza la impresión"""
        seleccion = self.listbox_impresoras.curselection()
        if not seleccion:
            messagebox.showerror("Error", "Seleccione una impresora")
            return
        
        self.impresora_seleccionada = self.listbox_impresoras.get(seleccion[0])
        
        # Enviar a imprimir
        if self.gestor.imprimir_archivo(self.ruta_archivo, self.impresora_seleccionada):
            messagebox.showinfo(
                "Exito",
                f"Documento enviado a impresora:\n{self.impresora_seleccionada}"
            )
            self.resultado = True
            self.destroy()
        else:
            messagebox.showerror("Error", "No se pudo enviar a imprimir")
