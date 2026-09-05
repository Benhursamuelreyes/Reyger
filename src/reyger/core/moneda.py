"""Formateo global de moneda y configuración regional para Reyger.

Centraliza la globalización del formato de importes: en lugar de
concatenar ``€`` a mano, las vistas Tkinter, los tickets térmicos y las
plantillas PDF usan :func:`format_currency`, que aplica el símbolo y los
separadores de miles/decimales según la moneda y el locale elegidos en
Ajustes.

Los importes siempre se almacenan en la base de datos como números
puros (REAL) por ``fiscal.py`` y las capas de persistencia; aquí solo se
convierte a texto para MOSTRAR en pantalla o PPF.

La preferencia de moneda y locale vive en la tabla singleton
``business_profile`` (id=1) de la base de datos.

La cobertura de países/monedas abarca los cinco continentes. Dentro de
una coalición monetaria (Unión Europea→EUR, ECOWAS→XOF, etc.) solo se
añade el país; la moneda compartida se define una única vez en
:data:`MONEDAS` y cada país de :data:`PAISES` la referencia por código.
"""

from ..ui import business_profile as bp

#: Símbolo, posición y **nombre legible** para cada código ISO de moneda.
#: ``posicion`` es True si el símbolo precede al importe (ej. $), False
#: si va después (ej. € al final).
MONEDAS = {
    # Europa
    "EUR": {"simbolo": "€", "posicion": False, "nombre": "Euro"},
    "GBP": {"simbolo": "£", "posicion": True, "nombre": "Libra esterlina"},
    "CHF": {"simbolo": "CHF", "posicion": False, "nombre": "Franco suizo"},
    "NOK": {"simbolo": "kr", "posicion": False, "nombre": "Corona noruega"},
    "SEK": {"simbolo": "kr", "posicion": False, "nombre": "Corona sueca"},
    "DKK": {"simbolo": "kr", "posicion": False, "nombre": "Corona danesa"},
    "ISK": {"simbolo": "kr", "posicion": False, "nombre": "Corona islandesa"},
    "PLN": {"simbolo": "zł", "posicion": False, "nombre": "Zloty polaco"},
    "CZK": {"simbolo": "Kč", "posicion": False, "nombre": "Corona checa"},
    "HUF": {"simbolo": "Ft", "posicion": False, "nombre": "Florín húngaro"},
    "RON": {"simbolo": "lei", "posicion": False, "nombre": "Leu rumano"},
    # América
    "USD": {"simbolo": "$", "posicion": True, "nombre": "Dólar estadounidense"},
    "CAD": {"simbolo": "C$", "posicion": True, "nombre": "Dólar canadiense"},
    "MXN": {"simbolo": "$", "posicion": True, "nombre": "Peso mexicano"},
    "BRL": {"simbolo": "R$", "posicion": True, "nombre": "Real brasileño"},
    "ARS": {"simbolo": "$", "posicion": True, "nombre": "Peso argentino"},
    "CLP": {"simbolo": "$", "posicion": True, "nombre": "Peso chileno"},
    "COP": {"simbolo": "$", "posicion": True, "nombre": "Peso colombiano"},
    "PEN": {"simbolo": "S/", "posicion": True, "nombre": "Sol peruano"},
    "VES": {"simbolo": "Bs.", "posicion": True, "nombre": "Bolívar venezolano"},
    "UYU": {"simbolo": "$U", "posicion": True, "nombre": "Peso uruguayo"},
    "PYG": {"simbolo": "₲", "posicion": True, "nombre": "Guaraní paraguayo"},
    "BOB": {"simbolo": "Bs", "posicion": True, "nombre": "Boliviano"},
    "PAB": {"simbolo": "B/.", "posicion": True, "nombre": "Balboa panameño"},
    "CRC": {"simbolo": "₡", "posicion": True, "nombre": "Colón costarricense"},
    "NIO": {"simbolo": "C$", "posicion": True, "nombre": "Córdoba nicaragüense"},
    "HNL": {"simbolo": "L", "posicion": True, "nombre": "Lempira hondureño"},
    "GTQ": {"simbolo": "Q", "posicion": True, "nombre": "Quetzal guatemalteco"},
    "DOP": {"simbolo": "RD$", "posicion": True, "nombre": "Peso dominicano"},
    "CUP": {"simbolo": "$", "posicion": True, "nombre": "Peso cubano"},
    "JMD": {"simbolo": "J$", "posicion": True, "nombre": "Dólar jamaiquino"},
    # Asia
    "JPY": {"simbolo": "¥", "posicion": True, "nombre": "Yen japonés"},
    "CNY": {"simbolo": "¥", "posicion": True, "nombre": "Yuan chino"},
    "KRW": {"simbolo": "₩", "posicion": True, "nombre": "Won surcoreano"},
    "INR": {"simbolo": "₹", "posicion": True, "nombre": "Rupia india"},
    "IDR": {"simbolo": "Rp", "posicion": True, "nombre": "Rupia indonesia"},
    "PHP": {"simbolo": "₱", "posicion": True, "nombre": "Peso filipino"},
    "THB": {"simbolo": "฿", "posicion": True, "nombre": "Baht tailandés"},
    "VND": {"simbolo": "₫", "posicion": True, "nombre": "Đồng vietnamita"},
    "MYR": {"simbolo": "RM", "posicion": True, "nombre": "Ringgit malayo"},
    "SGD": {"simbolo": "S$", "posicion": True, "nombre": "Dólar de Singapur"},
    "ILS": {"simbolo": "₪", "posicion": True, "nombre": "Séquel israelí"},
    "SAR": {"simbolo": "SR", "posicion": True, "nombre": "Riyal saudí"},
    "AED": {"simbolo": "AED", "posicion": False, "nombre": "Dírham de los EAU"},
    "TRY": {"simbolo": "₺", "posicion": True, "nombre": "Lira turca"},
    "PKR": {"simbolo": "₨", "posicion": True, "nombre": "Rupia pakistaní"},
    "BDT": {"simbolo": "৳", "posicion": True, "nombre": "Taka bangladesí"},
    # África
    "ZAR": {"simbolo": "R", "posicion": True, "nombre": "Rand sudafricano"},
    "EGP": {"simbolo": "E£", "posicion": True, "nombre": "Libra egipcia"},
    "NGN": {"simbolo": "₦", "posicion": True, "nombre": "Naira nigeriana"},
    "KES": {"simbolo": "KSh", "posicion": True, "nombre": "Chelín keniano"},
    "GHS": {"simbolo": "GH₵", "posicion": True, "nombre": "Cedi ghanés"},
    "MAD": {"simbolo": "DH", "posicion": True, "nombre": "Dírham marroquí"},
    "DZD": {"simbolo": "DA", "posicion": True, "nombre": "Dinar argelino"},
    "TND": {"simbolo": "DT", "posicion": True, "nombre": "Dinar tunecino"},
    "XOF": {"simbolo": "FCFA", "posicion": False, "nombre": "Franco CFA de África Occidental"},
    "ETB": {"simbolo": "Br", "posicion": True, "nombre": "Birr etíope"},
    "TZS": {"simbolo": "TSh", "posicion": True, "nombre": "Chelín tanzano"},
    "AOA": {"simbolo": "Kz", "posicion": True, "nombre": "Kwanza angoleño"},
    "MZN": {"simbolo": "MT", "posicion": False, "nombre": "Metical mozambiqueño"},
    # Oceanía
    "AUD": {"simbolo": "A$", "posicion": True, "nombre": "Dólar australiano"},
    "NZD": {"simbolo": "NZ$", "posicion": True, "nombre": "Dólar neozelandés"},
    "FJD": {"simbolo": "FJ$", "posicion": True, "nombre": "Dólar fiyiano"},
    "PGK": {"simbolo": "K", "posicion": True, "nombre": "Kina papú"},
}

