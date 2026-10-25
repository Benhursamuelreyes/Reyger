"""Registro de eventos y errores de la aplicación.

La app empaquetada se ejecuta sin consola (``console = false``), así que
cualquier ``print`` o traza de Tk se pierde. Este módulo envía todo a un
fichero rotativo en la carpeta de datos del usuario (``reyger.log``, junto a
``crash.log``), para poder diagnosticar fallos en el equipo del cliente.

Uso en cada módulo::

    import logging
    log = logging.getLogger(__name__)
"""

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

from ..resources import get_user_data_path

NOMBRE_FICHERO = "reyger.log"
TAMANO_MAXIMO = 1_000_000  # bytes por fichero
COPIAS = 3  # reyger.log.1 ... reyger.log.3

FORMATO = "%(asctime)s %(levelname)-8s %(name)s [%(threadName)s] %(message)s"

_log = logging.getLogger("reyger")


def ruta_registro():
    return os.path.join(str(get_user_data_path()), NOMBRE_FICHERO)


def configurar_registro(nivel=logging.INFO):
    """Prepara el logger ``reyger``. Es idempotente.

    Si el fichero no se puede abrir (disco lleno, permisos), la app sigue
    funcionando y solo registra en la consola.
    """
    if getattr(_log, "_reyger_configurado", False):
        return _log
    _log.setLevel(nivel)
    formato = logging.Formatter(FORMATO)
    try:
        fichero = RotatingFileHandler(
            ruta_registro(), maxBytes=TAMANO_MAXIMO, backupCount=COPIAS,
            encoding="utf-8",
        )
        fichero.setFormatter(formato)
        _log.addHandler(fichero)
    except OSError:
        pass
    if sys.stderr is not None:
        consola = logging.StreamHandler()
        consola.setLevel(logging.WARNING)
        consola.setFormatter(formato)
        _log.addHandler(consola)
    _log._reyger_configurado = True

    def _excepcion_en_hilo(args):
        if issubclass(args.exc_type, SystemExit):
            return
        _log.critical(
            "Excepción no controlada en el hilo %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _excepcion_en_hilo
    return _log
