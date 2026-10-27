"""Contact sheet of chosen pages of a PDF:  python scripts/contact_sheet.py deck.pdf out.png 3 10 20 ..."""
import sys

import fitz
from PIL import Image

pdf, out, *pages = sys.argv[1:]
doc = fitz.open(pdf)
ims = []
for p in map(int, pages):
    pix = doc[min(p, len(doc)) - 1].get_pixmap(matrix=fitz.Matrix(0.8, 0.8))
    ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
w, h = ims[0].size
rows = (len(ims) + 2) // 3
sheet = Image.new("RGB", (w * 3, h * rows), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % 3) * w, (i // 3) * h))
sheet.save(out)
