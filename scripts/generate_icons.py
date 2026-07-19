from PIL import Image
import os

SRC = "src/ventapro/assets/icono.png"
OUT_DIR = "src/ventapro/assets"
SIZES = [16, 32, 64, 128, 256, 512]

img = Image.open(SRC).convert("RGBA")
w, h = img.size

size = max(w, h)
if size < 512:
    size = 512

square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
offset = ((size - w) // 2, (size - h) // 2)
square.paste(img, offset, img)

for s in SIZES:
    resized = square.resize((s, s), Image.LANCZOS)
    path = os.path.join(OUT_DIR, f"icono.png-{s}.png")
    resized.save(path)
    print(f"Created {path}  ({s}x{s})")

print("Done!")
