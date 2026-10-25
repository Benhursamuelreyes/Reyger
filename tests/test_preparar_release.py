"""Tests de ``scripts/preparar_release.py`` (ficheros y notas de cada release)."""

import hashlib
import importlib.util
import os

import pytest

RUTA = os.path.join(os.path.dirname(__file__), "..", "scripts", "preparar_release.py")
_spec = importlib.util.spec_from_file_location("preparar_release", RUTA)
preparar_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preparar_release)

CHANGELOG = """Changelog content

## v1.3.0 (2026-11-01)

FEATURE: algo nuevo.

- Detalle.

## v1.2.1 (2026-10-25)

FIX: otra cosa.
"""


@pytest.fixture
def dist(tmp_path):
    raiz = tmp_path / "dist"
    for carpeta, nombre in (
        ("Reyger-Windows", "Reyger-1.3.0.msi"),
        ("Reyger-macOS", "Reyger-1.3.0.dmg"),
        ("Reyger-Linux", "Reyger-1.3.0-x86_64.AppImage"),
    ):
        (raiz / carpeta).mkdir(parents=True)
        (raiz / carpeta / nombre).write_bytes(nombre.encode())
    changelog = tmp_path / "CHANGELOG"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    return raiz, changelog


def test_publica_nombres_de_version_y_fijos(dist, tmp_path):
    raiz, changelog = dist
    salida = tmp_path / "salida"
    publicados = preparar_release.preparar(raiz, "v1.3.0", salida, changelog)
    assert set(publicados) == {
        "Reyger-1.3.0.msi", "Reyger-Windows.msi",
        "Reyger-1.3.0.dmg", "Reyger-macOS.dmg",
        "Reyger-1.3.0-x86_64.AppImage", "Reyger-Linux-x86_64.AppImage",
    }
    assert (salida / "Reyger-Windows.msi").read_bytes() == b"Reyger-1.3.0.msi"


def test_sha256sums_cubre_todos_los_ficheros(dist, tmp_path):
    raiz, changelog = dist
    salida = tmp_path / "salida"
    publicados = preparar_release.preparar(raiz, "v1.3.0", salida, changelog)
    lineas = (salida / "SHA256SUMS.txt").read_text().splitlines()
    assert len(lineas) == len(publicados)
    for linea in lineas:
        huella, nombre = linea.split("  ")
        assert huella == hashlib.sha256((salida / nombre).read_bytes()).hexdigest()


def test_notas_salen_de_la_seccion_del_changelog(dist, tmp_path):
    raiz, changelog = dist
    salida = tmp_path / "salida"
    preparar_release.preparar(raiz, "v1.3.0", salida, changelog)
    notas = (salida / "NOTAS.md").read_text(encoding="utf-8")
    assert notas.startswith("FEATURE: algo nuevo.")
    assert "FIX: otra cosa." not in notas  # solo la sección de esta versión
    assert "releases/download/v1.3.0/Reyger-1.3.0.msi" in notas
    assert "SHA256SUMS.txt" in notas


def test_falla_sin_seccion_en_el_changelog(dist, tmp_path):
    raiz, changelog = dist
    with pytest.raises(SystemExit, match="CHANGELOG no tiene la sección"):
        preparar_release.preparar(raiz, "v9.9.9", tmp_path / "salida", changelog)


def test_falla_si_el_instalador_es_de_otra_version(dist, tmp_path):
    raiz, changelog = dist
    (raiz / "Reyger-macOS" / "Reyger-1.3.0.dmg").rename(raiz / "Reyger-macOS" / "Reyger-1.2.1.dmg")
    with pytest.raises(SystemExit, match="no corresponde a la versión"):
        preparar_release.preparar(raiz, "v1.3.0", tmp_path / "salida", changelog)


def test_falla_si_falta_un_instalador(dist, tmp_path):
    raiz, changelog = dist
    (raiz / "Reyger-Linux" / "Reyger-1.3.0-x86_64.AppImage").unlink()
    with pytest.raises(SystemExit, match="se esperaba un instalador"):
        preparar_release.preparar(raiz, "v1.3.0", tmp_path / "salida", changelog)


def test_el_changelog_real_tiene_la_version_actual():
    """La versión de pyproject.toml tiene su sección en CHANGELOG (si no, la
    release fallaría al publicarse)."""
    import re

    raiz = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(raiz, "pyproject.toml"), encoding="utf-8") as f:
        version = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)
    with open(os.path.join(raiz, "CHANGELOG"), encoding="utf-8") as f:
        assert preparar_release.seccion_changelog(f.read(), version)
