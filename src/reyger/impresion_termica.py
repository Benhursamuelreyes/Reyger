"""Impresión térmica de tickets en ESC/POS sin dependencias externas.

El ticket se construye como una secuencia de bytes con los comandos
ESC/POS estándar (init, justificado, negrita, tamaño doble, corte) y se
envía a la impresora:

* Windows: cola de impresión RAW vía ``winspool.drv`` con ctypes.
* Linux/macOS: escritura directa en ``/dev/usb/lp*`` o CUPS (``lp -o raw``).

El texto se codifica en CP858 (incluye € y caracteres españoles) con
retroceso a CP437 si la impresora no lo soporta.
"""

import glob
import platform
import subprocess

ANCHO_80MM = 42
ANCHO_58MM = 32

INICIO = b"\x1b@"
IZQUIERDA = b"\x1ba\x00"
CENTRO = b"\x1ba\x01"
NEGRITA_ON = b"\x1bE\x01"
NEGRITA_OFF = b"\x1bE\x00"
DOBLE = b"\x1d!\x11"
NORMAL = b"\x1d!\x00"
CORTE_PARCIAL = b"\x1dV\x42\x00"


def _codificar(texto):
    """Codifica texto a bytes de impresora (CP858 con retroceso)."""
    try:
        return str(texto).encode("cp858")
    except LookupError:
        return str(texto).encode("cp437", errors="replace")


def _linea(texto=""):
    return _codificar(texto) + b"\n"


def _fila_dos_columnas(izquierda, derecha, ancho):
    """Fila 'Nombre...... 12.34 €' recortada al ancho del papel."""
    izquierda = str(izquierda)
    derecha = str(derecha)
    espacio = ancho - len(izquierda) - len(derecha)
    if espacio < 1:
        # Nombre demasiado largo: partir en dos líneas
        recortado = izquierda[: ancho - len(derecha) - 1]
        espacio = ancho - len(recortado) - len(derecha)
        izquierda = recortado
    return _linea(izquierda + " " * max(espacio, 0) + derecha)


class TicketTermico:
    """Constructor de tickets ESC/POS."""

    def __init__(self, ancho=ANCHO_80MM, empresa="Mi Empresa"):
        self.ancho = ancho
        self.empresa = empresa
        self._partes = [INICIO]

    # ---------------------------------------------------------- bloques
    def encabezado(self):
        self._partes += [
            CENTRO,
            DOBLE,
            NEGRITA_ON,
            _linea(self.empresa.upper()[: self.ancho]),
            NORMAL,
            NEGRITA_OFF,
            _linea("RECIBO DE VENTA"),
            b"\n",
        ]
        return self

    def info(self, numero_factura, fecha, cliente=None):
        self._partes += [
            IZQUIERDA,
            _fila_dos_columnas(f"Recibo: {numero_factura}", fecha, self.ancho),
        ]
        if cliente:
            self._partes.append(_linea(f"Cliente: {cliente}"))
        return self

    def separador(self):
        self._partes.append(_linea("-" * self.ancho))
        return self

    def linea_producto(self, nombre, cantidad, precio, subtotal):
        nombre = str(nombre)[: self.ancho]
        self._partes.append(
            _fila_dos_columnas(nombre, f"{float(subtotal):.2f}", self.ancho)
        )
        self._partes.append(
            _linea(f"  {cantidad} x {float(precio):.2f} €")
        )
        return self

    def totales(self, total, base=None, cuota=None):
        self._partes.append(NEGRITA_ON)
        self._partes.append(
            _fila_dos_columnas("TOTAL", f"{float(total):.2f} €", self.ancho)
        )
        self._partes.append(NEGRITA_OFF)
        if base is not None:
            self._partes.append(
                _fila_dos_columnas("Base imponible", f"{float(base):.2f} €", self.ancho)
            )
        if cuota is not None:
            self._partes.append(
                _fila_dos_columnas("Cuota IVA", f"{float(cuota):.2f} €", self.ancho)
            )
        return self

    def metodo_pago(self, metodo):
        self._partes.append(_linea(f"Pago: {metodo}"))
        return self

    def pie(self):
        self._partes += [
            CENTRO,
            _linea("Gracias por su compra"),
            _linea("Conserve este recibo"),
            b"\n\n",
        ]
        return self

    def cortar(self, avances=3):
        self._partes.append(b"\n" * avances)
        self._partes.append(CORTE_PARCIAL)
        return self

    # ------------------------------------------------------------ salida
    def construir(self):
        return b"".join(self._partes)


def construir_ticket_venta(
    numero_factura,
    fecha,
    productos,
    total,
    base=None,
    cuota=None,
    metodo_pago="Efectivo",
    cliente=None,
    empresa="Mi Empresa",
    ancho=ANCHO_80MM,
):
    """Genera los bytes del ticket completo de una venta.

    *productos* es una secuencia de tuplas
    ``(nombre, precio, cantidad, subtotal[, ...])`` tal y como las
    produce el módulo de ventas.
    """
    ticket = TicketTermico(ancho=ancho, empresa=empresa)
    ticket.encabezado().info(numero_factura, fecha, cliente).separador()
    for producto in productos:
        nombre, precio, cantidad, subtotal = producto[0], producto[1], producto[2], producto[3]
        ticket.linea_producto(nombre, cantidad, precio, subtotal)
    ticket.separador().totales(total, base, cuota).metodo_pago(metodo_pago)
    ticket.pie().cortar()
    return ticket.construir()


