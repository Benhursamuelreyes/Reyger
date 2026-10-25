"""Configuración de pytest para la suite de Reyger.

Sanea el estado global de la capa de datos antes y después de cada
prueba: restaura ``get_db_path`` a su valor original y descarta la
conexión compartida.  Varios tests antiguos redirigen la base de datos
hacia directorios temporales que borran en su ``finally`` sin restaurar
la ruta, lo que hacía fallar de forma dependiente del orden a los tests
que se ejecutan después.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

# Carpeta de datos aislada para toda la sesión. Sin esto los tests escribían
# en la del usuario real (config.json, reyger.key...): un desarrollador que
# ejecutara la suite se encontraba su configuración cambiada a «Test SL».
# Se sustituye ``get_user_data_path`` antes de que ningún módulo de la app
# la importe por nombre (``config``, ``seguridad``, ``registro``...).
DATOS_TESTS = Path(tempfile.mkdtemp(prefix="reyger_tests_")) / "Reyger"
DATOS_TESTS.mkdir(parents=True)

import reyger.resources as _resources  # noqa: E402


def _datos_de_tests():
    DATOS_TESTS.mkdir(parents=True, exist_ok=True)
    return DATOS_TESTS


_resources.get_user_data_path = _datos_de_tests

import reyger.core.db as db  # noqa: E402
from reyger.resources import get_db_path as _get_db_path_pristino  # noqa: E402

_referencia_original = _get_db_path_pristino


@pytest.fixture(autouse=True)
def _configuracion_por_defecto():
    """Cada test arranca con la configuración por defecto (sin config.json).

    Varios tests guardan ajustes (letra del ticket, nombre de empresa...) y
    los siguientes los heredaban, de modo que el resultado dependía del
    orden de ejecución.
    """
    (DATOS_TESTS / "config.json").unlink(missing_ok=True)
    yield


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Hace fallar el test si alguno de sus ``chequear()`` falló.

    Los tests antiguos (``test_fase*``, ``test_backup``...) registran las
    comprobaciones fallidas en la lista ``FALLOS`` del módulo y solo la
    revisan en su ``main()``. Bajo pytest nadie la miraba, así que una
    comprobación fallida no hacía fallar el test.
    """
    fallos = getattr(item.module, "FALLOS", None)
    inicio = len(fallos) if isinstance(fallos, list) else None
    resultado = yield
    if inicio is not None and len(fallos) > inicio:
        raise AssertionError(
            "Comprobaciones fallidas: " + "; ".join(map(str, fallos[inicio:]))
        )
    return resultado


#: Módulos cuyos ``messagebox`` sustituyen los ``silenciar_messageboxes()``.
_MODULOS_CON_DIALOGOS = (
    "reyger.container",
    "reyger.ui.clientes",
    "reyger.ui.inventario",
    "reyger.ui.ventas",
)


@pytest.fixture(autouse=True)
def _dialogos_silenciados(request):
    """Aplica el ``silenciar_messageboxes()`` del módulo y lo deshace al final.

    Esos tests solo lo llamaban en su ``main()``: bajo pytest abrían
    diálogos reales que bloqueaban el test hasta cerrarlos a mano, salvo que
    otro test anterior hubiera dejado ``messagebox`` sustituido (sin
    restaurarlo) para todos los que venían detrás.
    """
    silenciar = getattr(request.module, "silenciar_messageboxes", None)
    if silenciar is None:
        yield
        return
    import importlib

    ausente = object()
    modulos = [importlib.import_module(nombre) for nombre in _MODULOS_CON_DIALOGOS]
    originales = {modulo: getattr(modulo, "messagebox", ausente) for modulo in modulos}
    silenciar()
    yield
    for modulo, original in originales.items():
        if original is ausente:
            modulo.__dict__.pop("messagebox", None)
        else:
            modulo.messagebox = original


@pytest.fixture(autouse=True)
def _estado_de_datos_saneado():
    db._conexion = None
    db.get_db_path = _referencia_original
    yield
    db._conexion = None
    db.get_db_path = _referencia_original