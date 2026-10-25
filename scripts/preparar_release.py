#!/usr/bin/env python
"""Prepara los ficheros de una release a partir de los instaladores de CI.

Uso:  python scripts/preparar_release.py <dist> <tag> <salida>

* ``<dist>``: carpeta con los artefactos descargados de los jobs de build
  (``Reyger-Linux/*.AppImage``, ``Reyger-Windows/*.msi``, ``Reyger-macOS/*.dmg``).
* ``<tag>``: etiqueta de la versión, p. ej. ``v1.2.1``.
* ``<salida>``: carpeta donde se dejan los ficheros a publicar.

Genera en ``<salida>``:

* cada instalador con su nombre de versión (``Reyger-1.2.1.msi``) y con un
  nombre **fijo** (``Reyger-Windows.msi``), para que el enlace
  ``…/releases/latest/download/Reyger-Windows.msi`` del README apunte siempre
  a la última versión sin editarlo en cada release;
* ``SHA256SUMS.txt`` con la huella de todos ellos;
* ``NOTAS.md``: la sección de la versión en ``CHANGELOG`` más la tabla de
  descargas. Si el CHANGELOG no tiene la sección, falla: así no se publica
  una versión sin sus notas.
"""

import hashlib
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REPO = "Benhursamuelreyes/Reyger"

#: (carpeta del artefacto, patrón, nombre fijo, plataforma, descripción)
INSTALADORES = (
    ("Reyger-Windows", "*.msi", "Reyger-Windows.msi", "Windows",
     "Instalador para Windows 10/11 (64 bits)"),
    ("Reyger-macOS", "*.dmg", "Reyger-macOS.dmg", "macOS",
     "macOS 11 o superior, Intel y Apple Silicon"),
    ("Reyger-Linux", "*.AppImage", "Reyger-Linux-x86_64.AppImage", "Linux",
     "AppImage portable x86_64 (glibc 2.27+)"),
)


def seccion_changelog(texto, version):
    """Devuelve el cuerpo de ``## v<version> (…)`` en el CHANGELOG."""
    cabecera = f"## v{version} "
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        if linea.startswith(cabecera):
            cuerpo = []
            for siguiente in lineas[i + 1:]:
                if siguiente.startswith("## v"):
                    break
                cuerpo.append(siguiente)
            return "\n".join(cuerpo).strip()
    return None


def sha256(ruta):
    huella = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


def preparar(dist, tag, salida, changelog=RAIZ / "CHANGELOG"):
    dist, salida = Path(dist), Path(salida)
    version = tag[1:] if tag.startswith("v") else tag
    notas = seccion_changelog(Path(changelog).read_text(encoding="utf-8"), version)
    if not notas:
        raise SystemExit(
            f"ERROR: CHANGELOG no tiene la sección «## v{version} (…)». "
            "Añádela en el commit de release antes de etiquetar."
        )

    salida.mkdir(parents=True, exist_ok=True)
    publicados, filas = [], []
    for carpeta, patron, fijo, plataforma, descripcion in INSTALADORES:
        encontrados = sorted((dist / carpeta).glob(patron))
        if len(encontrados) != 1:
            raise SystemExit(
                f"ERROR: se esperaba un instalador {patron} en {dist / carpeta}, "
                f"hay {len(encontrados)}"
            )
        origen = encontrados[0]
        if version not in origen.name:
            raise SystemExit(
                f"ERROR: {origen.name} no corresponde a la versión {version}; "
                "¿falta actualizar pyproject.toml?"
            )
        shutil.copy2(origen, salida / origen.name)
        shutil.copy2(origen, salida / fijo)
        publicados += [origen.name, fijo]
        enlace = f"https://github.com/{REPO}/releases/download/{tag}/{origen.name}"
        filas.append(f"| {plataforma} | [`{origen.name}`]({enlace}) | {descripcion} |")

    sumas = "".join(f"{sha256(salida / nombre)}  {nombre}\n" for nombre in publicados)
    (salida / "SHA256SUMS.txt").write_text(sumas, encoding="utf-8")

    cuerpo = f"""{notas}

### Descarga

| Plataforma | Archivo | Requisitos |
|------------|---------|------------|
{chr(10).join(filas)}

Guía de instalación, actualización y solución de problemas en el
[README](https://github.com/{REPO}#descarga-e-instalación). Si ya usas
Reyger, instala encima: tus datos se conservan.

Para verificar la descarga, compara su SHA-256 con `SHA256SUMS.txt`:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing     # Linux
shasum -a 256 -c SHA256SUMS.txt --ignore-missing # macOS
```

```powershell
Get-FileHash .\\Reyger-Windows.msi -Algorithm SHA256   # Windows
```
"""
    (salida / "NOTAS.md").write_text(cuerpo, encoding="utf-8")
    return publicados


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    for nombre in preparar(*sys.argv[1:]):
        print(nombre)
