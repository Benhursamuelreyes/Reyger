"""Persistencia Segura: encriptación de copias de seguridad.

Utiliza Fernet (AES-128-CBC + HMAC-SHA256) del paquete ``cryptography``
para encriptar y desencriptar ficheros de backup.

La clave se genera en el primer arranque y se almacena en
``<user_data>/reyger.key``. Sin esta clave, los backups encriptados
no se pueden descifrar.
"""

import os
from typing import Optional

from ..resources import get_user_data_path


def _ruta_clave() -> str:
    """Ruta completa al fichero de clave Fernet."""
    return os.path.join(get_user_data_path(), "reyger.key")


def generar_clave() -> bytes:
    """Genera una nueva clave Fernet y la persiste en disco.

    Si ya existe una clave, la lee y retorna esa misma clave.
    """
    from cryptography.fernet import Fernet

    ruta = _ruta_clave()
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return f.read().strip()

    clave = Fernet.generate_key()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(clave)
    return clave


def cargar_clave() -> Optional[bytes]:
    """Carga la clave Fernet desde disco.

    Devuelve ``None`` si no existe el fichero de clave.
    """
    ruta = _ruta_clave()
    if not os.path.exists(ruta):
        return None
    with open(ruta, "rb") as f:
        return f.read().strip()


def cifrar_fichero(ruta_entrada: str, ruta_salida: Optional[str] = None) -> str:
    """Encripta un fichero con Fernet y lo guarda en *ruta_salida*.

    Si no se proporciona *ruta_salida*, se usa ``<entrada>.enc``.
    Devuelve la ruta del fichero encriptado.
    """
    from cryptography.fernet import Fernet

    if ruta_salida is None:
        ruta_salida = ruta_entrada + ".enc"

    clave = generar_clave()
    fernet = Fernet(clave)

    with open(ruta_entrada, "rb") as f:
        datos = f.read()

    token = fernet.encrypt(datos)

    with open(ruta_salida, "wb") as f:
        f.write(token)

    return ruta_salida


def descifrar_fichero(ruta_entrada: str, ruta_salida: Optional[str] = None) -> str:
    """Desencripta un fichero Fernet y lo guarda en *ruta_salida*.

    Si no se proporciona *ruta_salida*, se elimina la extensión ``.enc``.
    Devuelve la ruta del fichero desencriptado.

    Raises:
        cryptography.fernet.InvalidToken: si la clave no coincide.
    """
    from cryptography.fernet import Fernet

    if ruta_salida is None:
        if ruta_entrada.endswith(".enc"):
            ruta_salida = ruta_entrada[:-4]
        else:
            ruta_salida = ruta_entrada + ".dec"

    clave = cargar_clave()
    if clave is None:
        raise FileNotFoundError(
            "No se encontró la clave de encriptación. "
            "No se puede descifrar el backup."
        )

    fernet = Fernet(clave)

    with open(ruta_entrada, "rb") as f:
        token = f.read()

    datos = fernet.decrypt(token)

    with open(ruta_salida, "wb") as f:
        f.write(datos)

    return ruta_salida


def existe_clave() -> bool:
    """Indica si ya existe una clave Fernet en disco."""
    return os.path.exists(_ruta_clave())


def ruta_clave() -> str:
    """Devuelve la ruta al fichero de clave."""
    return _ruta_clave()
