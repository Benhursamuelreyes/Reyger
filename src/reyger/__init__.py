"""Reyger — Sistema de ventas."""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("reyger")
except Exception:
    __version__ = "3.0.0b9"
