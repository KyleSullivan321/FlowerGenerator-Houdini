"""Tile preview renders into one downscaled contact sheet.

usage: python tools/contact_sheet.py DIR OUT.jpg [max_width]

Rows are species, columns are the files of each species in name order
(<species>_b000.png, <species>_b050.png, ..., <species>_plant.png).
"""
import collections
import pathlib
import sys

from PIL import Image, ImageDraw

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
max_w = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
rows = collections.OrderedDict()
for f in sorted(src.glob("*.png")):
    rows.setdefault(f.stem.split("_")[0], []).append(f)
cols = max(len(v) for v in rows.values())
cell = max_w // cols
sheet = Image.new("RGB", (cell * cols, cell * len(rows)), (0, 0, 0))
draw = ImageDraw.Draw(sheet)
for r, (name, files) in enumerate(rows.items()):
    for c, f in enumerate(files):
        im = Image.open(f).convert("RGB")
        im.thumbnail((cell, cell))
        sheet.paste(im, (c * cell, r * cell))
        draw.text((c * cell + 4, r * cell + 4), f.stem, fill=(200, 200, 200))
sheet.save(out, quality=88)
print("wrote", out, sheet.size)
