# -*- coding: utf-8 -*-
"""Зміст трьох екранів — однаковий для всіх стилів (ZAVDANNYA-193). Стиль міняє лише вигляд."""
import json, math, os

TUT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(TUT, 'dani.json')))
NB = ' '
HR = {h['k']: h for h in D['hrupy']}
PORIADOK = [h['k'] for h in D['hrupy']]
ROKY = list(range(2016, 2027))
MIS = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень',
       'листопад', 'грудень']


def ch(n):
    s = f'{int(n):,}'.replace(',', NB)
    return s


def vidm(n, f):
    n = abs(int(n)) % 100
    if 11 <= n <= 14: return f[2]
    n %= 10
    return f[0] if n == 1 else f[1] if 2 <= n <= 4 else f[2]


def z_velykoi(t):
    return t[:1].upper() + t[1:]


def period_1551():
    m = D['misiatsi_1551']
    a, b = m[0].split('-'), m[-1].split('-')
    return f'{MIS[int(a[1]) - 1]} {a[0]} — {MIS[int(b[1]) - 1]} {b[0]}'


# ------------------------------------------------------------------ графіки (SVG)
def grafik(znach, vyd, w=320, h=80, zamk=(), nepovnyi=2026, kolir='currentColor', tiho='var(--muted)', pidpysy=True,
           osnova='var(--line-strong)'):
    """znach — список за ROKY. vyd: bars | line | tiles | hatch | vector | dots"""
    n = len(znach)
    mx = max(znach) or 1
    pad_b = 16 if pidpysy else 2
    hh = h - pad_b - 4
    out = [f'<svg class="grafik grafik--{vyd}" viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" role="img" '
           f'aria-label="За роками 2016–2026">']
    step = w / n
    if vyd in ('bars', 'hatch'):
        bw = step * (0.62 if vyd == 'bars' else 0.7)
        if vyd == 'hatch':
            out.append(f'<defs><pattern id="hp" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)">'
                       f'<line x1="0" y1="0" x2="0" y2="4" stroke="{kolir}" stroke-width="1.6"/></pattern></defs>')
        for i, v in enumerate(znach):
            r = ROKY[i]
            bh = max(1.5, hh * v / mx)
            x = i * step + (step - bw) / 2
            y = 4 + hh - bh
            fill = tiho if r in zamk else kolir
            if vyd == 'hatch' and r not in zamk:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="url(#hp)" stroke="{kolir}" stroke-width="1"/>')
            else:
                op = ' opacity=".55"' if r == nepovnyi else ''
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}"{op}/>')
    elif vyd in ('line', 'vector', 'dots'):
        pts = [((i + .5) * step, 4 + hh - hh * v / mx) for i, v in enumerate(znach)]
        if vyd == 'vector':
            out.append(f'<line x1="0" y1="{4 + hh + .5}" x2="{w}" y2="{4 + hh + .5}" stroke="{osnova}" stroke-width="1"/>')
            out.append(f'<path d="M{w - 7},{4 + hh - 3.5} L{w},{4 + hh + .5} L{w - 7},{4 + hh + 4.5}" fill="none" stroke="{osnova}" stroke-width="1"/>')
        d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts[:-1])
        out.append(f'<path d="{d}" fill="none" stroke="{kolir}" stroke-width="{2 if vyd != "dots" else 1}" stroke-linejoin="miter"/>')
        x1, y1 = pts[-2]; x2, y2 = pts[-1]
        out.append(f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" fill="none" stroke="{kolir}" stroke-width="2" stroke-dasharray="3 3"/>')
        for i, (x, y) in enumerate(pts):
            r = ROKY[i]
            if vyd == 'dots' or i in (n - 2,):
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3 if vyd == "dots" else 2.6}" fill="{tiho if r in zamk else kolir}"/>')
    elif vyd == 'tiles':
        # мозаїка: кожен рік — стовпчик плиток
        rows = 8
        th = hh / rows
        for i, v in enumerate(znach):
            r = ROKY[i]
            k = max(1, round(rows * v / mx))
            for j in range(k):
                x = i * step + step * .12
                y = 4 + hh - (j + 1) * th + 1
                fill = tiho if r in zamk else kolir
                op = .45 if r == nepovnyi else (0.55 + 0.45 * (j / rows))
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{step * .76:.1f}" height="{th - 2:.1f}" rx="1" fill="{fill}" opacity="{op:.2f}"/>')
    if pidpysy:
        for i, r in enumerate(ROKY):
            if i % 2 == 0 or r == 2026:
                out.append(f'<text x="{(i + .5) * step:.1f}" y="{h - 3}" text-anchor="middle">’{str(r)[2:]}</text>')
    out.append('</svg>')
    return ''.join(out)


