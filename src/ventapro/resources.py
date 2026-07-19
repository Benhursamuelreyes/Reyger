import os
import sys
from pathlib import Path

try:
    from platformdirs import AppDirs
except ImportError:
    AppDirs = None


def _get_dirs():
    if AppDirs is not None:
        return AppDirs("VentaPRO", "VentaPRO")
    return None


def get_user_data_path():
    dirs = _get_dirs()
    if dirs:
        path = Path(dirs.user_data_dir)
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "VentaPRO"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "VentaPRO"
    else:
        path = Path.home() / ".local" / "share" / "VentaPRO"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path():
    return str(get_user_data_path() / "database.db")


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
