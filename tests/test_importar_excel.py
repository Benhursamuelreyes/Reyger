#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de robustez de la importación de datos (.xlsx y .zip CSV) en backup.

Cubren el caso real que aparecía como
``No se pudo importar (no se cambió nada): list index out of range``:
 - filas con menos columnas que la cabecera (se tolera, celda -> NULL),
 - columnas extra más allá de la cabecera (se ignoran),
 - columnas en distinto orden (el emparejamiento es por nombre),
 - filas y hojas vacías (se omiten),
 - celdas vacías en columnas NOT NULL (el error es descriptivo y hay
   transacción atómica: no se modifica nada).

Ejecuta:  python -m pytest tests/test_importar_excel.py -q
"""

import os
import sqlite3
import zipfile

import pytest

from reyger.core import backup


def crear_bd(ruta):
    """Base con dos tablas: una NOT NULL y otra con columnas optativas."""
    conn = sqlite3.connect(ruta)
    conn.executescript(
        """
        CREATE TABLE inventario (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL,
            stock INTEGER
        );
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            email TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return ruta


def consulta(ruta, sql):
    conn = sqlite3.connect(ruta)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def hacer_xlsx(tmp_path, nombre, hojas, guardar=True):
    """Hojas = {nombre: [filas...]} -> fichero .xlsx en tmp_path."""
    import openpyxl

    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for hoja, filas in hojas.items():
        ws = libro.create_sheet(hoja)
        for fila in filas:
            ws.append(fila)
    ruta = os.path.join(str(tmp_path), nombre)
    if guardar:
        libro.save(ruta)
    return ruta


def hacer_zip(tmp_path, nombre, csvs):
    """csvs = {tabla: texto_csv} -> fichero .zip en tmp_path."""
    ruta = os.path.join(str(tmp_path), nombre)
    with zipfile.ZipFile(ruta, "w") as zf:
        for tabla, texto in csvs.items():
            zf.writestr(f"{tabla}.csv", texto)
    return ruta


@pytest.fixture
def bd(tmp_path):
    return crear_bd(str(tmp_path / "database.sqlite"))


def test_fila_corta_en_xlsx_se_tolera_con_null(tmp_path, bd):
    pytest.importorskip("openpyxl")
    ruta = hacer_xlsx(
        tmp_path,
        "corto.xlsx",
        {"inventario": [["nombre", "precio", "costo", "stock"],
                        ["Manzana", 0.85]]},
    )
    resultado = backup.importar_datos(ruta, db_path=bd)
    assert resultado["modo"] == "tablas"
    assert resultado["resumen"] == {"inventario": 1}
    assert consulta(bd, "SELECT nombre, precio, costo, stock "
                        "FROM inventario") == [("Manzana", 0.85, None, None)]


def test_columnas_extra_se_ignoran(tmp_path, bd):
    pytest.importorskip("openpyxl")
    ruta = hacer_xlsx(
        tmp_path,
        "extra.xlsx",
        {"inventario": [["nombre", "precio", "costo", "stock", "fantasma"],
                        ["Pera", 0.60, 0.30, 50, "sobra"]]},
    )
    backup.importar_datos(ruta, db_path=bd)
    assert consulta(bd, "SELECT nombre, precio, costo, stock "
                        "FROM inventario") == [("Pera", 0.60, 0.30, 50)]


def test_orden_de_columnas_distinto_importa_igual(tmp_path, bd):
    pytest.importorskip("openpyxl")
    ruta = hacer_xlsx(
        tmp_path,
        "reorden.xlsx",
        {"inventario": [["stock", "precio", "nombre", "costo"],
                        [12, 2.5, "Naranja", 1.1]]},
    )
    backup.importar_datos(ruta, db_path=bd)
    assert consulta(bd, "SELECT nombre, precio, stock, costo "
                        "FROM inventario") == [("Naranja", 2.5, 12, 1.1)]


def test_fila_corta_en_zip_se_tolera(tmp_path, bd):
    ruta = hacer_zip(
        tmp_path,
        "corto.zip",
        {"clientes": "nombre,email\nAna\nBeto,beto@x.es\n"},
    )
    resultado = backup.importar_datos(ruta, db_path=bd)
    assert resultado["resumen"] == {"clientes": 2}
    assert consulta(bd, "SELECT nombre, email FROM clientes ORDER BY id") == [
        ("Ana", None),
        ("Beto", "beto@x.es"),
    ]


def test_filas_y_hojas_vacias_se_omiten(tmp_path, bd):
    pytest.importorskip("openpyxl")
    ruta = hacer_xlsx(
        tmp_path,
        "mixto.xlsx",
        {"vacia": [["", " ", None], [None, None, None]],
         "clientes": [["nombre", "email"], [], ["Eva", None]]},
    )
    resultado = backup.importar_datos(ruta, db_path=bd)
    assert resultado["resumen"] == {"clientes": 1}
    assert consulta(bd, "SELECT nombre, email FROM clientes") == [("Eva", None)]


def test_libro_solo_con_hojas_vacias_se_rechaza(tmp_path, bd):
    pytest.importorskip("openpyxl")
    ruta = hacer_xlsx(tmp_path, "vacio.xlsx", {"vacia": [["  "]]})
    with pytest.raises(backup.BackupError, match="hojas están vacías"):
        backup.importar_datos(ruta, db_path=bd)


def test_celda_vacia_en_not_null_es_error_atomico(tmp_path, bd):
    ruta = hacer_zip(
        tmp_path,
        "notnull.zip",
        {"inventario": "nombre,precio,costo,stock\nUva\nMelon,1.2\n"},
    )
    with pytest.raises(backup.BackupError, match="no se ha modificado nada"):
        backup.importar_datos(ruta, db_path=bd)
    assert consulta(bd, "SELECT COUNT(*) FROM inventario") == [(0,)]