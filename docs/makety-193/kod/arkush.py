import sys, os
from PIL import Image, ImageDraw, ImageFont
P = sys.argv[1]; OUT = sys.argv[2]
POR = ['vektor-nich', 'vektor-rukh', 'spokiyna', 'tepla', 'chitka', 'nich', 'smila', 'kyiv', 'nynishniy']
NAZ = {'vektor-nich': '7а. Вектор · ніч', 'vektor-rukh': '7б. Вектор · рух', 'spokiyna': '1. Спокійна й чиста', 'tepla': '2. Тепла й людська',
       'chitka': '3. Чітка й упевнена', 'nich': '4. Нічне місто', 'smila': '5. Сміла й гучна', 'kyiv': '6. Свій Київ', 'nynishniy': "8. Нинішній «Індиго й м'ята»"}
F = ImageFont.truetype(sys.argv[3], 26)
def arkush(imya, w, h, kol=3):
    rows = (len(POR) + kol - 1) // kol
    A = Image.new('RGB', (kol * (w + 24) + 24, rows * (h + 64) + 24), '#FFFFFF')
    d = ImageDraw.Draw(A)
    for i, s in enumerate(POR):
        f = f'{P}/{s}/{imya}'
        if not os.path.exists(f): continue
        im = Image.open(f).convert('RGB')
        sc = w / im.width
        im = im.resize((w, int(im.height * sc)), Image.LANCZOS).crop((0, 0, w, h))
        x = 24 + (i % kol) * (w + 24); y = 24 + (i // kol) * (h + 64)
        d.text((x, y), NAZ[s], fill='#111', font=F)
        A.paste(im, (x, y + 40))
    A.save(f'{OUT}/{imya.replace(".png", "")}.png', optimize=True)
os.makedirs(OUT, exist_ok=True)
arkush('karta-pk.png', 683, 410)
arkush('karta-tel.png', 300, 650, kol=5 if False else 3)
arkush('budynok-pk.png', 683, 900)
arkush('budynok-tel.png', 300, 900)
arkush('rayon-pk.png', 683, 900)
arkush('rayon-tel.png', 300, 900)
