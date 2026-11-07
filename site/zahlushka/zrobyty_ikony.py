"""Іконки для встановлення на телефон (ZAVDANNYA-06, п. 4).

Малює логотип-соту заглушки (та сама фігура, що в шапці: зовнішній шестикутник
#0B6B6B, внутрішній білий) у файли PNG:
  ikony/ikona-192.png, ikony/ikona-512.png          — звичайні (прозорий фон);
  ikony/ikona-maskable-512.png                       — «маскована» для Android:
      фон #F7F6F2 на весь квадрат, сота в безпечному колі 80 % (система сама
      обрізає іконку колом, квадратом із заокругленням тощо).

Файли вже лежать у репозиторії; перезапускати треба лише при зміні логотипа.
Запуск: python site/zahlushka/zrobyty_ikony.py   (потрібна бібліотека Pillow)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

TEKA = Path(__file__).resolve().parent / 'ikony'
ZELENYI = (11, 107, 107, 255)     # #0B6B6B — колір логотипа
BILYI = (255, 255, 255, 255)
TLO = (247, 246, 242, 255)        # #F7F6F2 — фон сторінок
# Фігури з SVG логотипа в шапці (viewBox 0 0 26 28).
ZOVNISHNII = [(13, 1), (25, 8), (25, 20), (13, 27), (1, 20), (1, 8)]
VNUTRISHNII = [(13, 9), (18, 12), (18, 17), (13, 20), (8, 17), (8, 12)]
ZBILSHENNYA = 4  # малюємо вчетверо більшим і зменшуємо — краї рівні


def namalyuvaty(rozmir: int, chastka: float, tlo) -> Image.Image:
    """Сота займає `chastka` висоти квадрата, по центру."""
    v = rozmir * ZBILSHENNYA
    img = Image.new('RGBA', (v, v), tlo)
    d = ImageDraw.Draw(img)
    masshtab = v * chastka / 26          # фігура 24×26 у системі 26×28
    zsuv_x = (v - 24 * masshtab) / 2 - 1 * masshtab
    zsuv_y = (v - 26 * masshtab) / 2 - 1 * masshtab
    for fihura, kolir in ((ZOVNISHNII, ZELENYI), (VNUTRISHNII, BILYI)):
        d.polygon([(zsuv_x + x * masshtab, zsuv_y + y * masshtab) for x, y in fihura], fill=kolir)
    return img.resize((rozmir, rozmir), Image.LANCZOS)


def main() -> None:
    TEKA.mkdir(exist_ok=True)
    for rozmir in (192, 512):
        namalyuvaty(rozmir, 0.92, (0, 0, 0, 0)).save(TEKA / f'ikona-{rozmir}.png', optimize=True)
    # Безпечна зона маскованої іконки — коло діаметром 80 %; сота 56 % висоти в неї вміщується.
    namalyuvaty(512, 0.56, TLO).save(TEKA / 'ikona-maskable-512.png', optimize=True)
    for p in sorted(TEKA.glob('*.png')):
        print(p.name, p.stat().st_size, 'байт')


if __name__ == '__main__':
    main()
