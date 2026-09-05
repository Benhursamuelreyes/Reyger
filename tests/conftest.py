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

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import reyger.core.db as db
from reyger.resources import get_db_path as _get_db_path_pristino

_referencia_original = _get_db_path_pristino


@pytest.fixture(autouse=True)
def _estado_de_datos_saneado():
    db._conexion = None
    db.get_db_path = _referencia_original
    yield
    db._conexion = None
    db.get_db_path = _referencia_original