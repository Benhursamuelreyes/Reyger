"""Auto-Updater de GitHub para Reyger.

Consulta las releases de GitHub para detectar nuevas versiones y
facilita la descarga del binario actualizado.

No requiere dependencias externas: usa ``urllib`` de la stdlib
y ``json`` para parsear la API de GitHub.

El repositorio es ``Benhursamuelreyes/Reyger``.
"""

import json
import os
import platform
import re
import sys
import urllib.request
import urllib.error
from typing import Optional

from .. import __version__

REPO_GITHUB = "Benhursamuelreyes/Reyger"
API_URL = f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest"
TIMEOUT = 10


def _es_frozen() -> bool:
    """Indica si la app está empaquetada (Briefcase/PyInstaller)."""
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


def obtener_version_github() -> Optional[dict]:
    """Consulta la última release de GitHub.

    Devuelve un diccionario con ``tag_name``, ``name``,
    ``html_url`` y ``assets`` (lista de dicts con ``name`` y
    ``browser_download_url``), o ``None`` si no se pudo conectar.
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        return {
            "tag_name": datos.get("tag_name", ""),
            "name": datos.get("name", ""),
            "html_url": datos.get("html_url", ""),
            "assets": [
                {
                    "name": a.get("name", ""),
                    "browser_download_url": a.get("browser_download_url", ""),
                    "size": a.get("size", 0),
                }
                for a in datos.get("assets", [])
            ],
        }
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        return None


_PRE_TIPO = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2}


def _parsear_version(version_str: str) -> tuple:
    """Convierte ``'3.0.0b3'``, ``'v3.0.0-beta.3'`` o ``'v3.0.0'`` a tupla comparable.

    Devuelve una tupla ``(major, minor, patch, tipo_pre, num)`` donde
    tipo_pre es: 0=alpha, 1=beta, 2=rc, 3=final.

    ``3.0.0b3`` → ``(3, 0, 0, 1, 3)``
    ``v3.0.0-beta.3`` → ``(3, 0, 0, 1, 3)``
    ``3.0.0rc1`` → ``(3, 0, 0, 2, 1)``
    ``3.0.0`` (final) → ``(3, 0, 0, 3, 0)``
    """
    v = version_str.lstrip("v")
    m = re.search(r"(a|alpha|b|beta|rc)[\.\-]?(\d+)", v, re.IGNORECASE)
    if m:
        tipo = _PRE_TIPO.get(m.group(1).lower(), 3)
        num_pre = int(m.group(2))
    else:
        tipo = 3
        num_pre = 0
    num = re.split(r"[\-](?:alpha|beta|rc)", v, flags=re.IGNORECASE)[0]
    num = re.split(r"(?:a(?:lpha)?|b(?:eta)?|rc)\d", num, flags=re.IGNORECASE)[0]
    num = num.rstrip(".")
    partes = tuple(int(p) for p in num.split(".") if p.isdigit())
    return partes + (tipo, num_pre)


def hay_actualizacion(actual: Optional[str] = None) -> Optional[dict]:
    """Verifica si hay una versión más reciente en GitHub.

    Devuelve el diccionario de la release si hay actualización,
    o ``None`` si ya se tiene la última versión o no se pudo conectar.
    """
    actual = actual or __version__
    info = obtener_version_github()
    if info is None:
        return None

    v_actual = _parsear_version(actual)
    v_remota = _parsear_version(info["tag_name"])

    if v_remota > v_actual:
        return info
    return None


def _nombre_binario_sistema() -> Optional[str]:
    """Devuelve el patrón de nombre del binario para la plataforma actual."""
    sistema = platform.system().lower()
    if sistema == "linux":
        return ".AppImage"
    if sistema == "windows":
        return ".msi"
    if sistema == "darwin":
        return ".dmg"
    return None


def descargar_release(info_release: dict, ruta_destino: str) -> Optional[str]:
    """Descarga el binario de la release para la plataforma actual.

    Devuelve la ruta del fichero descargado, o ``None`` si no se
    encontró un binario compatible.
    """
    patron = _nombre_binario_sistema()
    if patron is None:
        return None

    for asset in info_release.get("assets", []):
        nombre = asset.get("name", "")
        if patron.lower() in nombre.lower():
            url = asset["browser_download_url"]
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                datos = resp.read()
            with open(ruta_destino, "wb") as f:
                f.write(datos)
            return ruta_destino

    return None


def texto_actualizacion(info_release: dict) -> str:
    """Genera un texto legible para el usuario sobre la actualización."""
    nombre = info_release.get("name") or info_release.get("tag_name", "")
    url = info_release.get("html_url", "")
    assets = info_release.get("assets", [])

    lineas = [
        f"Nueva versión disponible: {nombre}",
        "",
    ]
    if assets:
        patron = _nombre_binario_sistema() or ""
        for a in assets:
            if patron.lower() in a["name"].lower():
                size_mb = a.get("size", 0) / (1024 * 1024)
                lineas.append(f"  {a['name']} ({size_mb:.1f} MB)")
    lineas.append("")
    lineas.append(f"Descarga manual: {url}")

    return "\n".join(lineas)
