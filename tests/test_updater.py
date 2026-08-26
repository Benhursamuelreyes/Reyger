"""Tests del auto-updater de GitHub."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_parsear_version_basica():
    """_parsear_version maneja versiones simples."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.0") == (3, 0, 0)
    assert _parsear_version("v3.0.0") == (3, 0, 0)
    assert _parsear_version("2.1.5") == (2, 1, 5)


def test_parsear_version_beta():
    """_parsear_version ignora sufijos beta/rc."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.0b3") == (3, 0, 0)
    assert _parsear_version("3.0.0rc1") == (3, 0, 0)
    assert _parsear_version("3.0.0a1") == (3, 0, 0)


def test_parsear_version_comparacion():
    """Comparaciones de versiones."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.1") > _parsear_version("3.0.0")
    assert _parsear_version("4.0.0") > _parsear_version("3.9.9")
    assert _parsear_version("3.0.0") == _parsear_version("3.0.0")
    assert not (_parsear_version("2.0.0") > _parsear_version("3.0.0"))


def test_nombre_binario_sistema():
    """_nombre_binario_sistema devuelve la extensión correcta."""
    from reyger.core.updater import _nombre_binario_sistema

    resultado = _nombre_binario_sistema()
    # En el entorno de test, puede ser None si la plataforma no es reconocida
    if resultado is not None:
        assert isinstance(resultado, str)
        assert resultado.startswith(".")


def test_texto_actualizacion():
    """texto_actualizacion genera un texto legible."""
    from reyger.core.updater import texto_actualizacion

    info = {
        "tag_name": "v3.1.0",
        "name": "Reyger v3.1.0",
        "html_url": "https://github.com/Benhursamuelreyes/Reyger/releases/tag/v3.1.0",
        "assets": [
            {
                "name": "Reyger-3.1.0-x86_64.AppImage",
                "browser_download_url": "https://example.com/app.AppImage",
                "size": 50_000_000,
            }
        ],
    }
    texto = texto_actualizacion(info)
    assert "v3.1.0" in texto
    assert "Descarga manual" in texto


def test_obtener_version_github_red():
    """obtener_version_github retorna None si no hay conexión (o un dict si la hay)."""
    from reyger.core.updater import obtener_version_github

    resultado = obtener_version_github()
    # En CI puede no haber red; aceptamos ambos resultados
    if resultado is not None:
        assert "tag_name" in resultado
        assert "assets" in resultado
