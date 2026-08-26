"""Tests del auto-updater de GitHub."""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── _parsear_version ──────────────────────────────────────────────

def test_parsear_version_basica():
    """_parsear_version maneja versiones simples (final)."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.0") == (3, 0, 0, 3, 0)
    assert _parsear_version("v3.0.0") == (3, 0, 0, 3, 0)
    assert _parsear_version("2.1.5") == (2, 1, 5, 3, 0)


def test_parsear_version_beta_pep440():
    """_parsear_version maneja formato PEP 440 (b3, rc1, a1)."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.0b3") == (3, 0, 0, 1, 3)
    assert _parsear_version("3.0.0rc1") == (3, 0, 0, 2, 1)
    assert _parsear_version("3.0.0a1") == (3, 0, 0, 0, 1)


def test_parsear_version_beta_github():
    """_parsear_version maneja formato GitHub (v3.0.0-beta.3)."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("v3.0.0-beta.3") == (3, 0, 0, 1, 3)
    assert _parsear_version("v3.1.0-beta.1") == (3, 1, 0, 1, 1)
    assert _parsear_version("v2.0.0-rc.1") == (2, 0, 0, 2, 1)


def test_parsear_version_comparacion():
    """Comparaciones de versiones numéricas."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.1") > _parsear_version("3.0.0")
    assert _parsear_version("4.0.0") > _parsear_version("3.9.9")
    assert _parsear_version("3.0.0") == _parsear_version("3.0.0")
    assert not (_parsear_version("2.0.0") > _parsear_version("3.0.0"))


def test_parsear_version_beta_ordena():
    """Pre-releases se comparan correctamente entre sí."""
    from reyger.core.updater import _parsear_version

    # b4 > b3
    assert _parsear_version("3.0.0b4") > _parsear_version("3.0.0b3")
    # rc1 > b4 (rc está después de beta en ciclo de desarrollo)
    assert _parsear_version("3.0.0rc1") > _parsear_version("3.0.0b4")
    # rc2 > rc1
    assert _parsear_version("3.0.0rc2") > _parsear_version("3.0.0rc1")
    # GitHub format igual a PEP 440
    assert _parsear_version("v3.0.0-beta.3") == _parsear_version("3.0.0b3")


def test_parsear_version_final_vs_beta():
    """Una versión final es mayor que cualquier pre-release del mismo número."""
    from reyger.core.updater import _parsear_version

    # 3.0.0 (final) > 3.0.0b3 (beta)
    assert _parsear_version("3.0.0") > _parsear_version("3.0.0b3")
    assert _parsear_version("3.0.0") > _parsear_version("3.0.0rc1")
    # 3.0.1 (final) > 3.0.0b3
    assert _parsear_version("3.0.1") > _parsear_version("3.0.0b3")


def test_parsear_version_igual_mismo_formato():
    """Misma versión en formatos diferentes son iguales."""
    from reyger.core.updater import _parsear_version

    assert _parsear_version("3.0.0b3") == _parsear_version("v3.0.0-beta.3")
    assert _parsear_version("3.0.0rc1") == _parsear_version("v3.0.0-rc.1")
    assert _parsear_version("3.0.0a1") == _parsear_version("v3.0.0-alpha.1")


# ── _nombre_binario_sistema ──────────────────────────────────────

def test_nombre_binario_sistema():
    """_nombre_binario_sistema devuelve la extensión correcta."""
    from reyger.core.updater import _nombre_binario_sistema

    resultado = _nombre_binario_sistema()
    if resultado is not None:
        assert isinstance(resultado, str)
        assert resultado.startswith(".")


# ── texto_actualizacion ──────────────────────────────────────────

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


def test_texto_actualizacion_sin_assets():
    """texto_actualizacion funciona sin assets."""
    from reyger.core.updater import texto_actualizacion

    info = {
        "tag_name": "v3.1.0",
        "name": "Reyger v3.1.0",
        "html_url": "https://example.com",
        "assets": [],
    }
    texto = texto_actualizacion(info)
    assert "v3.1.0" in texto
    assert "Descarga manual" in texto


# ── obtener_version_github ───────────────────────────────────────

