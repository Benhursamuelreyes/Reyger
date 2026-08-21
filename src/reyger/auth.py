"""Utilidades de autenticación: hashing y verificación de contraseñas.

Se usa PBKDF2-HMAC-SHA256 de la librería estándar (sin dependencias
externas). El formato almacenado es:

    pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>
"""

import hashlib
import hmac
import os

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 120_000


def hash_password(password):
    """Devuelve el hash PBKDF2 de *password* con salt aleatorio."""
    salt = os.urandom(16)
    digesto = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERACIONES
    )
    return f"{ALGORITMO}${ITERACIONES}${salt.hex()}${digesto.hex()}"


def verify_password(password, almacenado):
    """Comprueba *password* contra el hash *almacenado* (tiempo constante)."""
    try:
        algoritmo, iteraciones, salt_hex, digesto_hex = almacenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        digesto = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iteraciones),
        )
        return hmac.compare_digest(digesto.hex(), digesto_hex)
    except (ValueError, AttributeError, TypeError):
        return False
