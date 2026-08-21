"""Sesiones de caja: apertura y cierre ligados al usuario autenticado."""

from .db import query_one, execute


def abrir_sesion(usuario_id):
    """Abre una sesión de caja para el usuario y devuelve su id."""
    return execute(
        "INSERT INTO sesiones_caja (usuario_id) VALUES (?)", (usuario_id,)
    )


def cerrar_sesion(sesion_id):
    """Marca la sesión como cerrada con la hora actual."""
    if sesion_id is None:
        return
    execute(
        "UPDATE sesiones_caja SET cierre = CURRENT_TIMESTAMP,"
        " estado = 'cerrada' WHERE id = ? AND estado = 'abierta'",
        (sesion_id,),
    )


def sesion_abierta(sesion_id):
    """Devuelve la fila de la sesión si sigue abierta; None si no."""
    if sesion_id is None:
        return None
    return query_one(
        "SELECT id FROM sesiones_caja WHERE id = ? AND estado = 'abierta'",
        (sesion_id,),
    )
