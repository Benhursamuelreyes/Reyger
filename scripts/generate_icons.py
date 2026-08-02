from PIL import Image
import os

SRC = "src/reyger/assets/icono.png"
OUT_DIR = "src/reyger/assets"
CANVAS = 1024
SIZES = [16, 32, 64, 128, 256, 512, 1024]

img = Image.open(SRC).convert("RGBA")
w, h = img.size

square = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
scale = (CANVAS * 0.8) / w
logo = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
square.paste(logo, ((CANVAS - logo.size[0]) // 2, (CANVAS - logo.size[1]) // 2), logo)

for s in SIZES:
    resized = square.resize((s, s), Image.LANCZOS)
    path = os.path.join(OUT_DIR, f"icono.png-{s}.png")
    resized.save(path)
    print(f"Created {path}  ({s}x{s})")

icns_path = os.path.join(OUT_DIR, "icono.icns")
square.save(icns_path, format="ICNS")
print(f"Created {icns_path}")

ico_path = os.path.join(OUT_DIR, "icono.ico")
square.save(
    ico_path,
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print(f"Created {ico_path}")

print("Done!")
