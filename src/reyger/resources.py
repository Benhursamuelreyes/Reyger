import logging
import os
import shutil
import sys
from pathlib import Path

try:
    from platformdirs import AppDirs
except ImportError:
    AppDirs = None

log = logging.getLogger(__name__)


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
                log.exception("No se pudo copiar la base de datos plantilla %s", bundled)
    return str(path)


def get_config_path():
    return str(get_user_data_path() / "config.json")


def _carpeta_escribible(path):
    """Crea *path* y comprueba que se puede escribir en ella.

    ``os.access`` no es fiable en Windows (ignora las ACL), así que se
    prueba creando un fichero temporal de verdad.
    """
    import tempfile

    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


def get_output_path(subdir):
    """Carpeta donde se guardan los documentos generados (PDF).

    Normalmente ``<datos de usuario>/<subdir>``. Si esa carpeta no admite
    escritura (permisos, antivirus, carpeta sincronizada bloqueada…) se usa
    ``~/Documents/Reyger/<subdir>`` y, en último caso, la carpeta temporal
    del sistema, en vez de fallar con ``Permission denied``.
    """
    import tempfile

    candidatas = (
        get_user_data_path() / subdir,
        Path.home() / "Documents" / "Reyger" / subdir,
        Path(tempfile.gettempdir()) / "Reyger" / subdir,
    )
    for path in candidatas:
        if _carpeta_escribible(path):
            if path != candidatas[0]:
                log.warning("Sin permiso de escritura en %s; se usa %s", candidatas[0], path)
            return str(path)
    raise PermissionError(
        f"No hay ninguna carpeta con permiso de escritura para «{subdir}»"
    )


def ruta_escribible(path):
    """Devuelve *path* o, si está bloqueado, una variante libre a su lado.

    Windows bloquea el PDF mientras está abierto en el visor (Edge, Adobe
    Reader…): reescribirlo al reimprimir la misma factura fallaba con
    ``PermissionError: [Errno 13] Permission denied``. En ese caso se usa
    ``nombre_1.pdf``, ``nombre_2.pdf``…
    """
    base, ext = os.path.splitext(path)
    for n in range(100):
        candidato = path if n == 0 else f"{base}_{n}{ext}"
        if not os.path.exists(candidato):
            return candidato
        try:
            with open(candidato, "r+b"):
                return candidato
        except OSError:
            continue
    raise PermissionError(f"No se puede escribir {path}: el fichero está en uso")


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
