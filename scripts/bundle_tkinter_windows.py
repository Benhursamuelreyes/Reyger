"""Inyecta tkinter y las bibliotecas Tcl/Tk en el runtime de Python embebido
que Briefcase empaqueta en el instalador MSI de Windows.

Briefcase usa la distribucion *embeddable* de python.org, que NO incluye
tkinter por diseno. Este script copia los archivos de la instalacion de
Python del host de compilacion dentro del bundle de la app:

    Lib/tkinter            -> <home>/Lib/tkinter
    tcl/tcl8.6, tcl/tk8.6  -> <home>/tcl/ y <home>/Lib/
    DLLs/_tkinter.pyd      -> <home>/DLLs/ y <home>/
    DLLs/tcl86t*.dll ...   -> <home>/DLLs/ y <home>/

Donde ``<home>`` es el directorio del bundle que contiene el runtime
embebido (``python312._pth``, ``python312.zip``, ``Lib/``, ``app/``). El
launcher nativo de Briefcase (``Reyger.exe``) usa ``PyConfig`` en modo
aislado e ignora el ``._pth``; construye sys.path a mano con
``<home>``, ``<home>\\Lib``, ``<home>\\DLLs`` y ``<home>\\app``.

Ademas inyecta un ``sitecustomize.py`` en ``<home>`` que define las
variables de entorno ``TCL_LIBRARY`` y ``TK_LIBRARY`` ANTES de que
``tkinter`` se importe (el stub importa ``site`` antes de arrancar la
app). Sin ellas, ``_tkinter`` no encuentra ``init.tcl``/``tk.tcl`` y la
app muere con un TclError en el MSI.

Finalmente verifica con el runtime embebido que ``tkinter`` IMPORTA Y que
se puede crear/actualizar/destruir una ventana ``Tk()`` real, que es
exactamente el punto donde ocurria el fallo. La verificacion usa
``python.exe`` copiado temporalmente del host, porque Briefcase elimina
``python*.exe`` del bundle al terminar ``briefcase create``.

Debe ejecutarse DESPUES de ``briefcase create`` y ANTES de
``briefcase package``, con el mismo Python que ejecuta Briefcase
(que debe poder ``import tkinter``).

Uso:
    python scripts/bundle_tkinter_windows.py [--embed-dir DIR] [--host-prefix DIR] [--no-verify]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SITECUSTOMIZE = """\
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
_TCL = os.path.join(_BASE, "tcl", "tcl8.6")
_TK = os.path.join(_BASE, "tcl", "tk8.6")

