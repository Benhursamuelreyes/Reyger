"""
Módulo para soporte de escáner de código de barras.
Los escáneres USB funcionan como teclados HID, por lo que se capturan
los códigos escaneados y se buscan automáticamente en el inventario.
"""

import sqlite3
import time
import tkinter as tk
from tkinter import messagebox, ttk
from .resources import get_db_path


class EscanerCodigoBarras:
    """
    Gestor de códigos de barras.
    Busca productos por código de barras en el inventario.
    """
    
    def __init__(self, db_path=None):
        """
        Inicializa el escáner.
        
        Args:
            db_path: Ruta de la base de datos
        """
        self.db_path = db_path or get_db_path()
        self.crear_columna_codigo_barras()
    
    def crear_columna_codigo_barras(self):
        """
        Crea la columna codigo_barras en la tabla inventario si no existe.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Intenta agregar la columna. SQLite no permite ADD COLUMN
            # ... UNIQUE sobre tablas existentes, así que la columna es
            # simple y la unicidad va en un índice aparte.
            try:
                cursor.execute(
                    "ALTER TABLE inventario ADD COLUMN codigo_barras TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError:
                # La columna ya existe
                pass

            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_inventario_codigo_barras"
                " ON inventario(codigo_barras)"
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error creando columna: {e}")
    
    def buscar_producto_por_codigo(self, codigo_barras):
        """
        Busca un producto por su código de barras.
        
        Args:
            codigo_barras: Código a buscar
        
        Returns:
            Diccionario con datos del producto o None si no existe
        """
        if not codigo_barras or not codigo_barras.strip():
            return None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT id, nombre, precio, stock, codigo_barras 
                    FROM inventario 
                    WHERE codigo_barras = ?
                """, (codigo_barras.strip(),)).fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'precio': row[2],
                    'stock': row[3],
                    'codigo_barras': row[4]
                }
            return None
        except Exception as e:
            print(f"Error buscando producto: {e}")
            return None
    
    def guardar_codigo_barras(self, id_producto, codigo_barras):
        """
        Guarda el código de barras para un producto.
        
        Args:
            id_producto: ID del producto en la tabla inventario
            codigo_barras: Código de barras a guardar
        
        Returns:
            Boolean indicando éxito
        """
        if not codigo_barras or not codigo_barras.strip():
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE inventario 
                    SET codigo_barras = ? 
                    WHERE id = ?
                """, (codigo_barras.strip(), id_producto))
            return True
        except sqlite3.IntegrityError:
            # Código de barras duplicado
            return False
        except Exception as e:
            print(f"Error guardando código: {e}")
            return False
    
    def obtener_producto_por_id(self, id_producto):
        """
        Obtiene datos del producto por ID.
        
        Args:
            id_producto: ID del producto
        
        Returns:
            Diccionario con datos del producto
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("""
                    SELECT id, nombre, precio, stock, codigo_barras 
                    FROM inventario 
                    WHERE id = ?
                """, (id_producto,)).fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'precio': row[2],
                    'stock': row[3],
                    'codigo_barras': row[4]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo producto: {e}")
            return None
    
    def listar_productos_sin_codigo(self):
        """
        Lista todos los productos que no tienen código de barras asignado.
        
        Returns:
            Lista de tuplas (id, nombre, código_actual)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                productos = conn.execute("""
                    SELECT id, nombre, codigo_barras 
                    FROM inventario 
                    WHERE codigo_barras IS NULL OR codigo_barras = ''
                    ORDER BY nombre
                """).fetchall()
            return productos
        except Exception as e:
            print(f"Error listando productos: {e}")
            return []


class DialogoAsignarCodigoBarras(tk.Toplevel):
    """
    Diálogo para asignar códigos de barras a productos.
    """
    
    def __init__(self, parent, id_producto, nombre_producto, escaner):
        """
        Inicializa el diálogo.
        
        Args:
            parent: Ventana padre
            id_producto: ID del producto
            nombre_producto: Nombre del producto
            escaner: Instancia de EscanerCodigoBarras
        """
        super().__init__(parent)
        self.title("Asignar Código de Barras")
        self.geometry("480x320")
        self.resizable(True, True)
        self.minsize(440, 300)
        
        self.id_producto = id_producto
        self.nombre_producto = nombre_producto
        self.escaner = escaner
        self.codigo_asignado = False
        
        # Frame principal
        frame = tk.Frame(self, bg="#C6D9E3")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Título
        titulo = tk.Label(
            frame,
            text=f"Asignar Código de Barras",
            bg="#C6D9E3",
            font="sans 14 bold"
        )
        titulo.pack(pady=10)
        
        # Información del producto
        info = tk.Label(
            frame,
            text=f"Producto: {nombre_producto}",
            bg="#C6D9E3",
            font="sans 11",
            wraplength=350
        )
        info.pack(pady=5)
        
        # Instrucción
        instruccion = tk.Label(
            frame,
            text="Escanee el código de barras o ingreselo manualmente:",
            bg="#C6D9E3",
            font="sans 10"
        )
        instruccion.pack(pady=10)
        
        # Campo de entrada
        self.entry_codigo = tk.Entry(frame, font="sans 12 bold", width=30)
        self.entry_codigo.pack(pady=10, ipady=5)
        self.entry_codigo.focus()
        self.entry_codigo.bind("<Return>", lambda e: self._guardar_codigo())
        
        # Botones
        frame_botones = tk.Frame(frame, bg="#C6D9E3")
        frame_botones.pack(pady=15)
        
        btn_guardar = tk.Button(
            frame_botones,
            text="Guardar",
            bg="#27AE60",
            fg="white",
            font="sans 10 bold",
            command=self._guardar_codigo
        )
        btn_guardar.pack(side="left", padx=5)
        
        btn_cancelar = tk.Button(
            frame_botones,
            text="Cancelar",
            bg="#C0392B",
            fg="white",
            font="sans 10 bold",
            command=self.destroy
        )
        btn_cancelar.pack(side="left", padx=5)
        
        # Hacer modal
        self.transient(parent)
        self.grab_set()
    
    def _guardar_codigo(self):
        """Guarda el código de barras"""
        codigo = self.entry_codigo.get().strip()
        
        if not codigo:
            messagebox.showerror("Error", "Ingrese un código de barras")
            return
        
        if self.escaner.guardar_codigo_barras(self.id_producto, codigo):
            messagebox.showinfo(
                "Exito",
                f"Código de barras asignado correctamente:\n{codigo}"
            )
            self.codigo_asignado = True
            self.destroy()
        else:
            messagebox.showerror(
                "Error",
                "Este código de barras ya está asignado a otro producto"
            )
            self.entry_codigo.delete(0, "end")
            self.entry_codigo.focus()


# ---------------------------------------------------------------------------
# Registro rápido de productos desde un código desconocido
# ---------------------------------------------------------------------------


def registrar_producto_rapido(db_path, codigo_barras, nombre, precio_venta,
                              precio_costo=None, stock=1, tipo_iva=None):
    """Crea un producto mínimo y le asigna ``codigo_barras``.

    Devuelve el diccionario del producto creado. Lanza ``ValueError`` si
    faltan datos obligatorios o si el código ya está asignado.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del producto es obligatorio")
    try:
        precio_venta = float(str(precio_venta).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("El precio de venta debe ser numérico")
    if precio_costo in (None, ""):
        precio_costo = precio_venta
    try:
        precio_costo = float(str(precio_costo).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("El precio de costo debe ser numérico")
    try:
        stock = int(stock)
    except (TypeError, ValueError):
        raise ValueError("El stock debe ser un número entero")

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "INSERT INTO inventario (nombre, proveedor, precio, costo,"
            " stock, tipo_iva, codigo_barras) VALUES (?,?,?,?,?,?,?)",
            (nombre, "", precio_venta, precio_costo, stock,
             tipo_iva if tipo_iva is not None else 21, codigo_barras),
        )
        id_producto = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError(
            f"El código {codigo_barras} ya está asignado a otro producto"
        ) from e
    finally:
        conn.close()

    return {
        "id": id_producto,
        "nombre": nombre,
        "precio": precio_venta,
        "stock": stock,
        "codigo_barras": codigo_barras,
    }


class DialogoRegistroRapido(tk.Toplevel):
    """Alta mínima de producto para un código de barras no registrado.

    Al cerrarse, ``self.resultado`` contiene el producto creado o ``None``.
    """

    def __init__(self, parent, codigo_barras, db_path):
        super().__init__(parent)
        self.title("Registrar producto nuevo")
        self.geometry("480x320")
        self.resizable(True, True)
        self.minsize(440, 300)
        self.configure(bg="#C6D9E3")
        self.resultado = None
        self.db_path = db_path
        self._codigo = codigo_barras

        frame = tk.Frame(self, bg="#C6D9E3", padx=15, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text=f"Código: {codigo_barras}",
            bg="#C6D9E3", font="sans 12 bold",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(
            frame,
            text="Complete los datos mínimos; podrá editarlos después\n"
                 "en Inventario.",
            bg="#C6D9E3", font="sans 9", justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

        campos = (
            ("Nombre *:", "nombre"),
            ("Precio de venta *:", "precio"),
            ("Precio de costo:", "costo"),
            ("Stock inicial:", "stock"),
        )
        self.entradas = {}
        for fila, (etiqueta, clave) in enumerate(campos, start=2):
            tk.Label(
                frame, text=etiqueta, bg="#C6D9E3", font="sans 11 bold",
            ).grid(row=fila, column=0, sticky="e", padx=6, pady=4)
            entrada = ttk.Entry(frame, font="sans 12", width=24)
            entrada.grid(row=fila, column=1, sticky="ew", padx=6, pady=4)
            self.entradas[clave] = entrada
        self.entradas["stock"].insert(0, "1")
        self.entradas["nombre"].focus()

        botones = tk.Frame(frame, bg="#C6D9E3")
        botones.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        tk.Button(
            botones, text="💾 Registrar", bg="#27AE60", fg="white",
            font="sans 11 bold", command=self._guardar,
        ).pack(side="left", padx=5)
        tk.Button(
            botones, text="Cancelar", bg="#C0392B", fg="white",
            font="sans 11 bold", command=self.destroy,
        ).pack(side="left", padx=5)

        self.transient(parent)
        self.grab_set()
        self.wait_window()

    def _guardar(self):
        try:
            self.resultado = registrar_producto_rapido(
                self.db_path,
                self._codigo,
                nombre=self.entradas["nombre"].get(),
                precio_venta=self.entradas["precio"].get(),
                precio_costo=self.entradas["costo"].get() or None,
                stock=self.entradas["stock"].get(),
            )
        except ValueError as e:
            messagebox.showwarning("Registrar producto", str(e), parent=self)
            return
        except Exception as e:
            messagebox.showerror(
                "Registrar producto", f"No se pudo registrar: {e}", parent=self
            )
            return
        self.destroy()


# ---------------------------------------------------------------------------
# Captura en vivo de lectoras HID (modo ráfaga de teclado)
# ---------------------------------------------------------------------------


class CapturaEscanero:
    """Detecta ráfagas de teclado típicas de una lectora de códigos.

    Se enlaza a los eventos ``<Key>`` de la ventana indicada y acumula
    caracteres cuando llegan como ráfaga rápida (firma de un escáner HID).
    La lectura termina con ``Enter``; si la ráfaga es válida se invoca al
    ``callback`` con el código completo.

    Si el foco está sobre un widget editable (Entry, Combobox...), las
    teclas no se consideran del escáner: así la escritura manual en el
    campo de código o en cualquier otro campo nunca se confunde con una
    lectura.
    """

    EDITABLES = ("Entry", "TEntry", "Combobox", "TCombobox", "Spinbox",
                 "Text", "Listbox")

    def __init__(self, widget, callback, pausa_maxima_ms=60,
                 duracion_maxima_ms=500, longitud_minima=4):
        self.widget = widget
        self.callback = callback
        self.pausa_maxima_ms = pausa_maxima_ms
        self.duracion_maxima_ms = duracion_maxima_ms
        self.longitud_minima = longitud_minima
        self.buffer = []
        self.inicio_ms = 0.0
        self.ultimo_ms = 0.0
        self.activo = False

    def iniciar(self):
        if self.activo:
            return
        self.widget.bind("<Key>", self._on_tecla)
        self.activo = True

    def detener(self):
        if not self.activo:
            return
        try:
            self.widget.unbind("<Key>")
        except Exception:
            pass
        self.buffer.clear()
        self.activo = False

    def _foco_editable(self):
        try:
            foco = self.widget.focus_get()
        except Exception:
            return True
        return foco is not None and foco.winfo_class() in self.EDITABLES

    def _on_tecla(self, evento):
        if not self.activo or self._foco_editable():
            return
        ahora_ms = time.monotonic() * 1000.0
        if evento.keysym in ("Return", "KP_Enter", "Enter"):
            self._terminar(ahora_ms)
            return
        caracter = evento.char
        if not caracter or not caracter.isprintable():
            return
        if int(evento.state) & 0x0004:  # Ctrl+<tecla>: atajo, no escáner
            return
        # Reinicia el buffer si la pausa entre teclas es demasiado larga
        if self.buffer and (ahora_ms - self.ultimo_ms) > self.pausa_maxima_ms:
            self.buffer.clear()
        if self.buffer and (ahora_ms - self.inicio_ms) > self.duracion_maxima_ms:
            self.buffer.clear()
        if not self.buffer:
            self.inicio_ms = ahora_ms
        self.buffer.append(caracter)
        self.ultimo_ms = ahora_ms

    def _terminar(self, ahora_ms):
        codigo = "".join(self.buffer).strip()
        self.buffer.clear()
        if len(codigo) < self.longitud_minima:
            return
        if (ahora_ms - self.inicio_ms) > self.duracion_maxima_ms:
            return
        self.callback(codigo)
