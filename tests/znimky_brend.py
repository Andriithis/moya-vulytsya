"""Знімки для звіту ZAVDANNYA-12: як аватар читається в колі 110 px.

Запуск: python tests/znimky_brend.py   (спершу python brend/zrobyty.py --vse)
Бере brend/hotovi/avatar/*.png, обрізає колом 110 px (так показують Instagram, TikTok,
YouTube) і кладе поруч на світлому й темному тлі -> docs/znimky/zavdannya-12/avatar-kolo-110.png.
Також показує, як аватар виглядає в списку каналів Telegram (коло 54 px).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

KORIN = Path(__file__).resolve().parents[1]
AVATARY = KORIN / 'brend' / 'hotovi' / 'avatar'
KUDY = KORIN / 'docs' / 'znimky' / 'zavdannya-12' / 'avatar-kolo-110.png'


def kolo(img: Image.Image, d: int) -> Image.Image:
    m = img.resize((d, d), Image.LANCZOS).convert('RGBA')
    maska = Image.new('L', (d * 4, d * 4), 0)
    ImageDraw.Draw(maska).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
    m.putalpha(maska.resize((d, d), Image.LANCZOS))
    return m


def main() -> None:
    faily = [AVATARY / 'avatar-1024.png', AVATARY / 'avatar-akcent-1024.png']
    tla = [(255, 255, 255), (247, 246, 242), (17, 21, 23)]
    poliv = Image.new('RGB', (3 * 150 * len(faily), 2 * 150), (255, 255, 255))
    for i, f in enumerate(faily):
        a = Image.open(f)
        for j, tlo in enumerate(tla):
            x = (i * 3 + j) * 150
            poliv.paste(tlo, (x, 0, x + 150, 300))
            k = kolo(a, 110)
            poliv.paste(k, (x + 20, 20), k)
            m = kolo(a, 54)
            poliv.paste(m, (x + 48, 190), m)
    KUDY.parent.mkdir(parents=True, exist_ok=True)
    poliv.save(KUDY, optimize=True)
    print(KUDY)


if __name__ == '__main__':
    main()