#: Países soportados: locale -> país, moneda (código ISO) y continente.
#: Es la fuente única de cara a la UI: país y nombre de moneda se muestran
#: como texto legible, pero el valor persistido es el código del locale.
PAISES = {
    # --- Europa (zona euro: solo se añade el país, moneda compartida EUR)
    "es_ES": {"pais": "España", "moneda": "EUR", "continente": "Europa"},
    "de_DE": {"pais": "Alemania", "moneda": "EUR", "continente": "Europa"},
    "fr_FR": {"pais": "Francia", "moneda": "EUR", "continente": "Europa"},
    "it_IT": {"pais": "Italia", "moneda": "EUR", "continente": "Europa"},
    "pt_PT": {"pais": "Portugal", "moneda": "EUR", "continente": "Europa"},
    "nl_NL": {"pais": "Países Bajos", "moneda": "EUR", "continente": "Europa"},
    "el_GR": {"pais": "Grecia", "moneda": "EUR", "continente": "Europa"},
    "en_IE": {"pais": "Irlanda", "moneda": "EUR", "continente": "Europa"},
    "de_AT": {"pais": "Austria", "moneda": "EUR", "continente": "Europa"},
    "fi_FI": {"pais": "Finlandia", "moneda": "EUR", "continente": "Europa"},
    "nl_BE": {"pais": "Bélgica", "moneda": "EUR", "continente": "Europa"},
    # --- Europa (UE con moneda propia o no UE)
    "en_GB": {"pais": "Reino Unido", "moneda": "GBP", "continente": "Europa"},
    "de_CH": {"pais": "Suiza", "moneda": "CHF", "continente": "Europa"},
    "nb_NO": {"pais": "Noruega", "moneda": "NOK", "continente": "Europa"},
    "sv_SE": {"pais": "Suecia", "moneda": "SEK", "continente": "Europa"},
    "da_DK": {"pais": "Dinamarca", "moneda": "DKK", "continente": "Europa"},
    "is_IS": {"pais": "Islandia", "moneda": "ISK", "continente": "Europa"},
    "pl_PL": {"pais": "Polonia", "moneda": "PLN", "continente": "Europa"},
    "cs_CZ": {"pais": "Chequia", "moneda": "CZK", "continente": "Europa"},
    "hu_HU": {"pais": "Hungría", "moneda": "HUF", "continente": "Europa"},
    "ro_RO": {"pais": "Rumanía", "moneda": "RON", "continente": "Europa"},
    # --- América
    "en_US": {"pais": "Estados Unidos", "moneda": "USD", "continente": "América"},
    "en_CA": {"pais": "Canadá", "moneda": "CAD", "continente": "América"},
    "es_MX": {"pais": "México", "moneda": "MXN", "continente": "América"},
    "pt_BR": {"pais": "Brasil", "moneda": "BRL", "continente": "América"},
    "es_AR": {"pais": "Argentina", "moneda": "ARS", "continente": "América"},
    "es_CL": {"pais": "Chile", "moneda": "CLP", "continente": "América"},
    "es_CO": {"pais": "Colombia", "moneda": "COP", "continente": "América"},
    "es_PE": {"pais": "Perú", "moneda": "PEN", "continente": "América"},
    "es_EC": {"pais": "Ecuador", "moneda": "USD", "continente": "América"},
    "es_VE": {"pais": "Venezuela", "moneda": "VES", "continente": "América"},
    "es_UY": {"pais": "Uruguay", "moneda": "UYU", "continente": "América"},
    "es_PY": {"pais": "Paraguay", "moneda": "PYG", "continente": "América"},
    "es_BO": {"pais": "Bolivia", "moneda": "BOB", "continente": "América"},
    "es_PA": {"pais": "Panamá", "moneda": "PAB", "continente": "América"},
    "es_CR": {"pais": "Costa Rica", "moneda": "CRC", "continente": "América"},
    "es_NI": {"pais": "Nicaragua", "moneda": "NIO", "continente": "América"},
    "es_HN": {"pais": "Honduras", "moneda": "HNL", "continente": "América"},
    "es_SV": {"pais": "El Salvador", "moneda": "USD", "continente": "América"},
    "es_GT": {"pais": "Guatemala", "moneda": "GTQ", "continente": "América"},
    "es_DO": {"pais": "República Dominicana", "moneda": "DOP", "continente": "América"},
    "es_CU": {"pais": "Cuba", "moneda": "CUP", "continente": "América"},
    "es_PR": {"pais": "Puerto Rico", "moneda": "USD", "continente": "América"},
    "en_JM": {"pais": "Jamaica", "moneda": "JMD", "continente": "América"},
    # --- Asia
    "ja_JP": {"pais": "Japón", "moneda": "JPY", "continente": "Asia"},
    "zh_CN": {"pais": "China", "moneda": "CNY", "continente": "Asia"},
    "ko_KR": {"pais": "Corea del Sur", "moneda": "KRW", "continente": "Asia"},
    "hi_IN": {"pais": "India", "moneda": "INR", "continente": "Asia"},
    "id_ID": {"pais": "Indonesia", "moneda": "IDR", "continente": "Asia"},
    "fil_PH": {"pais": "Filipinas", "moneda": "PHP", "continente": "Asia"},
    "th_TH": {"pais": "Tailandia", "moneda": "THB", "continente": "Asia"},
    "vi_VN": {"pais": "Vietnam", "moneda": "VND", "continente": "Asia"},
    "ms_MY": {"pais": "Malasia", "moneda": "MYR", "continente": "Asia"},
    "en_SG": {"pais": "Singapur", "moneda": "SGD", "continente": "Asia"},
    "he_IL": {"pais": "Israel", "moneda": "ILS", "continente": "Asia"},
    "ar_SA": {"pais": "Arabia Saudita", "moneda": "SAR", "continente": "Asia"},
    "ar_AE": {"pais": "Emiratos Árabes Unidos", "moneda": "AED", "continente": "Asia"},
    "tr_TR": {"pais": "Turquía", "moneda": "TRY", "continente": "Asia"},
    "ur_PK": {"pais": "Pakistán", "moneda": "PKR", "continente": "Asia"},
    "bn_BD": {"pais": "Bangladés", "moneda": "BDT", "continente": "Asia"},
    # --- África
    "en_ZA": {"pais": "Sudáfrica", "moneda": "ZAR", "continente": "África"},
    "ar_EG": {"pais": "Egipto", "moneda": "EGP", "continente": "África"},
    "en_NG": {"pais": "Nigeria", "moneda": "NGN", "continente": "África"},
    "sw_KE": {"pais": "Kenia", "moneda": "KES", "continente": "África"},
    "en_GH": {"pais": "Ghana", "moneda": "GHS", "continente": "África"},
    "ar_MA": {"pais": "Marruecos", "moneda": "MAD", "continente": "África"},
    "ar_DZ": {"pais": "Argelia", "moneda": "DZD", "continente": "África"},
    "ar_TN": {"pais": "Túnez", "moneda": "TND", "continente": "África"},
    "fr_SN": {"pais": "Senegal", "moneda": "XOF", "continente": "África"},
    "fr_CI": {"pais": "Costa de Marfil", "moneda": "XOF", "continente": "África"},
    "am_ET": {"pais": "Etiopía", "moneda": "ETB", "continente": "África"},
    "sw_TZ": {"pais": "Tanzania", "moneda": "TZS", "continente": "África"},
    "pt_AO": {"pais": "Angola", "moneda": "AOA", "continente": "África"},
    "pt_MZ": {"pais": "Mozambique", "moneda": "MZN", "continente": "África"},
    # --- Oceanía
    "en_AU": {"pais": "Australia", "moneda": "AUD", "continente": "Oceanía"},
    "en_NZ": {"pais": "Nueva Zelanda", "moneda": "NZD", "continente": "Oceanía"},
    "en_FJ": {"pais": "Fiyi", "moneda": "FJD", "continente": "Oceanía"},
    "en_PG": {"pais": "Papúa Nueva Guinea", "moneda": "PGK", "continente": "Oceanía"},
}

