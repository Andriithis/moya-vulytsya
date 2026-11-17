"""Картинки для поширення в соцмережах (Open Graph, `og:image`) — ZAVDANNYA-88, п. 3.

Лише числа: назва місця (адреса будинку, вулиця, вітрина) і одне-два числа з підписом. Жодних описів подій, слів про
небезпеку чи оцінок (ROLYKY-I-SOTSMEREZHI, розд. 5, п. 2). Колір — бренд (індиго), а не «страх».

Розмір 1200 × 630 — рекомендований для Facebook, Telegram, X, LinkedIn. Шрифт — IBM Plex Sans з сайту (woff2 читає
Pillow): кирилиця й латиниця — окремі файли, тож текст малюється відрізками за діапазонами з `sait.css`.
"""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SHYRYNA, VYSOTA = 1200, 630
SHRYFTY = Path(__file__).resolve().parent / 'sait' / 'shryfty'
POLE = 72


def _kyrylytsia(ch: str) -> bool:
    k = ord(ch)
    return 0x0400 <= k <= 0x045F or k in (0x0301, 0x0490, 0x0491, 0x04B0, 0x04B1, 0x2116)


@lru_cache(maxsize=None)
def _shryft(nabir: str, vaha: int, rozmir: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(SHRYFTY / f'ibm-plex-sans-{nabir}-{vaha}-normal.woff2'), rozmir)


def _vidrizky(tekst: str):
    """Текст → [(відрізок, набір шрифту)]: кирилиця й решта — різні файли шрифту."""
    out = []
    for ch in tekst:
        n = 'cyrillic' if _kyrylytsia(ch) else 'latin'
        if out and out[-1][1] == n:
            out[-1][0] += ch
        else:
            out.append([ch, n])
    return out


def shyryna_tekstu(tekst: str, vaha: int, rozmir: int) -> float:
    return sum(_shryft(n, vaha, rozmir).getlength(t) for t, n in _vidrizky(tekst))


def malyuvaty(d: ImageDraw.ImageDraw, xy: tuple, tekst: str, vaha: int, rozmir: int, kolir: str) -> None:
    x, y = xy
    for t, n in _vidrizky(tekst):
        f = _shryft(n, vaha, rozmir)
        d.text((x, y), t, font=f, fill=kolir, anchor='ls')
        x += f.getlength(t)


def rozbyty(tekst: str, vaha: int, rozmir: int, maks: float, ryadkiv: int) -> list[str]:
    """Перенос за словами; що не вміщається — обрізається трьома крапками."""
    slova, ryadky = tekst.split(), []
    for s in slova:
        if ryadky and shyryna_tekstu(ryadky[-1] + ' ' + s, vaha, rozmir) <= maks:
            ryadky[-1] += ' ' + s
        else:
            ryadky.append(s)
    if len(ryadky) > ryadkiv:
        ryadky = ryadky[:ryadkiv]
        ryadky[-1] += '…'
    while ryadky and shyryna_tekstu(ryadky[-1], vaha, rozmir) > maks and len(ryadky[-1]) > 2:
        ryadky[-1] = ryadky[-1][:-2] + '…'
    return ryadky


def kartynka(mitka: str, nazva: str, chysla: list[tuple[str, str]], kolory: dict) -> bytes:
    """PNG 1200 × 630: мітка (район, «будинок»), назва, до трьох чисел з підписами. Повертає байти PNG."""
    tlo, tekst, pryglushenyi, aktsent, mezha = (kolory['ground'], kolory['ink'], kolory['muted'], kolory['accent'],
                                                  kolory['line'])
    im = Image.new('RGB', (SHYRYNA, VYSOTA), tlo)
    d = ImageDraw.Draw(im)
    # Знак: шестикутник у шестикутнику, як лого сайту.
    cx, cy, r = POLE + 22, POLE + 24, 24
    d.polygon([(cx, cy - r), (cx + r * .87, cy - r / 2), (cx + r * .87, cy + r / 2), (cx, cy + r),
               (cx - r * .87, cy + r / 2), (cx - r * .87, cy - r / 2)], fill=aktsent)
    r2 = 10
    d.polygon([(cx, cy - r2), (cx + r2 * .87, cy - r2 / 2), (cx + r2 * .87, cy + r2 / 2), (cx, cy + r2),
               (cx - r2 * .87, cy + r2 / 2), (cx - r2 * .87, cy - r2 / 2)], fill=tlo)
    malyuvaty(d, (POLE + 62, POLE + 34), 'Моя вулиця', 700, 32, tekst)
    if mitka:
        malyuvaty(d, (POLE, POLE + 112), mitka, 600, 28, pryglushenyi)
    rozmir = 64 if shyryna_tekstu(nazva, 700, 64) <= SHYRYNA - 2 * POLE else 52
    y = POLE + 186
    for ryadok in rozbyty(nazva, 700, rozmir, SHYRYNA - 2 * POLE, 2):
        malyuvaty(d, (POLE, y), ryadok, 700, rozmir, tekst)
        y += int(rozmir * 1.15)
    # Числа — у ряд, кожне зі своїм підписом.
    chysla = chysla[:3]
    if chysla:
        d.line([(POLE, 430), (SHYRYNA - POLE, 430)], fill=mezha, width=2)
        krok = (SHYRYNA - 2 * POLE) / len(chysla)
        for i, (chyslo, pidpys) in enumerate(chysla):
            x = POLE + i * krok
            malyuvaty(d, (x, 520), chyslo, 700, 76, aktsent)
            for j, ryadok in enumerate(rozbyty(pidpys, 400, 26, krok - 24, 2)):
                malyuvaty(d, (x, 556 + j * 32), ryadok, 400, 26, pryglushenyi)
    buf = io.BytesIO()
    # Готова палітра (фон + 4 кольори з напівтонами) замість підбору кольорів для кожної картинки: у 10 разів швидше.
    im.quantize(palette=_palitra(tlo, tekst, pryglushenyi, aktsent, mezha), dither=Image.Dither.NONE).save(
        buf, 'PNG', compress_level=6)
    return buf.getvalue()


def _rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=4)
def _palitra(tlo: str, *kolory: str) -> Image.Image:
    t = _rgb(tlo)
    pal = [t]
    for k in map(_rgb, kolory):
        pal += [tuple(round(t[i] + (k[i] - t[i]) * j / 15) for i in range(3)) for j in range(1, 16)]
    im = Image.new('P', (1, 1))
    im.putpalette([c for rgb in pal for c in rgb] + [0] * (768 - 3 * len(pal)))
    return im
