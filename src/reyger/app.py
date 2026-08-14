import os
import sys
import traceback
from pathlib import Path

from .resources import get_user_data_path


def _ensure_tcl_library():
    """Asegura que el runtime Tcl/Tk encuentre init.tcl / tk.tcl.

    En la app empaquetada, el launcher nativo de Briefcase no fija las
    variables TCL_LIBRARY / TK_LIBRARY. Sin ellas, _tkinter no encuentra
    init.tcl y tkinter falla con un TclError (que, con console=false,
    parece un cierre silencioso en el MSI).

    El bundler (scripts/bundle_tkinter_windows.py) copia los scripts a
    <home>/tcl/tcl8.6 y <home>/tcl/tk8.6; aqui se apunta a ellos como
    red de seguridad en todos los entornos.
    """
    home = Path(__file__).resolve().parents[2]
    for name, sub in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        if os.environ.get(name):
            continue
        for base in (home, home / "Lib"):
            candidate = base / "tcl" / sub
            if not candidate.is_dir():
                candidate = base / sub
            if candidate.is_dir():
                os.environ.setdefault(name, str(candidate))
                break


_ensure_tcl_library()


def _crash_log_path():
    return os.path.join(str(get_user_data_path()), "crash.log")


def _write_crash(exc_type, exc_value, exc_tb):
    try:
        with open(_crash_log_path(), "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    except Exception:
        pass


def _show_native_error(message):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Reyger - Error", 0x10)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            import subprocess
            subprocess.Popen(
                ["osascript", "-e", f'display alert "Reyger - Error" message "{message}"']
            )
        except Exception:
            pass


def _install_crash_handler():
    def handler(exc_type, exc_value, exc_tb):
        _write_crash(exc_type, exc_value, exc_tb)
        try:
            _show_native_error(f"Ocurrió un error inesperado.\n\n{exc_value}\n\nDetalle guardado en crash.log")
        except Exception:
            pass
        if sys.__excepthook__ is not None:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handler


def main():
    _install_crash_handler()
    from .manager import Manager

    app = Manager()
    app.mainloop()


if __name__ == "__main__":
    main()