#: Convenciones regionales de separadores: (separador_miles,
#: separador_decimales). Conserva 1:1 con :data:`PAISES`.
LOCALES = {
    "es_ES": (".", ","),
    "de_DE": (".", ","),
    "fr_FR": (" ", ","),
    "it_IT": (".", ","),
    "pt_PT": (".", ","),
    "nl_NL": (".", ","),
    "el_GR": (".", ","),
    "en_IE": (",", "."),
    "de_AT": (".", ","),
    "fi_FI": (" ", ","),
    "nl_BE": (".", ","),
    "en_GB": (",", "."),
    "de_CH": (".", ","),
    "nb_NO": (" ", ","),
    "sv_SE": (" ", ","),
    "da_DK": (" ", ","),
    "is_IS": (".", ","),
    "pl_PL": (".", ","),
    "cs_CZ": (".", ","),
    "hu_HU": (".", ","),
    "ro_RO": (".", ","),
    "en_US": (",", "."),
    "en_CA": (",", "."),
    "es_MX": (",", "."),
    "pt_BR": (".", ","),
    "es_AR": (".", ","),
    "es_CL": (".", ","),
    "es_CO": (".", ","),
    "es_PE": (".", ","),
    "es_EC": (".", ","),
    "es_VE": (".", ","),
    "es_UY": (".", ","),
    "es_PY": (".", ","),
    "es_BO": (".", ","),
    "es_PA": (",", "."),
    "es_CR": (",", "."),
    "es_NI": (",", "."),
    "es_HN": (",", "."),
    "es_SV": (",", "."),
    "es_GT": (",", "."),
    "es_DO": (",", "."),
    "es_CU": (".", ","),
    "es_PR": (",", "."),
    "en_JM": (",", "."),
    "ja_JP": (",", "."),
    "zh_CN": (",", "."),
    "ko_KR": (",", "."),
    "hi_IN": (",", "."),
    "id_ID": (".", ","),
    "fil_PH": (",", "."),
    "th_TH": (",", "."),
    "vi_VN": (".", ","),
    "ms_MY": (".", ","),
    "en_SG": (",", "."),
    "he_IL": (",", "."),
    "ar_SA": (",", "."),
    "ar_AE": (",", "."),
    "tr_TR": (".", ","),
    "ur_PK": (",", "."),
    "bn_BD": (",", "."),
    "en_ZA": (",", "."),
    "ar_EG": (",", "."),
    "en_NG": (",", "."),
    "sw_KE": (",", "."),
    "en_GH": (",", "."),
    "ar_MA": (",", "."),
    "ar_DZ": (",", "."),
    "ar_TN": (",", "."),
    "fr_SN": (",", "."),
    "fr_CI": (",", "."),
    "am_ET": (",", "."),
    "sw_TZ": (",", "."),
    "pt_AO": (".", ","),
    "pt_MZ": (".", ","),
    "en_AU": (",", "."),
    "en_NZ": (",", "."),
    "en_FJ": (",", "."),
    "en_PG": (",", "."),
}