def strilka(a, b, w=34, h=14, kolir='currentColor'):
    """маленький «вектор» зміни a -> b (минуле, не прогноз): кут з відношення"""
    k = math.log2((b + 1) / (a + 1))
    ang = max(-50, min(50, k * 45))
    rad = math.radians(ang)
    x2, y2 = 2 + (w - 6) * math.cos(rad), h / 2 - (w - 6) * math.sin(rad) * .5
    return (f'<svg class="strilka" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<line x1="2" y1="{h / 2}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{kolir}" stroke-width="1.6"/>'
            f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="2" fill="{kolir}"/></svg>')


# ------------------------------------------------------------------ дані екранів
def trend(roky):
    mid = sum(roky[0:3]) / 3 or 1
    r = roky[9] / mid
    if r >= 1.25: return 'росте', r
    if r <= 0.8: return 'менше', r
    return 'стабільно', r


def rech_trend(roky):
    t, r = trend(roky)
    if t == 'росте':
        return f'2025 року — у {r:.1f} раза більше, ніж у середньому за 2016–2018'.replace('.', ',')
    if t == 'менше':
        return f'2025 року — {round(r * 100)} % від середнього за 2016–2018'
    return '2025 року — приблизно як у середньому за 2016–2018'


def sota():
    s = D['sota']
    hr = [(HR[k]['nazva'], n, k) for k, n in s['hrupy']]
    return dict(nazva='Подільський район', pidpys=f'сота ≈{NB}0,7{NB}км²', n=s['n'], raz=str(s['raz']).replace('.', ','),
                hrupy=hr, roky=[s['roky'][str(r)] if str(r) in s['roky'] else s['roky'].get(r, 0) for r in ROKY],
                pik=f'{s["pik"]}–{s["pik"] + 3}{NB}год', problemy=s['problemy'])


def budynok():
    b = D['budynok']
    sk = b['skarhy']
    vs = sum(n for _, n in sk)
    roky = {int(k): v for k, v in b['roky'].items()}
    po_hrupah = {}
    for r, g in roky.items():
        for k, n in g.items():
            po_hrupah[k] = po_hrupah.get(k, 0) + n
    pod = sum(po_hrupah.values())
    top = sorted(po_hrupah.items(), key=lambda x: (-x[1], PORIADOK.index(x[0])))
    t1, t2 = sk[0], sk[1]
    sus = b['susidy']
    abz = (f'За {period_1551()} до гарячої лінії 1551 щодо цього будинку надійшло {vs} {vidm(vs, ("звернення", "звернення", "звернень"))}. '
           f'Найчастіше — {t1[0]} ({t1[1]}) і {t2[0]} ({t2[1]}). Сусідній будинок у радіусі 400{NB}м зазвичай має на тему '
           f'«{t1[0]}» — {sus.get(t1[0], 0)}. У даних судів за 2024–2026 з адресою будинку — {pod} {vidm(pod, ("подія", "події", "подій"))}: '
           + ', '.join(f'{HR[k]["slovo"]} — {n}' for k, n in top) + '.')
    return dict(vulytsia=b['vulytsia'], rayon=b['rayon'], abz=abz, skarh=vs, podii=pod, skarhy=sk[:8], susidy=sus,
                susidiv=b['susidiv'], roky=roky, hrupy=[k for k in PORIADOK if k in po_hrupah], period=period_1551())


def rayon():
    r = D['rayon']
    hr = []
    for g in r['hrupy']:
        k = g['k']
        hr.append(dict(k=k, nazva=HR[k]['nazva'], n=g['n'], ost=g['roky'][9], roky=g['roky'], trend=rech_trend(g['roky']),
                       tr=trend(g['roky'])[0], vydy=[(z_velykoi(v), p) for v, p in g['vydy']]))
    vs = r['vsogo']
    top = sorted(hr, key=lambda x: -x['n'])[:2]
    zminy = sorted((x for x in hr if x['n'] >= 50), key=lambda x: -abs(math.log(trend(x['roky'])[1])))
    z = zminy[0]
    sk = r['skarhy']
    skv = sum(n for _, n in sk)
    rech = [
        f'За 2024–2026 у даних судів — {ch(vs)} {vidm(vs, ("подія", "події", "подій"))} з точною адресою в районі; найчастіше — '
        f'{top[0]["nazva"].lower() if top[0]["k"] != "dtp" else "ДТП"} ({ch(top[0]["n"])}) і {top[1]["nazva"].lower()} ({ch(top[1]["n"])}).',
        f'Найбільше змінилось за 10 років — {z["nazva"].lower() if z["k"] != "dtp" else "ДТП"}: {z["trend"]}.',
        f'До гарячої лінії 1551 з адрес району за 12 місяців найчастіше звертались на теми «{sk[0][0]}» і «{sk[1][0]}».',
    ]
    return dict(nazva=r['nazva'], vsogo=vs, hrupy=hr, rech=rech, skarhy=sk, budynkiv=r['budynkiv'], roky=r['roky'],
                problem_n=r['problem_n'], problemy=r['problemy_nazvy'])
