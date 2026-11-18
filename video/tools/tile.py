#!/usr/bin/env python3
"""tile PNGs into a grid: tile.py out.png cols a.png b.png ..."""
import sys, skia
out, cols, files = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
imgs = [skia.Image.open(f) for f in files]
w, h = imgs[0].width(), imgs[0].height()
rows = (len(imgs) + cols - 1) // cols
s = skia.Surface(cols * w + (cols - 1) * 8, rows * h + (rows - 1) * 8)
c = s.getCanvas(); c.clear(skia.Color(60, 60, 60))
for i, im in enumerate(imgs):
    c.drawImage(im, (i % cols) * (w + 8), (i // cols) * (h + 8))
s.makeImageSnapshot().save(out, skia.kPNG)