#: Valor por defecto si no hay perfil configurado.
DEFAULTS = {"moneda": "EUR", "locale": "es_ES"}


def nombre_moneda(codigo):
    """Devuelve el nombre legible de una moneda (p. ej. ``Euro``)."""
    return MONEDAS[codigo]["nombre"]


def pais_por_locale(locale):
    """Devuelve ``(nombre_pais, codigo_moneda)`` de un locale configurado."""
    datos = PAISES[locale]
    return datos["pais"], datos["moneda"]


def monedas_ordenadas():
    """Códigos de moneda ordenados alfabéticamente por su nombre legible."""
    return sorted(MONEDAS, key=lambda c: MONEDAS[c]["nombre"])


def paises_ordenados():
    """Locales ordenados alfabéticamente por nombre de país."""
    return sorted(PAISES, key=lambda l: PAISES[l]["pais"])


def continentes():
    """Devuelve el conjunto de continentes cubiertos por :data:`PAISES`."""
    return {datos["continente"] for datos in PAISES.values()}


def moneda_para_locale(locale):
    """Devuelve el código de moneda asociado a un país (para vista previa)."""
    return PAISES[locale]["moneda"]


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
    """Nº de decimales por defecto según la moneda (JPY suele ser 0)."""
    return 0 if codigo_moneda() == "JPY" else 2


