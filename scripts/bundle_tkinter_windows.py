"""Inyecta tkinter y las bibliotecas Tcl/Tk en el runtime de Python embebido
que Briefcase empaqueta en el instalador MSI de Windows.

Briefcase usa la distribucion *embeddable* de python.org, que NO incluye
tkinter por diseno. Este script copia los archivos de la instalacion de
Python del host de compilacion dentro del Python embebido de la app, de
modo que el MSI resultante sea totalmente autocontenido:

    Lib/tkinter          -> python/Lib/tkinter
    Lib/tcl8.6, Lib/tk8.6 -> python/Lib/
    DLLs/_tkinter.pyd    -> python/DLLs/
    DLLs/tcl86t*.dll ... -> python/DLLs/

Debe ejecutarse DESPUES de ``briefcase create`` y ANTES de
``briefcase package``, con el mismo Python que ejecuta Briefcase
(que debe poder ``import tkinter``).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_embedded_python(root: Path) -> Path:
    for python_dir in root.glob("**/python"):
        if (python_dir / "pythonw.exe").exists():
            return python_dir
    raise SystemExit(
        "No se encontro el Python embebido de Briefcase "
        f"(buscando '**/python/pythonw.exe' bajo {root})."
    )


def require(src: Path) -> Path:
    if not src.exists():
        raise SystemExit(f"Fuente inexistente: {src}")
    return src


def copy_into(src: Path, dst_dir: Path) -> None:
    shutil.copy2(src, dst_dir / src.name)
    print(f"  {src.name} -> {dst_dir}")


def copy_dir(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"  {src.name}/ -> {dst}")


def ensure_ptb_entries(ptb_file: Path) -> None:
    lines = ptb_file.read_text(encoding="utf-8", errors="replace").splitlines()
    active = {l.strip() for l in lines if l.strip() and not l.startswith("#")}

    def present(entry: str) -> bool:
        return any(e in active for e in (entry, ".\\" + entry, "./" + entry))

    missing = [entry for entry in ("Lib", "DLLs") if not present(entry)]
    if not missing:
        return
    with ptb_file.open("a", encoding="utf-8") as fh:
        for entry in missing:
            fh.write(f"\n.\\{entry}")
    print(f"  Anadidos .\\{', .\\'.join(missing)} a {ptb_file.name}")


def main() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        raise SystemExit(
            "El Python del host no tiene tkinter; imposible empaquetarlo. "
            "Usa una instalacion oficial de python.org con la opcion "
            "'tcl/tk and IDLE' activada."
        )

    prefix = Path(sys.base_prefix)
    embed = find_embedded_python(PROJECT_ROOT / "build")
    print(f"Python del host : {prefix}")
    print(f"Python embebido : {embed}")

    lib = prefix / "Lib"
    dlls = prefix / "DLLs"

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
    tcl_dir = require(lib / "tcl8.6")
    tk_dir = require(lib / "tk8.6")

    print("Copiando tkinter y Tcl/Tk al runtime embebido...")
    copy_dir(tkinter_pkg, embed / "Lib" / "tkinter")
    copy_dir(tcl_dir, embed / "Lib" / "tcl8.6")
    copy_dir(tk_dir, embed / "Lib" / "tk8.6")
    (embed / "DLLs").mkdir(exist_ok=True)
    for f in dll_files:
        copy_into(f, embed / "DLLs")

    for ptb in embed.glob("python*._pth"):
        ensure_ptb_entries(ptb)

    print("Verificando `import tkinter` con el runtime embebido...")
    result = subprocess.run(
        [str(embed / "python.exe"), "-c", "import tkinter"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"tkinter no importa en el runtime embebido:\n{result.stderr}"
        )
    print("OK: tkinter quedo incluido en el runtime embebido.")


if __name__ == "__main__":
    main()