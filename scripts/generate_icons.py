#!/usr/bin/env python3
"""Genera los iconos de aplicación a partir del isotipo de la marca.

Toma ``assets/img/logo_icon.png`` (el isotipo con canal alfa), lo compone
sobre un lienzo cuadrado transparente de 1024×1024 y a partir de ahí
genera:

* ``icono.png``           -> master 1024×1024 (para iconphoto de Tkinter)
* ``icono.png-<s>.png``   -> PNG cuadrados en 16/32/64/128/256/512/1024
* ``icono.ico``           -> multi-resolución para Windows/ejecutable
* ``icono.icns``          -> para compilación en macOS

Ejecutar desde la raíz del repositorio.
"""

import os
from PIL import Image

SRC = os.path.join("src", "reyger", "assets", "img", "logo_icon.png")
OUT_DIR = os.path.join("src", "reyger", "assets")
CANVAS = 1024
SIZES = [16, 32, 64, 128, 256, 512, 1024]


def _cuadrado_marca():
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    square = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    escala = (CANVAS * 0.88) / max(w, h)
    logo = img.resize((max(1, int(w * escala)), max(1, int(h * escala))), Image.LANCZOS)
    square.paste(
        logo, ((CANVAS - logo.size[0]) // 2, (CANVAS - logo.size[1]) // 2), logo
    )
    return square


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    square = _cuadrado_marca()

    for s in SIZES:
        ruta = os.path.join(OUT_DIR, f"icono.png-{s}.png")
        square.resize((s, s), Image.LANCZOS).save(ruta)
        print(f"Created {ruta} ({s}x{s})")

    master = os.path.join(OUT_DIR, "icono.png")
    square.save(master, "PNG")
    print(f"Created {master}")

    icns = os.path.join(OUT_DIR, "icono.icns")
    square.save(icns, format="ICNS")
    print(f"Created {icns}")

    ico = os.path.join(OUT_DIR, "icono.ico")
    square.save(
        ico,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created {ico}")

    print("Done!")


if __name__ == "__main__":
    main()
