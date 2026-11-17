"""Зшити кілька аркушів-знімків по вертикалі й зменшити (для перегляду): python video/vau/zshyty.py out.jpg a.jpg b.jpg … [--k 0.75]"""
import sys
from PIL import Image
a = [x for x in sys.argv[1:] if not x.startswith('--k')]
k = float(next((x.split('=')[1] for x in sys.argv if x.startswith('--k=')), 0.75))
out, fs = a[0], a[1:]
ims = [Image.open(f) for f in fs]
w = max(i.width for i in ims)
h = sum(i.height for i in ims) + 6 * len(ims)
z = Image.new('RGB', (w, h))
y = 0
for i in ims:
    z.paste(i, (0, y))
    y += i.height + 6
z.resize((int(w * k), int(h * k))).save(out, quality=80)
