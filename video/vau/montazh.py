"""Зібрати кілька знімків в один аркуш (для перевірки очима): python video/vau/montazh.py out.jpg a.png b.png …"""
import sys
from PIL import Image
out, fs = sys.argv[1], sys.argv[2:]
w = int(sys.argv[0] and 360)
ims = [Image.open(f).convert('RGB').resize((w, int(w * 16 / 9))) for f in fs]
a = Image.new('RGB', (w * len(ims) + 6 * (len(ims) - 1), ims[0].height), (17, 20, 42))
for i, im in enumerate(ims):
    a.paste(im, (i * (w + 6), 0))
a.save(out, quality=85)