def _agrupar_miles(entero, sep_miles):
    """Inserta el separador de miles en la parte entera."""
    if not entero:
        return "0"
    invertido = entero[::-1]
    grupos = [invertido[i:i + 3] for i in range(0, len(invertido), 3)]
    return sep_miles.join(grupos)[::-1]


def format_number(amount, decimales=None, separacion=None):
    """Formatea un número puro con separadores del locale activo.

    Ej. ``1234567.5`` con es_ES → ``1.234.567,50``.
    *decimales* fuerza el nº de decimales; por defecto usa la moneda.
    *separacion* sobrescribe (separador_miles, separador_decimales)
    sin cambiar el locale persistido (p. ej. para vistas previas).
    """
    if decimales is None:
        decimales = cantidad_decimales()
    if separacion is None:
        m, d = separadores()
    else:
        m, d = separacion
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


def format_currency(amount, decimales=None, simbolo=None, posicion=None,
                    separacion=None):
    """Devuelve el importe formateado con su símbolo y posición según región.

    Ejemplos:
        * EUR + es_ES:   ``1.234,56 €``
        * USD + en_US:   ``$1,234.56``
        * HNL + es_HN:   ``L1,234.56``

    *simbolo* / *posicion* permiten sobrescribir el símbolo (p. ej. en
    cabeceras de tabla) sin cambiar la moneda global. *separacion*
    sobrescribe los separadores (miles, decimales) del importe.
    """
    if simbolo is None:
        simbolo = simbolo_moneda()
    if posicion is None:
        posicion = _posicion_simbolo()

    numero = format_number(amount, decimales=decimales, separacion=separacion)

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