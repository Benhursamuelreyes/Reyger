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


def autenticar(usuario, password):
    """Valida las credenciales contra la tabla usuarios.

    Devuelve un dict con (id, usuario, nombre, rol) si son correctas y
    el usuario está activo; None en caso contrario.
    """
    from .db import query_one

    fila = query_one(
        "SELECT id, usuario, password_hash, nombre, rol FROM usuarios"
        " WHERE usuario = ? AND activo = 1",
        (usuario,),
    )
    if fila is None or not verify_password(password, fila["password_hash"]):
        return None
    return {
        "id": fila["id"],
        "usuario": fila["usuario"],
        "nombre": fila["nombre"],
        "rol": fila["rol"],
    }


def crear_usuario(usuario, password, nombre, rol="cajero"):
    """Crea un usuario nuevo. Devuelve el id o None si ya existe."""
    from .db import execute

    if rol not in ("admin", "cajero"):
        raise ValueError(f"Rol desconocido: {rol}")
    try:
        return execute(
            "INSERT INTO usuarios (usuario, password_hash, nombre, rol)"
            " VALUES (?, ?, ?, ?)",
            (usuario, hash_password(password), nombre, rol),
        )
    except Exception:
        return None


def cambiar_password(usuario_id, password_nueva):
    """Establece una contraseña nueva para el usuario indicado."""
    from .db import execute

    execute(
        "UPDATE usuarios SET password_hash = ? WHERE id = ?",
        (hash_password(password_nueva), usuario_id),
    )