# ------------------------------------------------------------------ envío
def listar_impresoras_termicas():
    """Devuelve los nombres de impresoras visibles por el sistema."""
    sistema = platform.system()
    nombres = []
    if sistema == "Windows":
        nombres += _listar_windows()
    else:
        try:
            salida = subprocess.run(
                ["lpstat", "-e"], capture_output=True, text=True, timeout=5
            )
            if salida.returncode == 0:
                nombres += [l.strip() for l in salida.stdout.splitlines() if l.strip()]
        except Exception:
            pass
    return nombres


def _listar_windows():
    """Enumera impresoras locales y de red vía winspool (nivel 4)."""
    import ctypes
    from ctypes import wintypes

    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [
            ("pPrinterName", wintypes.LPWSTR),
            ("pServerName", wintypes.LPWSTR),
            ("Attributes", wintypes.DWORD),
        ]

    nombres = []
    try:
        winspool = ctypes.WinDLL("winspool.drv")
        winspool.EnumPrintersW.argtypes = [
            wintypes.DWORD,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        winspool.EnumPrintersW.restype = wintypes.BOOL

        flags = 2 | 4  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
        necesarios = wintypes.DWORD(0)
        devueltas = wintypes.DWORD(0)
        winspool.EnumPrintersW(
            flags, None, 4, None, 0,
            ctypes.byref(necesarios), ctypes.byref(devueltas),
        )
        if not necesarios.value:
            return nombres
        bufer = (ctypes.c_byte * necesarios.value)()
        if winspool.EnumPrintersW(
            flags, None, 4, bufer, necesarios.value,
            ctypes.byref(necesarios), ctypes.byref(devueltas),
        ):
            registros = ctypes.cast(bufer, ctypes.POINTER(PRINTER_INFO_4W))
            for i in range(devueltas.value):
                nombre = registros[i].pPrinterName
                if nombre and nombre.strip():
                    nombres.append(nombre.strip())
    except Exception:
        pass
    return nombres


def enviar_bytes(datos, impresora=None):
    """Envía bytes crudos a la impresora térmica.

    Devuelve True si el envío se realizó; False en caso contrario
    (nunca lanza excepciones para no interrumpir la venta).
    """
    try:
        sistema = platform.system()
        if sistema == "Windows":
            return _enviar_windows(datos, impresora)
        return _enviar_posix(datos, impresora)
    except Exception:
        return False


def _enviar_windows(datos, impresora):
    """Imprime un trabajo RAW en la cola de Windows."""
    import ctypes
    from ctypes import wintypes

    class DOCINFO1W(ctypes.Structure):
        _fields_ = [
            ("pDocName", wintypes.LPWSTR),
            ("pOutputFile", wintypes.LPWSTR),
            ("pDatatype", wintypes.LPWSTR),
        ]

    winspool = ctypes.WinDLL("winspool.drv")
    winspool.OpenPrinterW.argtypes = [
        wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID,
    ]
    winspool.OpenPrinterW.restype = wintypes.BOOL
    winspool.StartDocPrinterW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
    ]
    winspool.StartDocPrinterW.restype = wintypes.BOOL
    winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.StartPagePrinter.restype = wintypes.BOOL
    winspool.WritePrinter.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    winspool.WritePrinter.restype = wintypes.BOOL
    winspool.EndPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.EndDocPrinter.argtypes = [wintypes.HANDLE]
    winspool.ClosePrinter.argtypes = [wintypes.HANDLE]

    handle = wintypes.HANDLE()
    if not winspool.OpenPrinterW(impresora, ctypes.byref(handle), None):
        return False
    try:
        documento = DOCINFO1W("Reyger Ticket", None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(documento)):
            return False
        try:
            if not winspool.StartPagePrinter(handle):
                return False
            try:
                escritos = wintypes.DWORD(0)
                bufer = (ctypes.c_char * len(datos)).from_buffer_copy(datos)
                ok = winspool.WritePrinter(
                    handle, bufer, len(datos), ctypes.byref(escritos)
                )
                return bool(ok) and escritos.value == len(datos)
            finally:
                winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def _enviar_posix(datos, impresora):
    # 1) Dispositivo directo (/dev/usb/lpN)
    rutas = []
    if impresora and impresora.startswith("/dev/"):
        rutas.append(impresora)
    else:
        rutas += sorted(glob.glob("/dev/usb/lp*"))
    for ruta in rutas:
        try:
            with open(ruta, "wb") as dispositivo:
                dispositivo.write(datos)
            return True
        except OSError:
            continue

    # 2) CUPS en modo raw
    comando = ["lp", "-o", "raw"]
    if impresora and not impresora.startswith("/dev/"):
        comando += ["-d", impresora]
    try:
        resultado = subprocess.run(
            comando, input=datos, capture_output=True, timeout=10
        )
        return resultado.returncode == 0
    except Exception:
        return False


def imprimir_ticket_venta(numero_factura, fecha, productos, total, base=None,
                          cuota=None, metodo_pago="Efectivo", cliente=None,
                          empresa="Mi Empresa", ancho=ANCHO_80MM,
                          impresora=None):
    """Construye y envía el ticket. Devuelve (ok, mensaje)."""
    datos = construir_ticket_venta(
        numero_factura, fecha, productos, total, base, cuota,
        metodo_pago, cliente, empresa, ancho,
    )
    if enviar_bytes(datos, impresora):
        return True, "Ticket impreso correctamente"
    return False, (
        "No se pudo imprimir el ticket.\n"
        "Revise la configuración de la impresora térmica en Ajustes."
    )
