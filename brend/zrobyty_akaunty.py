"""Картинки для створення акаунтів (ZAVDANNYA-131): аватар і обкладинки в розмірах кожної мережі.

    python brend/zrobyty_akaunty.py

Бере готові файли з `brend/hotovi/` (знак «сота в соті» й обкладинки, `brend/zrobyty.py --vse`) і кладе в
`brend/akaunty/` під назвами «мережа-що-розмір.png» — щоб у день реєстрації нічого не різати вручну.
Аватар зменшується якісно (Lanczos); обкладинки — копії готових файлів у розмірі, який радить мережа.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

TEKA = Path(__file__).resolve().parent
HOTOVI = TEKA / 'hotovi'
AKAUNTY = TEKA / 'akaunty'

AVATAR = HOTOVI / 'avatar' / 'avatar-1024.png'
# мережа → сторона квадратного аватара (рекомендований розмір мережі; мережа сама зменшує до кола)
AVATARY = {
    'tiktok': 400,          # мінімум 200×200
    'youtube': 800,         # радить 800×800
    'instagram': 640,       # показує 320×320; більший — чіткіший
    'facebook': 720,        # показує 176×176 на комп'ютері; радить ≥ 720
    'telegram-kanal': 640,
    'telegram-bot': 640,    # @BotFather → /setuserpic
    'x': 400,               # радить 400×400
    'hmail': 512,           # аватар облікового запису Google (пошта, YouTube)
}
OBKLADYNKY = {
    'youtube-obkladynka-2560x1440.png': HOTOVI / 'youtube' / 'youtube-2560x1440.png',
    'facebook-obkladynka-1640x624.png': HOTOVI / 'facebook' / 'facebook-1640x624.png',
    'x-obkladynka-1500x500.png': HOTOVI / 'x' / 'x-1500x500.png',
}


def zrobyty(kudy: Path = AKAUNTY) -> list[Path]:
    kudy.mkdir(parents=True, exist_ok=True)
    zrobleno = []
    z = Image.open(AVATAR).convert('RGB')
    for merezha, n in AVATARY.items():
        f = kudy / f'{merezha}-avatar-{n}.png'
        z.resize((n, n), Image.LANCZOS).save(f, optimize=True)
        zrobleno.append(f)
    for imia, dzherelo in OBKLADYNKY.items():
        f = kudy / imia
        shutil.copyfile(dzherelo, f)
        zrobleno.append(f)
    return zrobleno


if __name__ == '__main__':
    for f in zrobyty():
        print('готово ', f.relative_to(TEKA.parent))
    sys.exit(0)
