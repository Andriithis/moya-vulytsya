"""Таблиця контрасту напрямів М7 (ZAVDANNYA-42, етап А, п. 2): OKLCH → sRGB, контраст за WCAG 2.

Запуск: python maket/m7/kontrast_m7.py        — короткий звіт і що не проходить
        python maket/m7/kontrast_m7.py md     — таблиця для docs/NASTRII-M7.md
Межі: найсвітліший і найтемніший крок сот і вершина до тла ≥ 2 : 1; межі плашок, акцент ≥ 3 : 1; текст ≥ 4,5 : 1.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

N = json.loads((Path(__file__).parent / 'napryamy.json').read_text(encoding='utf-8'))
MEZHI = {'сота «менше» / тло': 2, 'сота «більше» / тло': 2, 'вершина / тло': 2, 'межа плашки / тло': 3,
         'межа плашки / поверхня': 3, 'межа плашки / вода': 3, 'акцент / поверхня': 3, 'текст / поверхня': 4.5,
         'тихий текст / поверхня': 4.5}


def oklch_hex(c) -> str:
    L, C, h = c
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
           -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
           -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s]
    f = lambda x: 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return '#' + ''.join(f'{round(min(1, max(0, f(x))) * 255):02X}' for x in rgb)


def lum(hx: str) -> float:
    v = [int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def kontrast(a: str, b: str) -> float:
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def napryamy():
    return [(k, n) for k, n in N.items() if not k.startswith('_')]


def rozrakhunok():
    ryadky, zle = [], []
    for kl, n in napryamy():
        for t in ('svitla', 'temna'):
            p = n[t]
            H = {x: oklch_hex(v) for x, v in p.items() if isinstance(v, list) and not isinstance(v[0], list)}
            sc, pk, tlo = [oklch_hex(c) for c in p['sc']], [oklch_hex(c) for c in p['pk']], H['bg']
            m = {'сота «менше» / тло': kontrast(sc[0], tlo), 'сота «більше» / тло': kontrast(sc[-1], tlo),
                 'вершина / тло': kontrast(pk[-1], tlo), 'межа плашки / тло': kontrast(H['mezha'], tlo),
                 'межа плашки / поверхня': kontrast(H['mezha'], H['surface']),
                 'межа плашки / вода': kontrast(H['mezha'], H['water']),
                 'акцент / поверхня': kontrast(H['accent'], H['surface']),
                 'текст / поверхня': kontrast(H['ink'], H['surface']),
                 'тихий текст / поверхня': kontrast(H['muted'], H['surface'])}
            zle += [f'{kl}/{t}: {x} = {v:.2f} (треба ≥ {MEZHI[x]})' for x, v in m.items() if v < MEZHI[x]]
            ryadky.append((kl, n['nazva'], t, sc, pk, tlo, m))
    return ryadky, zle


if __name__ == '__main__':
    ryadky, zle = rozrakhunok()
    if sys.argv[1:] == ['md']:
        kol = list(MEZHI)
        print('| Напрям | Тема | Тло | Кроки сот (менше → більше) | ' + ' | '.join(kol) + ' |')
        print('|---|---|---|---|' + '---|' * len(kol))
        for kl, nazva, t, sc, pk, tlo, m in ryadky:
            print(f'| {nazva} | {"світла" if t == "svitla" else "темна"} | `{tlo}` | ' + ' '.join(f'`{c}`' for c in sc) + ' | '
                  + ' | '.join(f'{m[x]:.1f}'.replace('.', ',') for x in kol) + ' |')
    else:
        for kl, nazva, t, sc, pk, tlo, m in ryadky:
            print(f'{nazva} · {t}: тло {tlo}; соти {" ".join(sc)}; вершини {" ".join(pk)}')
            print('   ' + ' · '.join(f'{x} {v:.2f}' for x, v in m.items()))
    print('\nНЕ ПРОХОДЯТЬ:' if zle else '\nусі межі пройдено', *zle, sep='\n  ', file=sys.stderr)
