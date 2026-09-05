"""Tests del gestor de impresoras multiplataforma (Fase 3).

Cubre el listado e impresión vía CUPS (Linux/macOS) forzando la
plataforma y simulando ``lpstat``/``lp``, incluidos los casos de
ausencia de herramientas CUPS.
"""

import os
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from reyger.hardware import impresoras


def resultado(returncode=0, stdout=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_cups_lista_impresoras_y_predeterminada():
    with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
         mock.patch.object(impresoras.shutil, "which",
                           return_value="/usr/bin/lpstat"), \
         mock.patch.object(impresoras.subprocess, "run") as run:
        def efecto(comando, **kwargs):
            if comando == ["lpstat", "-e"]:
                return resultado(stdout="HP_LaserJet\nRecep_Mini\n")
            if comando == ["lpstat", "-d"]:
                return resultado(stdout="system default destination: HP_LaserJet")
            raise AssertionError(f"comando inesperado: {comando}")

        run.side_effect = efecto

        gestor = impresoras.GestorImpresoras()
        impresoras_lista = gestor.obtener_impresoras_disponibles()

    assert impresoras_lista == ["HP_LaserJet", "Recep_Mini"]
    assert gestor.impresora_predeterminada == "HP_LaserJet"


def test_cups_sin_impresora_predeterminada():
    with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
         mock.patch.object(impresoras.shutil, "which",
                           return_value="/usr/bin/lpstat"), \
         mock.patch.object(impresoras.subprocess, "run") as run:
        def efecto(comando, **kwargs):
            if comando == ["lpstat", "-e"]:
                return resultado(stdout="")
            if comando == ["lpstat", "-d"]:
                return resultado(returncode=1, stdout="")
            raise AssertionError(f"comando inesperado: {comando}")

        run.side_effect = efecto

        gestor = impresoras.GestorImpresoras()
        impresoras_lista = gestor.obtener_impresoras_disponibles()

    assert impresoras_lista == []
    assert gestor.impresora_predeterminada is None


def test_cups_sin_lpstat_no_falla():
    with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
         mock.patch.object(impresoras.shutil, "which", return_value=None):
        gestor = impresoras.GestorImpresoras()
        impresoras_lista = gestor.obtener_impresoras_disponibles()

    assert impresoras_lista == []
    assert gestor.impresora_predeterminada is None


def test_imprime_en_cups_con_impresora():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "doc.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("documento de prueba")

        with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
             mock.patch.object(impresoras.shutil, "which",
                               return_value="/usr/bin/lp"), \
             mock.patch.object(impresoras.subprocess, "run",
                               return_value=resultado()) as run:
            gestor = impresoras.GestorImpresoras()
            ok = gestor.imprimir_archivo(ruta, nombre_impresora="HP_LaserJet")

    assert ok is True
    assert run.call_args.args[0] == ["lp", "-d", "HP_LaserJet", ruta]


def test_imprime_en_cups_con_archivo_inexistente():
    gestor = impresoras.GestorImpresoras()
    assert gestor.imprimir_archivo("/no/existe.txt", "HP_LaserJet") is False


def test_imprime_en_cups_fallido():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "doc.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("documento de prueba")

        with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
             mock.patch.object(impresoras.shutil, "which",
                               return_value="/usr/bin/lp"), \
             mock.patch.object(impresoras.subprocess, "run",
                               return_value=resultado(returncode=1)):
            gestor = impresoras.GestorImpresoras()
            ok = gestor.imprimir_archivo(ruta, nombre_impresora="HP_LaserJet")

    assert ok is False


def test_imprime_en_cups_sin_lp():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "doc.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("documento de prueba")

        with mock.patch.object(impresoras, "SISTEMA", "Linux"), \
             mock.patch.object(impresoras.shutil, "which", return_value=None):
            gestor = impresoras.GestorImpresoras()
            ok = gestor.imprimir_archivo(ruta, nombre_impresora="HP_LaserJet")

    assert ok is False