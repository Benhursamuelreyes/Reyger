import os
import shutil
import sys
from pathlib import Path

try:
    from platformdirs import AppDirs
except ImportError:
    AppDirs = None


def _get_dirs():
    if AppDirs is not None:
        return AppDirs("Reyger", "Reyger")
    return None


def get_user_data_path():
    dirs = _get_dirs()
    if dirs:
        path = Path(dirs.user_data_dir)
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Reyger"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Reyger"
    else:
        path = Path.home() / ".local" / "share" / "Reyger"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path():
    """Devuelve la ruta de la base de datos del usuario.

    Si no existe todavía (primer arranque), copia la base incluida con la
    aplicación (que ya trae las tablas) como plantilla, en vez de depender
    de que cada módulo cree sus tablas en runtime.
    """
    path = get_user_data_path() / "database.db"
    if not path.exists():
        bundled = Path(__file__).parent / "assets" / "database.db"
        if bundled.exists():
            try:
                shutil.copyfile(bundled, path)
            except Exception:
                pass
    return str(path)


def get_config_path():
    return str(get_user_data_path() / "config.json")


def get_output_path(subdir):
    path = get_user_data_path() / subdir
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_bundled_path(relative_path):
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return str(base / relative_path)


def open_file(path):
    if sys.platform == "darwin":
        import subprocess
        subprocess.Popen(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        import subprocess
        subprocess.Popen(["xdg-open", path])