def test_obtener_version_github_red():
    """obtener_version_github retorna None si no hay conexión (o un dict si la hay)."""
    from reyger.core.updater import obtener_version_github

    resultado = obtener_version_github()
    if resultado is not None:
        assert "tag_name" in resultado
        assert "assets" in resultado


# ── hay_actualizacion (con mocks) ────────────────────────────────

def _mock_release(tag_name, assets=None):
    """Crea un dict simulando la respuesta de GitHub API."""
    return {
        "tag_name": tag_name,
        "name": tag_name,
        "html_url": f"https://github.com/Benhursamuelreyes/Reyger/releases/tag/{tag_name}",
        "assets": assets or [],
    }


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_version_mayor(mock_api):
    """Devuelve release si la versión remota es mayor."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.1.0")
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is not None
    assert resultado["tag_name"] == "v3.1.0"


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_misma_version(mock_api):
    """Devuelve None si la versión es la misma."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.0.0-beta.3")
    resultado = hay_actualizacion(actual="3.0.0b3")
    assert resultado is None


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_local_mas_nueva(mock_api):
    """Devuelve None si la versión local es más nueva que la remota."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.0.0-beta.3")
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is None


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_beta_vs_final(mock_api):
    """Una versión final remota supera a una beta local."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.0.0")
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is not None


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_final_supera_beta(mock_api):
    """Una versión final 3.1.0 supera a una beta 3.0.0b4."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.1.0")
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is not None


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_api_falla(mock_api):
    """Devuelve None si la API falla."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = None
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is None


@patch("reyger.core.updater.obtener_version_github")
def test_hay_actualizacion_rc_supera_beta(mock_api):
    """Un rc remoto supera a una beta local del mismo número."""
    from reyger.core.updater import hay_actualizacion

    mock_api.return_value = _mock_release("v3.0.0-rc.1")
    resultado = hay_actualizacion(actual="3.0.0b4")
    assert resultado is not None


# ── descargar_release (con mocks) ────────────────────────────────

@patch("reyger.core.updater._nombre_binario_sistema")
@patch("reyger.core.updater.urllib.request.urlopen")
def test_descargar_release_exitoso(mock_urlopen, mock_nombre):
    """Descarga exitosa del binario correcto."""
    from reyger.core.updater import descargar_release

    mock_nombre.return_value = ".AppImage"
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"fake_binary_data"
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    info = _mock_release("v3.1.0", assets=[
        {"name": "Reyger-3.1.0-x86_64.AppImage", "browser_download_url": "https://example.com/app.AppImage", "size": 1000},
        {"name": "Reyger-3.1.0.msi", "browser_download_url": "https://example.com/app.msi", "size": 2000},
    ])

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".AppImage", delete=False) as f:
        ruta = f.name

    try:
        resultado = descargar_release(info, ruta)
        assert resultado == ruta
        with open(ruta, "rb") as f:
            assert f.read() == b"fake_binary_data"
    finally:
        os.unlink(ruta)


@patch("reyger.core.updater._nombre_binario_sistema")
def test_descargar_release_sin_asset_compat(mock_nombre):
    """Devuelve None si no hay asset compatible."""
    from reyger.core.updater import descargar_release

    mock_nombre.return_value = ".AppImage"
    info = _mock_release("v3.1.0", assets=[
        {"name": "Reyger-3.1.0.msi", "browser_download_url": "https://example.com/app.msi", "size": 2000},
    ])

    resultado = descargar_release(info, "/tmp/fake_dest")
    assert resultado is None


@patch("reyger.core.updater._nombre_binario_sistema")
def test_descargar_release_sin_assets(mock_nombre):
    """Devuelve None si la release no tiene assets."""
    from reyger.core.updater import descargar_release

    mock_nombre.return_value = ".AppImage"
    info = _mock_release("v3.1.0", assets=[])

    resultado = descargar_release(info, "/tmp/fake_dest")
    assert resultado is None


@patch("reyger.core.updater._nombre_binario_sistema")
def test_descargar_release_plataforma_desconocida(mock_nombre):
    """Devuelve None si la plataforma no es reconocida."""
    from reyger.core.updater import descargar_release

    mock_nombre.return_value = None
    info = _mock_release("v3.1.0")

    resultado = descargar_release(info, "/tmp/fake_dest")
    assert resultado is None
