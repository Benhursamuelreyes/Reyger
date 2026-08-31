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
import os
import platform
import subprocess

ANCHO_80MM = 42
ANCHO_58MM = 32

#: Puntos imprimibles de ancho para el rasterizado del logo/logotipo,
#: limitados a 384 px en 58 mm y 512 px en 80 mm (recomendación EPSON).
PUNTOS_POR_ANCHO = {ANCHO_80MM: 512, ANCHO_58MM: 384}

INICIO = b"\x1b@"
#: Fija la tabla de caracteres a PC850 / Latin-1 (Multilingual) para que
#: los acentos y símbolos españoles se impriman bien en lugar de salir
#: como caracteres extraños (p. ej. 'Ç ª ¿ ≡'). GS t 2 = PC850.
CODEPAGE_PC850 = b"\x1dt\x02"
IZQUIERDA = b"\x1ba\x00"
CENTRO = b"\x1ba\x01"
NEGRITA_ON = b"\x1bE\x01"
NEGRITA_OFF = b"\x1bE\x00"
DOBLE = b"\x1d!\x11"
NORMAL = b"\x1d!\x00"
CORTE_PARCIAL = b"\x1dV\x42\x00"

#: Tamaños de letra del cuerpo del ticket (comando ``GS ! n``):
#: nibble alto = multiplicador de ancho, nibble bajo = de altura.
ESCALAS_LETRA = {
    "pequena": b"\x1d!\x00",     # 1×1 (la original)
    "grande": b"\x1d!\x01",      # doble altura, mismos caracteres por línea
    "muy_grande": b"\x1d!\x11",  # doble ancho y alto
}

#: Escala del nombre de la empresa: siempre un paso mayor que el cuerpo
#: para que el encabezado destaque sobre los productos.
ESCALA_ENCABEZADO = {
    "pequena": b"\x1d!\x11",     # 2×2
    "grande": b"\x1d!\x21",      # 2×3
    "muy_grande": b"\x1d!\x22",  # 3×3
}

#: Multiplicador horizontal de la escala del encabezado.
MULTIPLICADOR_ENCABEZADO = {"pequena": 2, "grande": 2, "muy_grande": 3}


def _codificar(texto):
    """Codifica texto a bytes de impresora (CP858 → CP850 → CP437 → Latin-1).

    CP858 y CP850 comparten los bytes de los acentos españoles; solo
    difieren en el símbolo € (byte 0xD5). Se intenta CP858 primero para
    conservar el € y se degrada sin romper si el juego no lo soporta.
    """
    for codificacion in ("cp858", "cp850", "cp437", "latin-1"):
        try:
            return str(texto).encode(codificacion, errors="replace")
        except LookupError:
            continue
    return str(texto).encode("ascii", errors="replace")


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


