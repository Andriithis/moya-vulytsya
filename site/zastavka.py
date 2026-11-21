"""Перший екран головної й /karta/: легка картинка карти Києва замість живої карти (ZAVDANNYA-164, MV-176).

Жива карта важить ≈ 3 МБ (бібліотека, стилі, плитки, соти) — на телефоні перший екран з'являвся за 7–8 с. Тепер перший
екран — одна картинка WebP у тому самому вигляді: підкладка (знімки справжньої карти без сот — site/sait/pidkladka/,
їх робить znimaty.mjs) + соти з даних цього випуску + підписи місць зверху, як на живій карті. Жива карта вантажиться
після першого дотику, прокрутки або ≈ 3 с простою (karta.js) і ставиться на те саме місце — заміну не видно.

Два варіанти, як і камера живої карти (kameraMista() у karta.js): телефон (до 700 px завширшки — великі соти, рівень 7)
і комп'ютер (середні соти, рівень 8, бо там стартовий зум ≈ 10). Кожен — у світлій і темній темі; браузер бере лише
одну картинку з чотирьох (CSS за шириною екрана й темою).

Положення картинки рахує CSS (одиниці контейнера cqw/cqh) за тими самими формулами, що й стартова камера карти:
зум = log2(min((ширина − поля) / dx, (висота − поля) / dy)) + запас, центр — середина меж Києва. Масштаб лінійний,
тож логарифм не потрібен.

Колір — кількість подій у даних, не небезпека (AGENTS.md, розд. 7). Лише числа по сотах, без адрес (розд. 8).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw

PIDKLADKA_TEKA = Path(__file__).resolve().parent / 'sait' / 'pidkladka'
TEMY_TEKA = Path(__file__).resolve().parent / 'temy'
# Підкладка своя в кожної теми вигляду (MV-219): sait/pidkladka/<тема>/. Обрану тему ставить збирач (vstanovyty_temu).
TEMA = 'spokiyna'
POLIA_PIDKLADKY = ('bg', 'water', 'park', 'building', 'road', 'label', 'halo')   # кольори теми, що видно на знімках підкладки


def pidkladka(tema: str | None = None) -> Path:
    return PIDKLADKA_TEKA / (tema or TEMA)


def vidbytok_pidkladky(tema: str) -> str:
    """Відбиток кольорів підкладки теми (тло, вода, парки, будинки, дороги, підписи) — пише znimaty.mjs у meta.json;
    змінили їх у site/temy/<тема>.json — перезніміть підкладку (тест стереже)."""
    k = json.loads((TEMY_TEKA / f'{tema}.json').read_text(encoding='utf-8'))['kolory']
    dani = {r: {n: k[r].get(n) for n in POLIA_PIDKLADKY} for r in ('svitla', 'temna')}
    return hashlib.sha256(json.dumps(dani, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def zminni_karty(tema: str | None = None) -> dict:
    """Прозорість сот, межа соти й «світло» верху вершини — з теми (zminni_tem: karta-proz, karta-mezha-soty, karta-kant)."""
    z = json.loads((TEMY_TEKA / f'{tema or TEMA}.json').read_text(encoding='utf-8'))['zminni_tem']
    out = {}
    for r in ('svitla', 'temna'):
        lo, hi = (float(x) for x in z[r]['karta-proz'].split())
        m = re.fullmatch(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', z[r]['karta-mezha-soty'].replace(' ', ''))
        out[r] = {'proz': (lo, hi), 'mezha': (int(m[1]), int(m[2]), int(m[3]), round(float(m[4]) * 255)),
                  'kant': float(z[r].get('karta-kant', 0.08 if r == 'temna' else 0.28))}
    return out

# Ті самі сталі, що в karta.js (KYIV, RIVNI, KVANT, VERSHYNA, kameraMista). Змінили там — змініть тут:
# тест tests/test_zastavka.py звіряє їх з karta.js. PROZ — запасна (тема indygo), якщо в темі немає karta-proz.
KYIV = ((30.2361, 50.2132), (30.8264, 50.5908))
KVANT = (0.2, 0.4, 0.6, 0.88)
VERSHYNA = 0.88
PROZ = {'svitla': (0.2, 0.62), 'temna': (0.24, 0.5)}
# варіант → рівень сот, коефіцієнт зменшення стовпчика (RIVNI.k), поля камери (верх, низ, ліво, право), запас зуму
VARIANTY = {
    'telefon': {'riven': 7, 'k': 0.55, 'polia': (120, 70, 0, 0), 'zapas': 0.3},
    'komp': {'riven': 8, 'k': 0.64, 'polia': (130, 60, 48, 48), 'zapas': 0.35},
}
TELEFON_DO = 700          # telefon() у karta.js: window.innerWidth <= 700
NADVYBIRKA = 2            # соти малюємо вдвічі більшими й зменшуємо — рівні краї без драбинки
YAKIST = 68           # на око як 80, а важить на чверть менше (ZVIT-164)


def merc(lon: float, lat: float, z: float) -> tuple[float, float]:
    """Довгота/широта → пікселі веб-Меркатора (плитки 512, як у MapLibre) на зумі z."""
    s = 512 * 2 ** z
    y = math.log(math.tan(math.pi / 4 + lat * math.pi / 360))
    return (lon + 180) / 360 * s, (1 - y / math.pi) / 2 * s


def tsentr_kyieva() -> tuple[float, float]:
    """Центр стартової камери: середина меж Києва (по Меркатору — як kameraMista())."""
    (w, s), (e, n) = KYIV
    my = lambda la: math.log(math.tan(math.pi / 4 + la * math.pi / 360))
    cy = (my(n) + my(s)) / 2
    return (w + e) / 2, (2 * math.atan(math.exp(cy)) - math.pi / 2) * 180 / math.pi


def chastky(soty: list[dict]) -> dict[str, tuple[float, int]]:
    """Шкала частками (MV-55), як pererakhuvaty() у karta.js за всіх видів і останніх 3 років: сота → (q, клас 0–4)."""
    zi = sorted((f for f in soty if f['properties'].get('all3', 0) > 0), key=lambda f: f['properties']['all3'])
    L, out, i = len(zi), {}, 0
    while i < L:
        j = i
        while j < L and zi[j]['properties']['all3'] == zi[i]['properties']['all3']:
            j += 1
        q = (i + (j - i) / 2) / L
        for t in range(i, j):
            out[zi[t]['properties']['id']] = (q, sum(1 for x in KVANT if q >= x))
        i = j
    return out


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _zmishaty(a: str, b: str, k: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return '#' + ''.join(f'{max(0, min(255, round(x + (y - x) * k))):02X}' for x, y in zip(ra, rb))


def _kant(q: float, kolory: dict, tema: str, svitlo: float | None = None) -> str:
    """Колір верху стовпчика-вершини (koloryVershyny у karta.js): згори видно саме його."""
    t = math.sqrt(min(1, max(0, (q - VERSHYNA) / (1 - VERSHYNA))))
    c = _zmishaty(kolory['pk'][0], kolory['pk'][1], t)
    if svitlo is None:
        svitlo = 0.08 if tema == 'temna' else 0.28
    return _zmishaty(c, '#FFFFFF', svitlo)


def meta(tema: str | None = None) -> dict:
    return json.loads((pidkladka(tema) / 'meta.json').read_text(encoding='utf-8'))['varianty']


def kartynka(variant: str, tema: str, soty: list[dict], kolory: dict) -> bytes:
    """WebP першого екрана: тло підкладки → соти → підписи місць (порядок шарів живої карти: соти під підписами)."""
    m, v = meta()[variant], VARIANTY[variant]
    z, dpr, W, H = m['z'], m['dpr'], m['sirina'], m['vysota']
    cx, cy = merc(*m['tsentr'], z)
    x0, y0 = cx - W / 2, cy - H / 2
    tlo = Image.open(pidkladka() / f'{variant}-{tema}-tlo.webp').convert('RGBA')
    pidpysy = Image.open(pidkladka() / f'{variant}-{tema}-pidpysy.webp').convert('RGBA')
    PW, PH = tlo.size
    S = NADVYBIRKA * PW / W                 # пікселів картинки (з надвибіркою) на CSS-піксель
    zalyvka = Image.new('RGBA', (PW * NADVYBIRKA, PH * NADVYBIRKA), (0, 0, 0, 0))
    liniyi = Image.new('RGBA', zalyvka.size, (0, 0, 0, 0))
    stovpy = Image.new('RGBA', zalyvka.size, (0, 0, 0, 0))
    dz, dl, ds = ImageDraw.Draw(zalyvka), ImageDraw.Draw(liniyi), ImageDraw.Draw(stovpy)
    zk = zminni_karty()[tema]
    lo, hi = zk['proz']
    liniia = zk['mezha']
    tovshch = max(1, round(0.6 * S))
    op_stovpa = 0.95 if tema == 'temna' else 0.88
    q_kr = chastky(soty)

    def pt(lon, lat):
        x, y = merc(lon, lat, z)
        return (x - x0) * S, (y - y0) * S

    for f in soty:
        k = f['properties']['id']
        if k not in q_kr:
            continue
        q, kr = q_kr[k]
        kontur = f['geometry']['coordinates'][0]
        tochky = [pt(lon, lat) for lon, lat in kontur]
        if not any(-50 < x < zalyvka.width + 50 and -50 < y < zalyvka.height + 50 for x, y in tochky):
            continue
        a = lo + (hi - lo) * q * q
        dz.polygon(tochky, fill=(*_rgb(kolory['sc'][kr]), round(a * 255)))
        dl.line(tochky + [tochky[0]], fill=liniia, width=tovshch, joint='curve')
        if q >= VERSHYNA:
            # стовпчик згори — зменшена сота (zmenshyty у karta.js) кольору верху
            vershyny = kontur[:-1] if kontur[0] == kontur[-1] else kontur
            mx = sum(p[0] for p in vershyny) / len(vershyny)
            my_ = sum(p[1] for p in vershyny) / len(vershyny)
            menshi = [pt(mx + (lon - mx) * v['k'], my_ + (lat - my_) * v['k']) for lon, lat in kontur]
            ds.polygon(menshi, fill=(*_rgb(_kant(q, kolory, tema, zk['kant'])), round(op_stovpa * 255)))
    vse = Image.alpha_composite(Image.alpha_composite(zalyvka, liniyi), stovpy)
    vse = vse.resize((PW, PH), Image.LANCZOS)
    rez = Image.alpha_composite(Image.alpha_composite(tlo, vse), pidpysy).convert('RGB')
    b = io.BytesIO()
    rez.save(b, 'WEBP', quality=YAKIST, method=6)
    return b.getvalue()


def css(fayly: dict[tuple[str, str], str]) -> str:
    """Стилі положення картинки: та сама геометрія, що в стартової камери живої карти (kameraMista у karta.js)."""
    (w, s), (e, n) = KYIV
    my = lambda la: math.log(math.tan(math.pi / 4 + la * math.pi / 360))
    dx0, dy0 = (e - w) / 360 * 512, (my(n) - my(s)) / (2 * math.pi) * 512
    tc = tsentr_kyieva()
    pravyla = []
    for variant, v in VARIANTY.items():
        m = meta()[variant]
        z, W, H = m['z'], m['sirina'], m['vysota']
        cx, cy = merc(*m['tsentr'], z)
        kx, ky = merc(*tc, z)
        t, b, l, r = v['polia']
        k = W * 2 ** (v['zapas'] - z)
        A, B = k / dx0, k / dy0
        fx, fy = (W / 2 + kx - cx) / W, (H / 2 + ky - cy) / W
        shyryna = f'min(calc((100cqw - {l + r}px) * {A:.6f}), calc((100cqh - {t + b}px) * {B:.6f}))'
        pravylo = (f'.zastavka{{--zw:{shyryna};width:var(--zw);height:calc(var(--zw) * {H / W:.6f});'
                   f'left:calc(50cqw - var(--zw) * {fx:.6f});top:calc(50cqh - var(--zw) * {fy:.6f});'
                   f'background-size:100% 100%;background-image:url("{fayly[(variant, "svitla")]}")}}'
                   f'html[data-t="temna"] .zastavka{{background-image:url("{fayly[(variant, "temna")]}")}}')
        umova = f'(max-width:{TELEFON_DO}px)' if variant == 'telefon' else f'(min-width:{TELEFON_DO + 0.02}px)'
        pravyla.append(f'@media {umova}{{{pravylo}}}')
    return ('/* Перший екран карти (ZAVDANNYA-164): картинка там само, де стане жива карта; пише site/zastavka.py. */\n'
            '@supports (width:1cqw){.ekran-karty{container-type:size}' + ''.join(pravyla) + '}\n')


def zibraty(soty_rivniv: dict[int, dict], kolory_tem: dict, teka_karty: Path) -> tuple[str, dict]:
    """Картинки першого екрана в теку karta/ сайту; повертає стилі для sait.css і адреси картинок {(варіант, тема): url}. Ім'я файла — з відбитком вмісту:
    новий випуск — нова назва, і старий кеш браузера не покаже старих сот під новою живою картою."""
    fayly = {}
    if not (pidkladka() / 'meta.json').is_file():
        print(f'Увага: немає знімків підкладки теми {TEMA} (site/sait/pidkladka/{TEMA}/) — перший екран без картинки, '
              'жива карта одразу. Зняти: site/sait/pidkladka/znimaty.mjs')
        return '', fayly
    for variant, v in VARIANTY.items():
        soty = soty_rivniv[v['riven']]['features']
        for tema in ('svitla', 'temna'):
            dani = kartynka(variant, tema, soty, kolory_tem[tema])
            nazva = f'zastavka-{variant}-{tema}-{hashlib.sha256(dani).hexdigest()[:10]}.webp'
            teka_karty.mkdir(parents=True, exist_ok=True)
            (teka_karty / nazva).write_bytes(dani)
            fayly[(variant, tema)] = f'/karta/{nazva}'
    return css(fayly), fayly
