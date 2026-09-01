"""Generación de códigos de barras (Code128-B) y códigos QR en memoria.

Se usan en los tickets regalo y en las devoluciones para que el lector/ESC
del TPV identifique rápidamente el ticket o la venta. Ambas funciones
devuelven una imagen PIL lista para rasterizar en la impresora térmica.
"""
from PIL import Image, ImageDraw

# Patrones de barras de Code128 (107 símbolos; índice = código del símbolo).
# Cada dígito es el ancho en módulos de una barra/espacio alterno (barra-par).
_C128 = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213",
    "122312", "132212", "221213", "221312", "231212", "112232", "122132",
    "122231", "113222", "123122", "123221", "223211", "221132", "221231",
    "213212", "223112", "312131", "311222", "321122", "321221", "312212",
    "322112", "322211", "212123", "212321", "232121", "111323", "131123",
    "131321", "112313", "132113", "132311", "211313", "231113", "231311",
    "112133", "112331", "132131", "113123", "113321", "133121", "313121",
    "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111",
    "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114",
    "413111", "241112", "134111", "111242", "121142", "121241", "114212",
    "124112", "124211", "411212", "421112", "421211", "212141", "214121",
    "412121", "111143", "111341", "131141", "114113", "114311", "411113",
    "411311", "113141", "114131", "311141", "411131", "211412", "211214",
    "211232", "2331112",
]

_START_B = 104
_STOP = 106


def _codigo_b128(texto):
    """Devuelve la secuencia de códigos (start, datos, checksum, stop)."""
    valores = [ord(c) - 32 for c in texto]  # Code128 subset B (ASCII 32-126)
    checksum = _START_B
    for i, v in enumerate(valores, start=1):
        checksum += v * i
    checksum %= 103
    return [_START_B] + valores + [checksum, _STOP]


def generar_barcode_pil(texto, altura=50, modulo=2, leer_humano=True):
    """Genera un código de barras Code128-B y devuelve una imagen PIL."""
    secuencia = _codigo_b128(texto)
    unidades = []
    for c in secuencia:
        unidades.append(_C128[c])
    # Aplicar módulo de barra
    p = 12  # quiet zone inicial (módulos)
    total_modulos = p
    for u in unidades:
        for d in u:
            total_modulos += int(d)
    total_modulos += 12  # quiet zone final

    ancho = total_modulos * modulo
    alto = altura + (16 if leer_humano else 2)
    imagen = Image.new("L", (ancho, alto), 255)
    dibujo = ImageDraw.Draw(imagen)

    x = p * modulo
    for i, u in enumerate(unidades):
        es_barra = True
        for d in u:
            ancho_d = int(d) * modulo
            if es_barra:
                dibujo.rectangle([x, 0, x + ancho_d - 1, altura - 1], fill=0)
            x += ancho_d
            es_barra = not es_barra

    if leer_humano:
        try:
            from PIL import ImageFont
            fuente = ImageFont.load_default()
        except Exception:
            fuente = None
        if fuente is None:
            return imagen
        w_texto = dibujo.textlength(texto, font=fuente)
        dibujo.text(
            ((ancho - w_texto) / 2, altura + 2),
            texto, fill=0, font=fuente,
        )
    return imagen


def generar_qr_pil(texto, tamano_modulo=6):
    """Genera un código QR y devuelve una imagen PIL."""
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=tamano_modulo,
        border=2,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("L")
