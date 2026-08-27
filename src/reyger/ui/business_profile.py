"""Perfil fiscal y de contacto de la empresa (singleton en BD).

La tabla ``business_profile`` contiene una única fila (id=1) con los
datos necesarios para facturas, tickets, albaranes y el cumplimiento
VeriFactu (NIF, actividad económica, número de series, etc.).
"""

from ..core import db


CAMPOS = (
    "nombre",
    "nif",
    "direccion",
    "codigo_postal",
    "provincia",
    "telefono",
    "email",
    "actividad_economica",
    "numero_series",
    "logo_path",
    "moneda",
    "locale",
)

DEFAULTS = {
    "nombre": "Mi Empresa",
    "nif": "",
    "direccion": "",
    "codigo_postal": "",
    "provincia": "",
    "telefono": "",
    "email": "",
    "actividad_economica": "",
    "numero_series": "A",
    "logo_path": None,
    "moneda": "EUR",
    "locale": "es_ES",
}


def obtener():
    """Devuelve el perfil como ``sqlite3.Row`` o ``None`` si la tabla está vacía."""
    return db.query_one("SELECT * FROM business_profile WHERE id = 1")


def obtener_campo(campo):
    """Devuelve el valor de un campo concreto o su valor por defecto."""
    if campo not in CAMPOS:
        raise ValueError(f"Campo desconocido: {campo}")
    fila = db.query_one(f"SELECT {campo} FROM business_profile WHERE id = 1")
    if fila is None:
        return DEFAULTS.get(campo)
    valor = fila[campo]
    return valor if valor is not None else DEFAULTS.get(campo)


def guardar(**kwargs):
    """Actualiza los campos indicados del perfil.

    Crea la fila si aún no existe.  Acepta solo campos conocidos; los
    demás se ignoran silenciosamente.

    Devuelve ``True`` si se guardó correctamente.
    """
    campos_validos = {c: kwargs[c] for c in CAMPOS if c in kwargs}
    if not campos_validos:
        return False

    conn = db.get_connection()
    existente = conn.execute(
        "SELECT id FROM business_profile WHERE id = 1"
    ).fetchone()

    if existente:
        sets = ", ".join(f"{k} = ?" for k in campos_validos)
        vals = list(campos_validos.values())
        conn.execute(
            f"UPDATE business_profile SET {sets}, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = 1",
            vals,
        )
    else:
        columnas = list(campos_validos.keys()) + ["id"]
        placeholders = ", ".join(["?"] * len(campos_validos) + ["1"])
        vals = list(campos_validos.values())
        conn.execute(
            f"INSERT INTO business_profile ({', '.join(columnas)}) VALUES ({placeholders})",
            vals,
        )
    conn.commit()
    return True


def nombre_empresa():
    """Abreviatura para obtener solo el nombre de la empresa."""
    return obtener_campo("nombre")


def nif():
    """Abreviatura para obtener solo el NIF."""
    return obtener_campo("nif")