os.environ.setdefault("TCL_LIBRARY", _TCL if os.path.isdir(_TCL) else os.path.join(_BASE, "Lib", "tcl8.6"))
os.environ.setdefault("TK_LIBRARY", _TK if os.path.isdir(_TK) else os.path.join(_BASE, "Lib", "tk8.6"))
"""

VERIFY_PROBE = (
    "import sys, tkinter;"
    "r = tkinter.Tk();"
    "r.update();"
    "r.destroy();"
    "print('tkinter OK: Tcl', tkinter.TclVersion, '| Tk', tkinter.TkVersion)"
)


def find_embedded_python(root: Path, embed_dir: str | None = None) -> Path:
    """Localiza el home del runtime embebido dentro del bundle.

    El launcher de Briefcase arranca desde el directorio donde esta
    ``python*._pth`` (que no se elimina al crear el bundle), no desde un
    subdirectorio ``python/`` ni desde ``python.exe`` (que si se borra).
    """
    if embed_dir is not None:
        embed_dir = Path(embed_dir)
        if not (embed_dir / "Lib").exists():
            raise SystemExit(f"{embed_dir} no parece el home del runtime embebido")
        return embed_dir.resolve()

    for pth in root.glob("**/python*._pth"):
        candidate = pth.parent
        if (candidate / "Lib").exists():
            return candidate

    for python_dir in root.glob("**/python"):
        if (python_dir / "pythonw.exe").exists():
            return python_dir

    raise SystemExit(
        "No se encontro el Python embebido de Briefcase "
        f"(buscando '**/python*._pth' bajo {root})."
    )


def require(src: Path) -> Path:
    if not src.exists():
        raise SystemExit(f"Fuente inexistente: {src}")
    return src


def copy_into(src: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / src.name)
    print(f"  {src.name} -> {dst_dir}")


def copy_dir(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"  {src.name}/ -> {dst}")


def find_tcl_tk_scripts(prefix: Path) -> tuple[Path, Path]:
    candidates = (
        prefix / "tcl" / "tcl8.6",
        prefix / "Lib" / "tcl8.6",
    )
    tcl = next((c for c in candidates if c.exists()), None)
    if tcl is None:
        raise SystemExit(
            "No se encontraron los scripts de Tcl/Tk (init.tcl) en "
            f"{prefix}. Usa una instalacion oficial de python.org con "
            "'tcl/tk and IDLE' activada."
        )
    tk_candidates = (
        prefix / "tcl" / "tk8.6",
        prefix / "Lib" / "tk8.6",
        tcl.parent / "tk8.6",
    )
    tk = next((c for c in tk_candidates if c.exists()), None)
    if tk is None:
        raise SystemExit(
            f"Se encontro Tcl en {tcl} pero no tk8.6 al lado; revisa "
            "la instalacion de python.org."
        )
    return tcl, tk


def ensure_ptb_entries(ptb_file: Path) -> None:
    """Garantiza que el ._pth del runtime embebido incluya Lib, DLLs y site.

    El launcher real ignora el ._pth, pero la verificacion de este script
    usa python.exe, que si lo respeta: sin estos cambios la verificacion
    no encontraria tkinter.
    """
    text = ptb_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    active = {l.strip() for l in lines if l.strip() and not l.strip().startswith("#")}

    def present(entry: str) -> bool:
        return any(e in active for e in (entry, ".\\" + entry, "./" + entry))

    additions = []
    for entry in ("Lib", "DLLs"):
        if not present(entry):
            additions.append(f".\\{entry}")

    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("#import site", "# import site"):
            lines[i] = line.replace(stripped, "import site")
            changed = True

    if additions or changed:
        new_lines = lines + ([""] + additions if additions else [])
        ptb_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        if additions:
            print(f"  Anadidos {', '.join(additions)} a {ptb_file.name}")
        if changed:
            print(f"  Habilitado 'import site' en {ptb_file.name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embed-dir", help="Override: home del runtime embebido")
    parser.add_argument("--host-prefix", help="Override: prefix del Python del host")
    parser.add_argument("--no-verify", action="store_true",
                        help="Saltar la verificacion con el runtime embebido")
    args = parser.parse_args(argv)

    try:
        import tkinter  # noqa: F401
    except ImportError:
        raise SystemExit(
            "El Python del host no tiene tkinter; imposible empaquetarlo. "
            "Usa una instalacion oficial de python.org con la opcion "
            "'tcl/tk and IDLE' activada."
        )

    prefix = Path(args.host_prefix or sys.base_prefix)
    embed = find_embedded_python(PROJECT_ROOT / "build", args.embed_dir)
    print(f"Python del host : {prefix}")
    print(f"Runtime embebido: {embed}")

    lib = prefix / "Lib"
    dlls = prefix / "DLLs"
    tcl_scripts, tk_scripts = find_tcl_tk_scripts(prefix)

    dll_files = sorted(dlls.glob("_tkinter.*")) if dlls.exists() else []
    dll_files += (
        sorted(dlls.glob("tcl*t.dll")) + sorted(dlls.glob("tk*t.dll"))
        if dlls.exists() else []
    )
    dll_files += sorted(dlls.glob("zlib1.dll")) if dlls.exists() else []
    if not dll_files:
        raise SystemExit(
            f"No hay DLLs de Tcl/Tk bajo {dlls}; usa una instalacion "
            "oficial de python.org (la 'embeddable' no las incluye)."
        )

    tkinter_pkg = require(lib / "tkinter")

    print("Copiando tkinter y Tcl/Tk al runtime embebido...")
    copy_dir(tkinter_pkg, embed / "Lib" / "tkinter")
    copy_dir(tcl_scripts, embed / "tcl" / "tcl8.6")
    copy_dir(tk_scripts, embed / "tcl" / "tk8.6")
    copy_dir(tcl_scripts, embed / "Lib" / "tcl8.6")
    copy_dir(tk_scripts, embed / "Lib" / "tk8.6")
    for f in dll_files:
        copy_into(f, embed / "DLLs")
        copy_into(f, embed)

    for ptb in embed.glob("python*._pth"):
        ensure_ptb_entries(ptb)

    (embed / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    print(f"  sitecustomize.py -> {embed}")

    if args.no_verify:
        print("Verificacion omitida (--no-verify).")
        return

    python_exe = require(prefix / "python.exe")
    pythonw_exe = require(prefix / "pythonw.exe")
    print("Verificando `import tkinter` + crear ventana Tk() con el runtime embebido...")
    temp_python = embed / "python.exe"
    temp_pythonw = embed / "pythonw.exe"
    result = None
    try:
        shutil.copy2(python_exe, temp_python)
        shutil.copy2(pythonw_exe, temp_pythonw)
        result = subprocess.run(
            [str(temp_python), "-c", VERIFY_PROBE],
            capture_output=True,
            text=True,
            cwd=str(embed),
            timeout=120,
        )
    finally:
        temp_python.unlink(missing_ok=True)
        temp_pythonw.unlink(missing_ok=True)

    if result is None or result.returncode != 0:
        detail = (result.stdout or "") + (result.stderr or "") if result else ""
        raise SystemExit(
            "tkinter falla en el runtime embebido:\n" + detail
        )
    print(f"OK: {result.stdout.strip()}")


if __name__ == "__main__":
    main()
