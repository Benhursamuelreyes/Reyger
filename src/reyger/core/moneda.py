"""Formateo global de moneda y configuración regional para Reyger.

Centraliza la globalización del formato de importes: en lugar de
concatenar ``€`` a mano, las vistas Tkinter, los tickets térmicos y las
plantillas PDF usan :func:`format_currency`, que aplica el símbolo y los
separadores de miles/decimales según la moneda y el locale elegidos en
Ajustes.

Los importes siempre se almacenan en la base de datos como números
puros (REAL) por ``fiscal.py`` y las capas de persistencia; aquí solo se
convierte a texto para MOSTRAR/mostrar en PPF.

La preferencia de moneda y locale vive en la tabla singleton
``business_profile`` (id=1) de la base de datos.
"""

from ..ui import business_profile as bp

#: Símbolo y posición para cada código ISO de moneda.
#: ``posicion`` es True si el símbolo precede al importe (ej. $), False
#: si va después (ej. € al final).
MONEDAS = {
    "EUR": {"simbolo": "€", "posicion": False},
    "USD": {"simbolo": "$", "posicion": True},
    "HNL": {"simbolo": "L", "posicion": True},
    "MXN": {"simbolo": "$", "posicion": True},
    "COP": {"simbolo": "$", "posicion": True},
    "GBP": {"simbolo": "£", "posicion": True},
    "JPY": {"simbolo": "¥", "posicion": True},
    "ARS": {"simbolo": "$", "posicion": True},
    "PEN": {"simbolo": "S/", "posicion": True},
    "CLP": {"simbolo": "$", "posicion": True},
    "BRL": {"simbolo": "R$", "posicion": True},
    "BOB": {"simbolo": "Bs", "posicion": True},
    "CRC": {"simbolo": "₡", "posicion": True},
    "PAB": {"simbolo": "B/.", "posicion": True},
    "NIO": {"simbolo": "C$", "posicion": True},
    "PYG": {"simbolo": "₲", "posicion": True},
    "UYU": {"simbolo": "$U", "posicion": True},
    "VES": {"simbolo": "Bs.", "posicion": True},
}

#: Convenciones regionales de separadores: (separador_miles,
#: separador_decimales).
LOCALES = {
    "es_ES": (".", ","),
    "en_US": (",", "."),
    "en_GB": (",", "."),
    "de_DE": (".", ","),
    "fr_FR": (" ", ","),
    "it_IT": (".", ","),
    "pt_BR": (".", ","),
    "en_HN": (",", "."),
    "es_MX": (",", "."),
    "es_CO": (".", ","),
    "es_AR": (".", ","),
    "es_CL": (".", ","),
    "ja_JP": (",", "."),
}

#: Valor por defecto si no hay perfil configurado.
DEFAULTS = {"moneda": "EUR", "locale": "es_ES"}


def codigo_moneda():
    """Devuelve el código ISO de la moneda configurada (por defecto EUR)."""
    try:
        valor = bp.obtener_campo("moneda") or DEFAULTS["moneda"]
    except Exception:
        return DEFAULTS["moneda"]
    if valor not in MONEDAS:
        valor = DEFAULTS["moneda"]
    return valor


def simbolo_moneda():
    """Devuelve el símbolo de la moneda configurada."""
    return MONEDAS[codigo_moneda()]["simbolo"]


def _posicion_simbolo():
    """True si el símbolo precede al importe (monedas pre-fijas)."""
    return MONEDAS[codigo_moneda()]["posicion"]


def locale_activo():
    """Devuelve el código del locale configurado (por defecto es_ES)."""
    try:
        valor = bp.obtener_campo("locale") or DEFAULTS["locale"]
    except Exception:
        return DEFAULTS["locale"]
    if valor not in LOCALES:
        valor = DEFAULTS["locale"]
    return valor


def separadores():
    """Devuelve (separador_miles, separador_decimales) del locale activo."""
    return LOCALES[locale_activo()]


def cantidad_decimales():
    """Nº de decimales por default según la moneda (JPY suele ser 0)."""
    return 0 if codigo_moneda() == "JPY" else 2


def _agrupar_miles(entero, sep_miles):
    """Inserta el separador de miles en la parte entera."""
    if not entero:
        return "0"
    invertido = entero[::-1]
    grupos = [invertido[i:i + 3] for i in range(0, len(invertido), 3)]
    return sep_miles.join(grupos)[::-1]


def format_number(amount, decimales=None):
    """Formatea un número puro con separadores del locale activo.

    Ej. ``1234567.5`` con es_ES → ``1.234.567,50``.
    *decimales* fuerza el nº de decimales; por defecto usa la moneda.
    """
    if decimales is None:
        decimales = cantidad_decimales()
    m, d = separadores()
    try:
        valor = float(amount)
    except (TypeError, ValueError):
        valor = 0.0
    cantidad = "{:.{}f}".format(valor, decimales)
    entero, _, parte_decimal = cantidad.partition(".")
    entero_fmt = _agrupar_miles(entero, m)
    if decimales <= 0:
        return entero_fmt
    return f"{entero_fmt}{d}{parte_decimal}"


def format_currency(amount, decimales=None, simbolo=None, posicion=None):
    """Devuelve el importe formateado con su símbolo y posición según región.

    Ejemplos:
        * EUR + es_ES:   ``1.234,56 €``
        * USD + en_US:   ``$1,234.56``
        * HNL + en_HN:   ``L1,234.56``

    *simbolo* / *posicion* permiten sobrescribir el símbolo (p. ej. en
    cabeceras de tabla) sin cambiar la moneda global.
    """
    if simbolo is None:
        simbolo = simbolo_moneda()
    if posicion is None:
        posicion = _posicion_simbolo()

    numero = format_number(amount, decimales=decimales)

    if posicion:
        # Símbolo prefijo, sin espacio (convención $1.234,56)
        return f"{simbolo}{numero}"
    # Símbolo sufijo con espacio (convención 1.234,56 €)
    return f"{numero} {simbolo}"


def guardar_moneda(moneda):
    """Persiste la moneda elegida en business_profile (no toca la UI)."""
    if moneda not in MONEDAS:
        moneda = DEFAULTS["moneda"]
    bp.guardar(moneda=moneda)


def guardar_locale(locale):
    """Persiste el locale elegido en business_profile (no toca la UI)."""
    if locale not in LOCALES:
        locale = DEFAULTS["locale"]
    bp.guardar(locale=locale)