def _rasterizar_logo(ruta, puntos_ancho, puntos_alto_max=192):
    """Convierte una imagen en mapa de bits ESC/POS (comando ``GS v 0``).

    El resultado es blanco y negro puro: primero se compone la imagen
    sobre fondo blanco (para que las transparencias no salgan negras),
    se reescala al ancho del cabezal y se umbraliza sin grises, porque
    los térmicos imprimen los grises como manchas.

    Devuelve los bytes del comando listo para enviar o ``None`` si no
    hay Pillow, la imagen no existe o falla el procesado.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        imagen = Image.open(ruta)
        if imagen.mode != "RGBA":
            imagen = imagen.convert("RGBA")
        fondo = Image.new("RGBA", imagen.size, (255, 255, 255, 255))
        imagen = Image.alpha_composite(fondo, imagen).convert("L")

        escala = min(
            puntos_ancho / imagen.width,
            puntos_alto_max / imagen.height,
        )
        nuevo_tamano = (
            max(1, int(imagen.width * escala)),
            max(1, int(imagen.height * escala)),
        )
        imagen = imagen.resize(nuevo_tamano, Image.LANCZOS)

        # Umbral fijo -> 1 bit real (negro o blanco, nada intermedio)
        imagen = imagen.point(lambda p: 255 if p >= 128 else 0).convert("1")

        fila_bytes = (imagen.width + 7) // 8
        datos = bytearray()
        pixeles = imagen.load()
        for y in range(imagen.height):
            fila = bytearray(fila_bytes)
            for x in range(imagen.width):
                if not pixeles[x, y]:  # 0 = negro en modo "1"
                    fila[x // 8] |= 0x80 >> (x % 8)
            datos += fila
        if not datos:
            return None

        # GS v 0 m xL xH yL yH d1...dk  (raster bit image, modo normal)
        # Ojo: la '0' y la 'm' (0x30) son obligatorias; sin ellas la
        # impresora interpreta mal el encabezado e imprime basura.
        cabecera = b"\x1dv0\x30" + bytes((
            fila_bytes & 0xFF, (fila_bytes >> 8) & 0xFF,
            imagen.height & 0xFF, (imagen.height >> 8) & 0xFF,
        ))
        return cabecera + bytes(datos)
    except Exception:
        return None


class TicketTermico:
    """Constructor de tickets ESC/POS.

    *letra* elige el tamaño del cuerpo entre las claves de
    :data:`ESCALAS_LETRA` («pequena», «grande», «muy_grande»); por
    defecto «muy_grande» (doble ancho y alto) para que el texto sea
    legible de un vistazo. *logo* es la ruta opcional de una imagen que
    se imprime rasterizada sobre el nombre de la empresa.
    """

    def __init__(self, ancho=ANCHO_80MM, empresa="Mi Empresa",
                 letra="muy_grande", logo=None, negocio=None):
        self.ancho = ancho
        self.empresa = empresa
        self.negocio = negocio or {}
        if letra not in ESCALAS_LETRA:
            letra = "muy_grande"
        self.letra = letra
        # Con doble ancho caben la mitad de caracteres por línea
        multiplicador = 2 if letra == "muy_grande" else 1
        self.columnas = max(16, self.ancho // multiplicador)
        mult_encabezado = MULTIPLICADOR_ENCABEZADO[letra]
        self.columnas_encabezado = max(6, self.ancho // mult_encabezado)
        self._fuente_cuerpo = ESCALAS_LETRA[letra]
        self._escala_encabezado = ESCALA_ENCABEZADO[letra]
        self.logo_ruta = logo if logo and os.path.exists(logo) else None
        self.puntos_ancho = PUNTOS_POR_ANCHO.get(ancho, 512)
        self._partes = [INICIO, CODEPAGE_PC850, self._fuente_cuerpo]

    # ---------------------------------------------------------- bloques
    def encabezado(self):
        nombre = (self.negocio.get("nombre") or self.empresa).upper()
        if self.logo_ruta is not None:
            raster = _rasterizar_logo(self.logo_ruta, self.puntos_ancho)
            if raster is not None:
                self._partes += [CENTRO, raster, b"\n"]
        self._partes += [
            CENTRO,
            self._escala_encabezado,
            NEGRITA_ON,
            _linea(nombre[: self.columnas_encabezado]),
            self._fuente_cuerpo,
            NEGRITA_OFF,
        ]
        # Nombre comercial / de la tienda, justo bajo la razón social.
        nombre_comercial = self.negocio.get("nombre_comercial")
        if nombre_comercial:
            self._partes += [CENTRO, _linea(str(nombre_comercial))]
        # Membrete completo del negocio (NIF, dirección, teléfono, email)
        for linea_extra in self._lineas_negocio():
            self._partes.append(CENTRO)
            self._partes.append(_linea(linea_extra))
        self._partes += [
            CENTRO,
            _linea("RECIBO DE VENTA"),
            b"\n",
        ]
        return self

    def _lineas_negocio(self):
        """Devuelve las líneas del membrete fiscal usando datos del perfil."""
        lineas = []
        nif = self.negocio.get("nif")
        if nif:
            lineas.append(f"NIF: {nif}")
        direccion = self.negocio.get("direccion")
        if direccion:
            linea_dir = str(direccion)
            cp = self.negocio.get("codigo_postal")
            provincia = self.negocio.get("provincia")
            if cp or provincia:
                linea_dir = f"{linea_dir}, {cp or ''} {provincia or ''}".strip()
            lineas.append(linea_dir.strip())
        telefono = self.negocio.get("telefono")
        email = self.negocio.get("email")
        if telefono or email:
            contacto = ", ".join(
                p for p in (f"Tel: {telefono}" if telefono else "",
                            email or "") if p
            )
            lineas.append(contacto)
        return lineas

    def info(self, numero_factura, fecha, cliente=None):
        self._partes += [
            IZQUIERDA,
            _fila_dos_columnas(
                f"Recibo: {numero_factura}", fecha, self.columnas
            ),
        ]
        if cliente:
            self._partes.append(_linea(f"Cliente: {cliente}"))
        return self

    def separador(self):
        self._partes.append(_linea("-" * self.columnas))
        return self

    def linea_producto(self, nombre, cantidad, precio, subtotal):
        from ..core import moneda as mod_moneda
        nombre = str(nombre)[: self.columnas]
        self._partes.append(
            _fila_dos_columnas(nombre, mod_moneda.format_currency(subtotal), self.columnas)
        )
        self._partes.append(
            _linea(f"  {cantidad} x {mod_moneda.format_currency(precio)}")
        )
        return self

    def totales(self, total, base=None, cuota=None):
        from ..core import moneda as mod_moneda
        self._partes.append(NEGRITA_ON)
        self._partes.append(
            _fila_dos_columnas(
                "TOTAL", mod_moneda.format_currency(total), self.columnas
            )
        )
        self._partes.append(NEGRITA_OFF)
        if base is not None:
            self._partes.append(
                _fila_dos_columnas(
                    "Base imponible", mod_moneda.format_currency(base), self.columnas
                )
            )
        if cuota is not None:
            self._partes.append(
                _fila_dos_columnas(
                    "Cuota IVA", mod_moneda.format_currency(cuota), self.columnas
                )
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
    letra="muy_grande",
    logo=None,
    negocio=None,
):
    """Genera los bytes del ticket completo de una venta.

    *productos* es una secuencia de tuplas
    ``(nombre, precio, cantidad, subtotal[, ...])`` tal y como las
    produce el módulo de ventas. *logo* es una ruta de imagen opcional
    que se imprime rasterizada en el encabezado. *negocio* es un diccionario
    opcional con el membrete fiscal (``nombre``, ``nif``, ``direccion``,
    ``codigo_postal``, ``provincia``, ``telefono``, ``email``).
    """
    ticket = TicketTermico(
        ancho=ancho, empresa=empresa, letra=letra, logo=logo, negocio=negocio
    )
    ticket.encabezado().info(numero_factura, fecha, cliente).separador()
    for producto in productos:
        nombre, precio, cantidad, subtotal = producto[0], producto[1], producto[2], producto[3]
        ticket.linea_producto(nombre, cantidad, precio, subtotal)
    ticket.separador().totales(total, base, cuota).metodo_pago(metodo_pago)
    ticket.pie().cortar()
    return ticket.construir()


def construir_ticket_arqueo(
    resumen,
    total_esperado,
    total_contado,
    diferencia,
    fecha_apertura="",
    fecha_cierre="",
    usuario="",
    empresa="Mi Empresa",
    ancho=ANCHO_80MM,
    letra="muy_grande",
    logo=None,
    negocio=None,
):
    """Genera los bytes del ticket térmico de informe de cierre de caja.

    *resumen* es un diccionario (ver :func:`reyger.core.cierre_caja.resumen_ventas`)
    con los totales por método de pago del período.
    """
    from ..core import moneda as mod_moneda

    ticket = TicketTermico(
        ancho=ancho, empresa=empresa, letra=letra, logo=logo, negocio=negocio
    )
    ticket.encabezado()
    ticket._partes += [CENTRO, NEGRITA_ON, _linea("INFORME DE CIERRE DE CAJA"), NEGRITA_OFF]
    ticket._partes += [IZQUIERDA]
    if fecha_cierre:
        ticket._partes.append(_linea(f"Fecha: {fecha_cierre}"))
    if usuario:
        ticket._partes.append(_linea(f"Usuario: {usuario}"))
    ticket.separador()
    if fecha_apertura and fecha_cierre:
        ticket._partes.append(_linea(f"Desde: {fecha_apertura}"))
        ticket._partes.append(_linea(f"Hasta: {fecha_cierre}"))
    ticket._partes.append(
        _fila_dos_columnas(
            "Total ventas", mod_moneda.format_currency(resumen["total_ventas"]),
            ticket.columnas,
        )
    )
    ticket._partes.append(
        _fila_dos_columnas(
            "Efectivo esperado",
            mod_moneda.format_currency(resumen["efectivo_neto"]),
            ticket.columnas,
        )
    )
    ticket._partes.append(
        _fila_dos_columnas(
            "Tarjeta", mod_moneda.format_currency(resumen["tarjeta"]),
            ticket.columnas,
        )
    )
    ticket._partes.append(
        _fila_dos_columnas(
            "Ingresos manuales", mod_moneda.format_currency(resumen["ingreso_manual"]),
            ticket.columnas,
        )
    )
    ticket._partes.append(
        _fila_dos_columnas(
            "Retiros manuales", mod_moneda.format_currency(resumen["retiro_manual"]),
            ticket.columnas,
        )
    )
    ticket.separador()
    ticket._partes += [NEGRITA_ON]
    ticket._partes.append(
        _fila_dos_columnas(
            "Total esperado", mod_moneda.format_currency(total_esperado),
            ticket.columnas,
        )
    )
    ticket._partes.append(
        _fila_dos_columnas(
            "Total contado", mod_moneda.format_currency(total_contado),
            ticket.columnas,
        )
    )
    ticket._partes += [NEGRITA_OFF]
    if diferencia:
        etiqueta = "Diferencia (a favor)" if diferencia > 0 else "Diferencia (en contra)"
        ticket._partes.append(
            _fila_dos_columnas(
                etiqueta, mod_moneda.format_currency(diferencia), ticket.columnas
            )
        )
    ticket.separador().pie().cortar()
    return ticket.construir()


def imprimir_ticket_arqueo(
    resumen,
    total_esperado,
    total_contado,
    diferencia,
    fecha_apertura="",
    fecha_cierre="",
    usuario="",
    empresa="Mi Empresa",
    ancho=ANCHO_80MM,
    letra="muy_grande",
    impresora=None,
    logo=None,
    negocio=None,
):
    """Construye y envía el informe de cierre de caja. Devuelve (ok, mensaje)."""
    datos = construir_ticket_arqueo(
        resumen, total_esperado, total_contado, diferencia,
        fecha_apertura, fecha_cierre, usuario, empresa, ancho, letra,
        logo, negocio,
    )
    if enviar_bytes(datos, impresora):
        return True, "Informe de cierre de caja impreso correctamente"
    return False, "No se pudo imprimir el informe (impresora no disponible o error de envío)"


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
                          letra="muy_grande", impresora=None, logo=None,
                          negocio=None):
    """Construye y envía el ticket. Devuelve (ok, mensaje)."""
    datos = construir_ticket_venta(
        numero_factura, fecha, productos, total, base, cuota,
        metodo_pago, cliente, empresa, ancho, letra, logo, negocio,
    )
    if enviar_bytes(datos, impresora):
        return True, "Ticket impreso correctamente"
    return False, (
        "No se pudo imprimir el ticket.\n"
        "Revise la configuración de la impresora térmica en Ajustes."
    )
