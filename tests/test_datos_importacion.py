#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests de importación/exportación granular (clientes y productos).

Cubren la solicitud de la cliente: gestión por tablas independientes,
estrategias de duplicados (actualizar/ignorar), validación previa sin
toques a la base y plantillas de ejemplo.

Ejecuta:  python -m pytest tests/test_datos_importacion.py -q
"""

import os
import sqlite3

import pytest

from reyger.core import datos
from reyger.core.backup import BackupError


def crear_bd(ruta):
    conn = sqlite3.connect(ruta)
    conn.executescript(
        """
        CREATE TABLE inventario (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            proveedor TEXT NOT NULL,
            precio REAL NOT NULL,
            costo REAL NOT NULL,
            stock INTEGER NOT NULL,
            proveedor_id INTEGER,
            tipo_iva REAL NOT NULL DEFAULT 21.0,
            categoria_id INTEGER,
            codigo_barras TEXT,
            margen_porcentaje REAL
        );
        CREATE UNIQUE INDEX idx_inv_sku ON inventario(codigo_barras);
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            tipo_documento TEXT NOT NULL DEFAULT 'NIF',
            documento TEXT,
            direccion TEXT, codigo_postal TEXT, provincia TEXT,
            telefono TEXT, email TEXT, notas TEXT
        );
        CREATE TABLE proveedores (id INTEGER PRIMARY KEY, nombre TEXT);
        CREATE TABLE categorias (id INTEGER PRIMARY KEY, nombre TEXT);
        """
    )
    conn.execute(
        "INSERT INTO inventario (nombre, proveedor, precio, costo, stock, "
        "tipo_iva, codigo_barras, margen_porcentaje) "
        "VALUES ('Manzana', 'Frutería', 0.85, 0.40, 100, 21.0, '111111', 12)"
    )
    conn.execute(
        "INSERT INTO clientes (nombre, tipo_documento, documento, email) "
        "VALUES ('Ana', 'NIF', '11111111A', 'ana@x.es')"
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


@pytest.fixture
def bd(tmp_path):
    return crear_bd(str(tmp_path / "database.sqlite"))


def hacer_xlsx(tmp_path, nombre, cabecera, filas, hoja="Datos"):
    pytest.importorskip("openpyxl")
    import openpyxl

    libro = openpyxl.Workbook(write_only=False)
    libro.remove(libro.active)
    ws = libro.create_sheet(hoja)
    ws.append(cabecera)
    for fila in filas:
        ws.append(fila)
    ruta = os.path.join(str(tmp_path), nombre)
    libro.save(ruta)
    libro.close()
    return ruta


def hacer_csv(tmp_path, nombre, cabecera, filas):
    import csv

    ruta = os.path.join(str(tmp_path), nombre)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        for fila in filas:
            w.writerow(fila)
    return ruta


CAB_PRODUCTO = ["Código", "Nombre", "Precio Coste", "Precio Venta",
                "Stock", "IVA", "Proveedor", "Categoría", "Margen %"]
CAB_CLIENTE = ["Nombre", "NIF/CIF", "Teléfono", "Email", "Dirección",
               "Código Postal", "Provincia", "Notas"]


def test_importar_productos_inserta_y_actualiza(tmp_path, bd):
    ruta = hacer_xlsx(
        tmp_path, "p.xlsx", CAB_PRODUCTO,
        [
            ["222222", "Pera", 0.50, 0.90, 40, 10, "Frutería", "General", ""],
            ["111111", "Manzana Golden", 0.45, 0.95, 120, 21, "Frutería", "General", 10],
        ],
    )
    resultado = datos.importar_productos(ruta, modo="actualizar", db_path=bd)
    assert resultado["insertados"] == 1
    assert resultado["actualizados"] == 1
    assert resultado["ignorados"] == 0
    assert consulta(bd, "SELECT COUNT(*) FROM inventario") == [(2,)]
    assert consulta(
        bd, "SELECT nombre, precio FROM inventario WHERE codigo_barras='111111'"
    ) == [("Manzana Golden", 0.95)]


def test_importar_productos_ignora_duplicados(tmp_path, bd):
    ruta = hacer_csv(
        tmp_path, "p.csv", ["SKU", "Nombre", "Precio Coste", "Precio de Venta",
                            "Stock", "IVA"],
        [["111111", "Manzana CAMBIADA", 9.9, 9.9, 9, "21"],
         ["222222", "Pera", 0.5, 0.9, 40, "10"]],
    )
    resultado = datos.importar_productos(ruta, modo="ignorar", db_path=bd)
    assert (resultado["insertados"], resultado["actualizados"],
            resultado["ignorados"]) == (1, 0, 1)
    assert consulta(bd, "SELECT nombre, precio FROM inventario "
                        "WHERE codigo_barras='111111'") == [("Manzana", 0.85)]
    assert consulta(bd, "SELECT COUNT(*) FROM inventario") == [(2,)]


def test_importar_clientes_por_nif_actualiza(tmp_path, bd):
    ruta = hacer_xlsx(
        tmp_path, "c.xlsx", ["Nombre/Razón Social", "NIF/CIF", "Teléfono",
                             "Email", "Dirección"],
        [["Ana García", "11111111A", "600111222", "ana@nuevo.es", "C/ Sol"],
         ["Beto", "22222222B", None, "beto@x.es", None]],
    )
    resultado = datos.importar_clientes(ruta, modo="actualizar", db_path=bd)
    assert (resultado["insertados"], resultado["actualizados"],
            resultado["ignorados"]) == (1, 1, 0)
    assert consulta(bd, "SELECT nombre, email, telefono FROM clientes "
                        "WHERE documento='11111111A'") == [
        ("Ana García", "ana@nuevo.es", "600111222")]


def test_importar_clientes_ignora_duplicados(tmp_path, bd):
    ruta = hacer_csv(
        tmp_path, "c.csv", ["Nombre", "NIF/CIF"],
        [["Ana CAMBIADA", "11111111A"], ["Beto", "22222222B"]],
    )
    resultado = datos.importar_clientes(ruta, modo="ignorar", db_path=bd)
    assert (resultado["insertados"], resultado["actualizados"],
            resultado["ignorados"]) == (1, 0, 1)
    assert consulta(bd, "SELECT nombre FROM clientes "
                        "WHERE documento='11111111A'") == [("Ana",)]


def test_filas_con_error_no_modifican_nada(tmp_path, bd):
    ruta = hacer_xlsx(
        tmp_path, "mal.xlsx", CAB_PRODUCTO,
        [["", "Sin código", 1.0, 2.0, 5, "21"],
         ["999", "Malo IVA", 1.0, 2.0, 5, "33"],
         ["888", "Válido", 1.0, 2.0, 5, "21"]],
    )
    with pytest.raises(BackupError, match="no se importó nada"):
        datos.importar_productos(ruta, modo="actualizar", db_path=bd)
    assert consulta(bd, "SELECT COUNT(*) FROM inventario") == [(1,)]


def test_faltan_columnas_obligatorias(tmp_path, bd):
    ruta = hacer_csv(tmp_path, "p.csv", ["Código", "Nombre"],
                     [["10", "X"]])
    with pytest.raises(BackupError, match="Precio Coste"):
        datos.importar_productos(ruta, db_path=bd)


def test_existe_respaldo_automatico_previo(tmp_path, bd):
    ruta = hacer_csv(tmp_path, "p.csv", ["Código", "Nombre", "Precio Coste",
                                         "Precio Venta", "Stock", "IVA"],
                     [["222", "Kiwi", 1, 2, 3, "21"]])
    resultado = datos.importar_productos(ruta, db_path=bd)
    assert resultado["respaldo"] and os.path.exists(resultado["respaldo"])


def test_plantillas_generan_cabecera_esperada(tmp_path):
    pytest.importorskip("openpyxl")
    ruta = str(tmp_path / "plantilla_productos.xlsx")
    datos.plantilla_productos(ruta)
    from openpyxl import load_workbook

    libro = load_workbook(ruta, read_only=True)
    cabecera = [c.value for c in next(libro.active.iter_rows())]
    libro.close()
    assert cabecera == [etiqueta for _, etiqueta in datos.CAMPOS_PRODUCTO]


def test_exportar_e_importar_round_trip(tmp_path, bd):
    pytest.importorskip("openpyxl")
    salida = str(tmp_path / "clientes.xlsx")
    datos.exportar_clientes(salida, db_path=bd)
    nueva = str(tmp_path / "nueva.sqlite")
    crear_bd(nueva)
    resultado = datos.importar_clientes(salida, modo="actualizar", db_path=nueva)
    assert resultado["actualizados"] == 1
    assert consulta(nueva, "SELECT nombre FROM clientes") == [("Ana",)]


def test_exportar_productos_csv_reordena_por_nombre(tmp_path, bd):
    salida = str(tmp_path / "productos.csv")
    datos.exportar_productos(salida, db_path=bd)
    with open(salida, encoding="utf-8-sig") as f:
        contenido = f.read()
    assert contenido.splitlines()[0].startswith("Código,Nombre,Precio Coste")
    assert "Manzana" in contenido
    assert "111111" in contenido


def test_importar_productos_con_encabezados_en_desorden(tmp_path, bd):
    ruta = hacer_csv(
        tmp_path, "p.csv",
        ["Stock", "IVA", "Precio Venta", "Nombre", "Precio Coste", "Código"],
        [["15", "21", "1.25", "Fresa", "0.60", "333333"]],
    )
    resultado = datos.importar_productos(ruta, db_path=bd)
    assert resultado["insertados"] == 1
    assert consulta(bd, "SELECT nombre, stock, precio FROM inventario "
                        "WHERE codigo_barras='333333'") == [("Fresa", 15, 1.25)]