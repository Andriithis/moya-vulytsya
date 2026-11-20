"""Продуктові ролики ZAVDANNYA-155: «потреба → продукт» (В6) — вступ рушієм (вигляди 139) + запис справжніх сторінок продажу.

    node site/worker/testy/mistsevyi.mjs 8799 <тека сайту>                      # сервер продажу з тестовою оплатою
    python video/vau/stan155.py --server http://127.0.0.1:8799                  # замовлення, оплата, довідки, кабінети
    python video/vau/stan155.py --lyst nove-<дата>.json indeks.json 2026-10      # лист «Стежу» в HTML
    python video/vau/zapys155.py <events.db> --indeks indeks.json [--lyshe p1,p4] [--kadry 1,5,9] [--cpu]
    python video/vau/zapys155.py <events.db> --indeks indeks.json --pachka         # лише перевірки й чергування В2

Кожен ролик — два шматки, що йдуть один за одним без шва в часі:
  1. **потреба** (≈ 3,5 с): рушій `stsena.html` з виглядом 139 (тепло, хвилі, шпилі, бульбашки, світні точки, календар) —
     гачок у кадрі 0, тема ролика (темна чи світла), місце без номера будинку (камера не ближче рівня вулиці, MV-151);
  2. **продукт**: запис справжньої сторінки — довідка, повний звіт, кабінет рієлтора, кабінет ОСББ, лист «Стежу»,
     «Судова практика» — з місцевого сервера продажу (тестова оплата, довідки — справжнім генератором dani-edrsr).
Номери житлових будинків у кадрі розмиті (MV-25): у кожній сторінці «назва, номер» → номер під розмиттям; карти будинку
в довідці й звіті — розмиті цілком (точка будинку = адреса). Числа в тексті ролика — зі сторінки, яку записуємо.
Вихід — як у rushii.py: video/vyhid/155/<id>.mp4 (1080×1920, звук), lehki/, arkushi/; перевірки — perevirka.py (правила 138)
на весь ролик (вступ + запис), чергування пачки — perevirka.pereviryty_pachku.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import http.server
import json
import re
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402
import perevirka  # noqa: E402
import zapys_saitu as ZS  # noqa: E402
from laboratoriia139 import mistsia  # noqa: E402
from rushii import ARG_CPU, ARG_GPU, arkush, ffmpeg, lehka  # noqa: E402
from rushii import rendery as rendery_rushiia  # noqa: E402
from rushii import server as server_rushiia  # noqa: E402
from stsenarii import PROFIL, Rolyk, fp  # noqa: E402

VYHID = KORIN / 'video' / 'vyhid' / '155'
KESH = KORIN / 'video' / 'vyhid' / 'kesh' / 'stsenarii'
FPS = 30
VSTUP = 3.5                    # секунд «потреби» рушієм
PACHKA = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6']

# ------------------------------------------------------------------ сторінки: розмиття номерів будинків (MV-25)

ROZMYTTIA = r"""
(() => {
  const RX = /([А-ЯІЇЄҐа-яіїєґ'’.»])(\s*,\s*)(\d{1,4}(?:[-\/][0-9А-ЯІЇЄа-яіїє]{1,4}|[А-ЯІЇЄа-яіїє](?![а-яіїє]))?)(?![\d,]|\.\d|\s*(?:%|грн|под|звер|скарг|м\b|хв|раз|рок))/g;
  const KARTY = '.leaflet-container, .maplibregl-map, .mapa, #mapa, .karta-zvitu, .zvit-karta, figure.karta, .karta';
  function obrobyty(korin) {
    const w = document.createTreeWalker(korin, NodeFilter.SHOW_TEXT);
    const vuzly = [];
    while (w.nextNode()) { const n = w.currentNode; RX.lastIndex = 0; if (RX.test(n.nodeValue) && !(n.parentElement && n.parentElement.closest('script,style,.mv-rozm'))) vuzly.push(n); }
    for (const n of vuzly) {
      const f = document.createElement('span');
      f.innerHTML = n.nodeValue.replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]))
        .replace(RX, (m, a, b, c) => a + b + '<span class="mv-rozm">' + c + '</span>');
      n.replaceWith(...f.childNodes);
    }
    document.title = document.title.replace(RX, (m, a, b) => a + b + '…');
  }
  function styl() {
    if (document.getElementById('mv-rozm-styl')) return;
    const s = document.createElement('style'); s.id = 'mv-rozm-styl';
    s.textContent = '.mv-rozm{filter:blur(5px);display:inline-block;background:rgba(127,127,127,.25);border-radius:6px;padding:0 3px}' +
      KARTY + '{filter:blur(9px) saturate(.7)!important}';
    (document.head || document.documentElement).appendChild(s);
  }
  function vse() { if (document.body) { styl(); obrobyty(document.body); } }
  document.addEventListener('DOMContentLoaded', () => { vse(); new MutationObserver(vse).observe(document.body, {childList: true, subtree: true, characterData: true}); });
  window.__mvRozmyty = vse;
})();
"""


class Proksi(ZS.Obrobnyk):
    """/__vau/ — рамка й стилі рушія; решта — до місцевого сервера продажу (той самий шлях, куки, форми).
    Origin і Referer переписуються на адресу сервера (він приймає форми лише «зі свого сайту»); заборону вбудовування
    (frame-ancestors) і політику сторінки знято — сторінка показується в рамці «телефона» лише тут, на сервері вона та сама."""
    prodazh = 'http://127.0.0.1:8799'          # не «server»: так у обробника зветься сам HTTP-сервер

    def _peredaty(self):
        if self.path.startswith('/__vau/') or self.path.startswith('/site/sait/shryfty/'):
            return super().do_GET()
        if self.path.split('?')[0] == '/__lyst155.html':      # лист «Стежу» (платні дані — лише у video/vyhid/, не в git)
            dani = (VYHID / 'lyst155.html').read_bytes()
            self.send_response(200)
            self.send_header('content-type', 'text/html; charset=utf-8')
            self.send_header('content-length', str(len(dani)))
            http.server.SimpleHTTPRequestHandler.end_headers(self)
            self.wfile.write(dani)
            return
        u = urllib.parse.urlparse(self.prodazh)
        dovzh = int(self.headers.get('content-length') or 0)
        tilo = self.rfile.read(dovzh) if dovzh else None
        h = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'origin', 'referer', 'accept-encoding', 'connection')}
        if self.headers.get('origin'):
            h['origin'] = self.prodazh
        if self.headers.get('referer'):
            h['referer'] = self.prodazh + urllib.parse.urlparse(self.headers['referer']).path
        c = http.client.HTTPConnection(u.hostname, u.port, timeout=120)
        c.request(self.command, self.path, body=tilo, headers=h)
        r = c.getresponse()
        dani = r.read()
        self.send_response(r.status)
        for k, v in r.getheaders():
            kl = k.lower()
            if kl in ('transfer-encoding', 'connection', 'content-length', 'x-frame-options'):
                continue
            if kl == 'content-security-policy':
                continue        # лише в записі: інакше політика сторінок кабінету не пускає стиль розмиття номерів
            if kl == 'location':
                v = v.replace(self.prodazh, '')
            self.send_header(k, v)
        self.send_header('content-length', str(len(dani)))
        http.server.SimpleHTTPRequestHandler.end_headers(self)
        self.wfile.write(dani)

    def do_GET(self):
        self._peredaty()

    def do_POST(self):
        self._peredaty()


def tekst_storinky(stan, shliakh, kuka=None) -> str:
    u = urllib.parse.urlparse(stan['server'])
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=60)
    c.request('GET', shliakh, headers={'cookie': f"{kuka['name']}={kuka['value']}"} if kuka else {})
    t = c.getresponse().read().decode('utf-8', 'replace')
    t = re.sub(r'<(script|style)[\s\S]*?</\1>', ' ', t)
    import html
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))


def chyslo(s: str) -> int:
    return int(re.sub(r'\D', '', s))


# ------------------------------------------------------------------ вступ «потреба» — рушій, вигляди 139

def vstup(id_, tema, styl, c, z, p, b, hook, P, radius=1500, maks=None, poriadok='vypadkovo', min_m=0, efekty=()):
    """Рушій: вигляд 139 довкола місця c (без номерів, камера не ближче рівня вулиці), гачок з кадру 0."""
    R = Rolyk(f'155-{id_}-vstup', VSTUP, tema=tema, nazva='вступ', hachok=hook, meta='потреба', kudy='/', obryv=True, pravyla=129)
    R.S['nad_dorohamy'] = True
    R.S['zatemnennia'] = 0.55 if tema == 'svitla' else 0.85
    R.kam(0, c, z[0], p[0], b[0]).kam(VSTUP, c, z[1], p[1], b[1], e='io')
    st = dict(styl)
    if st['typ'] not in ('kalendar',):
        st['mistsia'] = mistsia(P, c, radius, t0=0.15, t1=2.4, maks=maks, poriadok=poriadok, min_m=min_m)
    R.S['styl'] = [st]
    R.tekst(0, VSTUP + 1, 'hook', hook, y='verkh')
    R.S['novynky'] = [1.2, 2.4]
    for e in efekty:
        R.efekt(*e[:2], **(e[2] if len(e) > 2 else {}))
    return R


def kalendar_2025(P):
    from datetime import date
    d0 = date(2025, 1, 1)
    dni = [0] * 365
    for x in P:
        if (x.data or '').startswith('2025'):
            try:
                i = (date.fromisoformat(x.data) - d0).days
            except ValueError:
                continue
            if 0 <= i < 365:
                dni[i] += 1
    nenul = sorted(v for v in dni if v)
    return dni, [nenul[int(len(nenul) * q)] for q in (0.0, 0.25, 0.5, 0.8)]


# ------------------------------------------------------------------ ролики

def tochka(indeks, slug):
    b = indeks[slug]
    return (b['lo'], b['la'])


def p1(stan, P, ix):
    """«Читає довідку про свій будинок — і вау» (В5): довідка 199 грн. Світла."""
    url = stan['dovidky']['orendar@proba.ua'][0]
    t = tekst_storinky(stan, url)
    vsi = chyslo(re.search(r'(\d[\d ]*)\s*скарг 1551 про будинок', t).group(1))
    hrupa, tut, sus = re.search(r'найчастіше — на ([^:]+):\s*(\d+); у сусідніх будинках типово (\d+)', t).groups()
    poruch = t[t.find('Поруч із сусідніми будинками'):]
    riadky = re.findall(r"(?:будинками|більше) ([а-яіїє][а-яіїє ,'’]*?) тут (\d+) · у сусідніх (\d+)", poruch)
    druha, n2 = riadky[1][0], riadky[1][1]          # другий рядок порівняння (перший — найчастіша група)
    hrupa_k = hrupa.split(',')[0].strip()
    c = tochka(ix, stan['budynky']['pryozerna'])
    c = (c[0] + 0.002, c[1] + 0.006)               # кадр — квартал на північ від будинку, не будинок
    T = 16.5
    R = vstup('p1', 'svitla', {'typ': 'teplo', 'z_ref': 13, 'radius': 30, 'ln_maks': 4.0, 'tryv': 2.2}, c, (13.4, 14.2), (20, 45),
              (0, -25), 'Живеш тут роками.\n*А що болить будинку?*', P, radius=2500)
    return R, {
        'id': '155-p1-chytaie-dovidku-vau', 'tryvalist': T, 'tema': 'svitla', 'start': url, 'kuka': None,
        'meta': dict(nazva='Читає довідку про свій будинок — і вау', typ='Хтось читає звіт — і вау', hrupa='Потреба → продукт',
                     meta='потреба (що болить будинку) → довідка про будинок, 199 грн', liniia='Довідка про будинок',
                     hachok='«Живеш тут роками. А що болить будинку?» над тепловою плямою кварталу', kudy='/miy-budynok/',
                     shar='zvit', vyhliad='teplo (139), світла'),
        'tekst': [
            {'t0': 3.5, 't1': 5.6, 'styl': 'velykyi', 'tekst': 'Довідка про будинок.\n*Відкриваю…*', 'y': 330},
            {'t0': 5.7, 't1': 8.0, 'styl': 'velykyi', 'tekst': f'*{D.chyslo(vsi)}* скарг\nза рік?!', 'y': 330},
            {'t0': 8.1, 't1': 10.6, 'styl': 'velykyi', 'tekst': f'{hrupa_k.capitalize()} — *{tut}*.\nУ сусідніх — {sus}.', 'y': 330},
            {'t0': 10.7, 't1': 13.0, 'styl': 'velykyi', 'tekst': f'{druha.split(",")[0].strip().capitalize()} — *{n2}*.\nОсь воно що.', 'y': 330},
            {'t0': 13.1, 't1': 15.4, 'styl': 'velykyi', 'tekst': 'І події з рішень\n*судів поруч*', 'y': 330},
            {'t0': 15.5, 't1': 16.5, 'styl': 'baner', 'zag': 'Довідка про будинок', 'knopka': '199 грн · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 4.6, 'dia': 'skrol', 'do_px': 60, 'tryv': 0.6},
            {'t': 5.7, 'dia': 'skrol', 'do_px': 120, 'tryv': 0.8},
            {'t': 7.2, 'dia': 'skrol', 'sel': 'h2, h3', 'do_px': 1180, 'tryv': 1.0},
            {'t': 8.4, 'dia': 'skrol', 'do_px': 1500, 'tryv': 0.9},
            {'t': 9.6, 'dia': 'skrol', 'do_px': 1880, 'tryv': 0.8},
            {'t': 10.8, 'dia': 'skrol', 'do_px': 2380, 'tryv': 1.0},
            {'t': 12.0, 'dia': 'skrol', 'do_px': 2620, 'tryv': 0.8},
            {'t': 13.1, 'dia': 'skrol', 'do_px': 3950, 'tryv': 1.4},
            {'t': 14.6, 'dia': 'skrol', 'do_px': 4300, 'tryv': 0.8},
        ],
        'zvuk': {'muzyka': {'styl': 'lofi', 'bpm': 92}, 'efekty': [
            {'t': 0.0, 'typ': 'pop', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.7, 'typ': 'udar', 'v': 0.55},
            {'t': 8.1, 'typ': 'pop', 'h': 1.1}, {'t': 10.7, 'typ': 'pop', 'h': 1.25}, {'t': 15.5, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}],
            'holos': [{'t': 0.2, 'tekst': 'Живеш тут роками. А що болить будинку?', 'holos': 'tetiana'},
                      {'t': 5.8, 'tekst': f'{D.chyslo(vsi)} скарг за рік. Серйозно?', 'holos': 'tetiana'},
                      {'t': 13.2, 'tekst': 'І все — з посиланнями.', 'holos': 'tetiana'}]},
        'pidpys': ['Запис справжньої довідки «Моєї вулиці» (тестова оплата). Номер будинку приховано. Скарги — звернення до 1551, '
                   'не перевірені факти; події — лише те, що дійшло до суду.', 'Довідка про свій будинок — 199 грн, посилання в профілі.'],
    }


def p2(stan, P, ix):
    """«Стежу за вулицею» — лист «Нове біля дому» раз на місяць (підписка 399). Темна."""
    lyst = (VYHID / stan['lyst']['fail']).read_text(encoding='utf-8')
    t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', lyst))
    n_p = chyslo(re.search(r'(\d+) поді\w* і', stan['lyst']['tema']).group(1))
    n_s = chyslo(re.search(r'(\d[\d ]*) звернен', stan['lyst']['tema']).group(1))
    c = tochka(ix, stan['budynky']['palladina'])
    c = (c[0] - 0.003, c[1] + 0.002)
    T = 15.5
    R = vstup('p2', 'temna', {'typ': 'khvyli', 'z_ref': 14.2}, c, (14.0, 14.6), (45, 60), (10, -30),
              'Біля дому щось сталося —\n*а ти й не знав?*', P, radius=1400, maks=160)
    return R, {
        'id': '155-p2-stezhu-za-vulytseiu', 'tryvalist': T, 'tema': 'temna', 'start': '/kabinet/', 'kuka': 'pidpysnyk',
        'meta': dict(nazva='Стежу за вулицею: лист «Нове біля дому»', typ='Стежу за вулицею · Рієлтор · ОСББ', hrupa='Потреба → продукт',
                     meta='потреба (що нового біля дому) → «Стежу» в підписці, лист раз на місяць, 399 грн/міс',
                     hachok='«Біля дому щось сталося — а ти й не знав?» над кільцями-хвилями', liniia='Підписка',
                     kudy='/oplata/?tovar=pidpyska', shar='zapys', riven='vulytsia', vyhliad='khvyli (139), темна'),
        'tekst': [
            {'t0': 3.5, 't1': 5.8, 'styl': 'velykyi', 'tekst': 'Кабінет → *«Стежу»*.\nДодав свій будинок.', 'y': 330},
            {'t0': 5.9, 't1': 8.2, 'styl': 'velykyi', 'tekst': 'Раз на місяць —\n*лист*', 'y': 330},
            {'t0': 8.3, 't1': 10.8, 'styl': 'velykyi', 'tekst': f'*{n_p} {fp(n_p)}* з рішень\nсудів поруч', 'y': 330},
            {'t0': 10.9, 't1': 13.2, 'styl': 'velykyi', 'tekst': f'*{D.chyslo(n_s)}* звернень\nдо 1551 поруч', 'y': 330},
            {'t0': 13.3, 't1': 14.4, 'styl': 'velykyi', 'tekst': 'Нове біля дому —\n*у пошті*', 'y': 330},
            {'t0': 14.5, 't1': 15.5, 'styl': 'baner', 'zag': 'Стежу за вулицею', 'knopka': 'Підписка 399 грн · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 3.6, 'dia': 'skrol', 'do_sel': '#stezhu', 'tryv': 1.2},
            {'t': 5.0, 'dia': 'tap', 'sel': '#stezhu li, #stezhu p'},
            {'t': 5.9, 'dia': 'goto', 'url': '/__lyst155.html'},
            {'t': 6.8, 'dia': 'skrol', 'do_px': 60, 'tryv': 1.0},
            {'t': 8.3, 'dia': 'skrol', 'do_frac': 0.25, 'tryv': 1.2},
            {'t': 9.6, 'dia': 'skrol', 'do_frac': 0.5, 'tryv': 1.2},
            {'t': 10.9, 'dia': 'skrol', 'do_frac': 0.85, 'tryv': 1.6},
            {'t': 12.6, 'dia': 'skrol', 'do_frac': 1.0, 'tryv': 0.8},
            {'t': 13.4, 'dia': 'tap', 'sel': 'a[href*="stezhu"]'},
        ],
        'zvuk': {'muzyka': {'styl': 'nich', 'bpm': 88}, 'efekty': [
            {'t': 0.0, 'typ': 'bas', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.9, 'typ': 'spovishchennia', 'v': 0.7},
            {'t': 8.3, 'typ': 'pop'}, {'t': 10.9, 'typ': 'pop', 'h': 1.2}, {'t': 14.5, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}]},
        'pidpys': [f'Запис справжнього кабінету й листа «Нове біля дому» (тестові дані, нікому не надіслано): {stan["lyst"]["tema"]}. '
                   'Номери будинків приховано. «Нове в даних» — рішення, що з\'явилися в даних за місяць.',
                   '«Стежу» — у підписці 399 грн/міс, посилання в профілі.'],
        'lyst': lyst,
    }


def p3(stan, P, ix):
    """Повний звіт «перед купівлею» (299 грн): рік за роком, усі події з описами. Світла."""
    url = stan['dovidky']['kupets@proba.ua'][0]
    t = tekst_storinky(stan, url)
    roky = sorted(set(re.findall(r'\b(202[3-6])\b', t)))
    c = tochka(ix, stan['budynky']['beresteiskyi'])
    c = (c[0] + 0.003, c[1] + 0.001)
    T = 16
    R = vstup('p3', 'svitla', {'typ': 'shpyli', 'r': 11, 'm_na_podiu': 9, 'maks_n': 160, 'tryv_rostu': 0.8}, c, (14.0, 14.5),
              (55, 66), (20, -20), 'Квартира — за 2 мільйони.\n*А що було на вулиці?*', P, radius=1500, poriadok='vid_tsentru')
    return R, {
        'id': '155-p3-povnyi-zvit-pered-kupivleiu', 'tryvalist': T, 'tema': 'svitla', 'start': url, 'kuka': None,
        'meta': dict(nazva='Повний звіт перед купівлею', typ='Хтось читає звіт — і вау', hrupa='Потреба → продукт',
                     meta='потреба (велика покупка) → повний звіт «перед купівлею», 299 грн',
                     hachok='«Квартира — за 2 мільйони. А що було на вулиці?» над 3D-шпилями', liniia='Повний звіт',
                     kudy='/miy-budynok/', shar='zvit', vyhliad='shpyli (139), світла'),
        'tekst': [
            {'t0': 3.5, 't1': 5.8, 'styl': 'velykyi', 'tekst': 'Повний звіт —\n*перед купівлею*', 'y': 330},
            {'t0': 5.9, 't1': 8.2, 'styl': 'velykyi', 'tekst': f'Рік за роком:\n*{roky[0]}–{roky[-1]}*', 'y': 330},
            {'t0': 8.3, 't1': 10.8, 'styl': 'velykyi', 'tekst': 'Що *повторюється*\nі що поруч', 'y': 330},
            {'t0': 10.9, 't1': 13.6, 'styl': 'velykyi', 'tekst': 'Кожна подія —\n*з описом і рішенням*', 'y': 330},
            {'t0': 13.7, 't1': 14.9, 'styl': 'velykyi', 'tekst': '299 грн.\n*Проти 2 мільйонів*', 'y': 330},
            {'t0': 15.0, 't1': 16.0, 'styl': 'baner', 'zag': 'Повний звіт перед купівлею', 'knopka': '299 грн · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 4.4, 'dia': 'skrol', 'do_px': 300, 'tryv': 1.2},
            {'t': 5.9, 'dia': 'skrol', 'do_tekst': 'Як змінювалося', 'tryv': 1.2},
            {'t': 7.3, 'dia': 'skrol', 'do_dy': 320, 'tryv': 0.9},
            {'t': 8.3, 'dia': 'skrol', 'do_tekst': 'Що повторюється на вулиці', 'tryv': 1.2},
            {'t': 9.7, 'dia': 'skrol', 'do_dy': 380, 'tryv': 0.9},
            {'t': 10.7, 'dia': 'js', 'kod': '() => document.querySelectorAll("details").forEach(d => { if (d.closest("section, div") && d.textContent.length < 40000) d.open = true; })'},
            {'t': 10.9, 'dia': 'skrol', 'do_tekst': 'Усі події з описами', 'tryv': 1.3},
            {'t': 12.4, 'dia': 'skrol', 'do_dy': 420, 'tryv': 1.0},
            {'t': 13.7, 'dia': 'skrol', 'do_dy': 380, 'tryv': 1.2},
        ],
        'zvuk': {'muzyka': {'styl': 'epik', 'bpm': 96, 'drop': 3.5}, 'efekty': [
            {'t': 0.0, 'typ': 'udar', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.9, 'typ': 'pop'},
            {'t': 8.3, 'typ': 'pop', 'h': 1.1}, {'t': 10.9, 'typ': 'pop', 'h': 1.2}, {'t': 13.7, 'typ': 'kasa', 'v': 0.6},
            {'t': 15.0, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}],
            'holos': [{'t': 0.2, 'tekst': 'Квартира за два мільйони. А що було на вулиці?', 'holos': 'mykyta'},
                      {'t': 6.0, 'tekst': 'Рік за роком.', 'holos': 'mykyta'},
                      {'t': 13.8, 'tekst': 'Двісті дев\'яносто дев\'ять гривень. Проти двох мільйонів.', 'holos': 'mykyta'}]},
        'pidpys': ['Запис справжнього повного звіту «Моєї вулиці» (тестова оплата). Номер будинку приховано. Лише те, що дійшло до '
                   'суду; звіт не оцінює будинок і нічого не радить.', 'Повний звіт перед купівлею — 299 грн, посилання в профілі.'],
    }


def p4(stan, P, ix):
    """Рієлтор «Мої об'єкти» (799 грн/міс, 5 довідок). Темна."""
    t = tekst_storinky(stan, '/kabinet/', stan['kuky']['rieltor'])
    m = re.search(r'(\d) з (\d) використано', t)
    vyk, vsi = m.groups() if m else ('3', '5')
    c = (30.5160, 50.4410)                     # центр — квартали навколо Лесі Українки (без будинку)
    T = 15.5
    R = vstup('p4', 'temna', {'typ': 'bulbashky', 'z_ref': 14.2}, c, (13.9, 14.3), (20, 35), (0, -15),
              'Клієнт питає:\n*«А що тут поруч?»*', P, radius=2200, maks=22, min_m=420, poriadok='vid_bilshykh')
    return R, {
        'id': '155-p4-rieltor-moi-obiekty', 'tryvalist': T, 'tema': 'temna', 'start': '/kabinet/', 'kuka': 'rieltor',
        'meta': dict(nazva='Рієлтор: «Мої об\'єкти»', typ='Стежу за вулицею · Рієлтор · ОСББ', hrupa='Потреба → продукт',
                     meta='потреба (питання клієнта про місце) → кабінет рієлтора, 5 довідок на місяць, 799 грн/міс',
                     hachok='«Клієнт питає: „А що тут поруч?"» над бульбашками з числом', liniia='Рієлтор',
                     kudy='/oplata/?tovar=rieltor', shar='zapys', riven='mistse', vyhliad='bulbashky (139), темна'),
        'tekst': [
            {'t0': 3.5, 't1': 5.8, 'styl': 'velykyi', 'tekst': 'Кабінет рієлтора:\n*«Мої об\'єкти»*', 'y': 330},
            {'t0': 5.9, 't1': 8.2, 'styl': 'velykyi', 'tekst': f'*{vyk} з {vsi}* довідок\nцього місяця', 'y': 330},
            {'t0': 8.3, 't1': 10.6, 'styl': 'velykyi', 'tekst': 'Кожен об\'єкт —\n*одна кнопка*', 'y': 330},
            {'t0': 10.7, 't1': 13.3, 'styl': 'velykyi', 'tekst': 'Довідка —\n*клієнту за хвилину*', 'y': 330},
            {'t0': 13.4, 't1': 14.4, 'styl': 'velykyi', 'tekst': 'Відповідь —\n*з даними*', 'y': 330},
            {'t0': 14.5, 't1': 15.5, 'styl': 'baner', 'zag': 'Для рієлтора', 'knopka': '799 грн/міс · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 4.0, 'dia': 'skrol', 'do_sel': '#obiekty, h2', 'tryv': 1.2},
            {'t': 6.2, 'dia': 'skrol', 'do_dy': 220, 'tryv': 1.0},
            {'t': 7.4, 'dia': 'skrol', 'do_dy': -120, 'tryv': 0.8},
            {'t': 8.4, 'dia': 'tap', 'sel': 'a[href*="/dovidka/"]'},
            {'t': 9.0, 'dia': 'goto_sel', 'sel': 'a[href*="/dovidka/"]'},
            {'t': 10.7, 'dia': 'skrol', 'do_px': 900, 'tryv': 1.2},
            {'t': 12.2, 'dia': 'skrol', 'do_px': 1300, 'tryv': 1.0},
            {'t': 13.4, 'dia': 'skrol', 'do_px': 1700, 'tryv': 0.9},
        ],
        'zvuk': {'muzyka': {'styl': 'puls', 'bpm': 104}, 'efekty': [
            {'t': 0.0, 'typ': 'pop', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.9, 'typ': 'pop'},
            {'t': 8.4, 'typ': 'klik', 'h': 1.1}, {'t': 10.7, 'typ': 'spovishchennia', 'v': 0.6}, {'t': 14.5, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}],
            'holos': [{'t': 0.2, 'tekst': 'Клієнт питає: а що тут поруч?', 'holos': 'lada'},
                      {'t': 10.8, 'tekst': 'Довідка — клієнту. За хвилину.', 'holos': 'lada'}]},
        'pidpys': ['Запис справжнього кабінету рієлтора «Моєї вулиці» (тестова оплата): об\'єкти й довідки до них. Номери будинків '
                   'приховано. Довідка показує дані, а не оцінку будинку.', 'Для рієлтора — 799 грн/міс, 5 довідок; посилання в профілі.'],
    }


def p5(stan, P, ix):
    """ОСББ: довідка приходить сама щомісяця (1 490 грн/рік). Світла."""
    url = stan['dovidky']['osbb@proba.ua'][0]
    t = tekst_storinky(stan, url)
    m = re.search(r'Місяць:\s*([а-яії]+ \d{4})', t)
    misiats = m.group(1) if m else 'останній місяць'
    c = tochka(ix, stan['budynky']['lesi'])
    c = (c[0] - 0.003, c[1] - 0.002)
    T = 15.5
    R = vstup('p5', 'svitla', {'typ': 'svitni', 'z_ref': 14.4}, c, (14.1, 14.6), (40, 55), (-10, -35),
              'Збори ОСББ.\n*«На що скаржились цього місяця?»*', P, radius=1500)
    return R, {
        'id': '155-p5-osbb-shchomisiatsia', 'tryvalist': T, 'tema': 'svitla', 'start': '/kabinet/', 'kuka': 'osbb',
        'meta': dict(nazva='ОСББ: довідка щомісяця сама', typ='Стежу за вулицею · Рієлтор · ОСББ', hrupa='Потреба → продукт',
                     meta='потреба (звіт правління мешканцям) → щомісячна довідка ОСББ, 1 490 грн/рік',
                     hachok='«Збори ОСББ. „На що скаржились цього місяця?"» над світними точками', liniia='ОСББ',
                     kudy='/osbb/', shar='zvit', vyhliad='svitni (139), світла'),
        'tekst': [
            {'t0': 3.5, 't1': 5.8, 'styl': 'velykyi', 'tekst': 'Кабінет ОСББ:\n*приходить сама*', 'y': 330},
            {'t0': 5.9, 't1': 8.2, 'styl': 'velykyi', 'tekst': 'Щомісяця —\n*увесь оплачений рік*', 'y': 330},
            {'t0': 8.3, 't1': 10.8, 'styl': 'velykyi', 'tekst': f'Зверху —\n*{misiats}*', 'y': 330},
            {'t0': 10.9, 't1': 13.3, 'styl': 'velykyi', 'tekst': 'Поруч зі звичайним\n*місяцем і сусідами*', 'y': 330},
            {'t0': 13.4, 't1': 14.4, 'styl': 'velykyi', 'tekst': 'Готово\n*до зборів*', 'y': 330},
            {'t0': 14.5, 't1': 15.5, 'styl': 'baner', 'zag': 'Для ОСББ', 'knopka': '1 490 грн/рік · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 4.0, 'dia': 'skrol', 'do_sel': '#osbb, h2', 'tryv': 1.2},
            {'t': 6.0, 'dia': 'skrol', 'do_dy': 200, 'tryv': 1.0},
            {'t': 7.6, 'dia': 'tap', 'sel': 'a[href*="/dovidka/"]'},
            {'t': 8.2, 'dia': 'goto', 'url': url},
            {'t': 8.9, 'dia': 'skrol', 'do_tekst': 'Місяць:', 'tryv': 1.2},
            {'t': 10.9, 'dia': 'skrol', 'do_dy': 330, 'tryv': 1.2},
            {'t': 12.4, 'dia': 'skrol', 'do_dy': 260, 'tryv': 0.9},
            {'t': 13.4, 'dia': 'skrol', 'do_dy': 260, 'tryv': 0.9},
        ],
        'zvuk': {'muzyka': {'styl': 'lofi', 'bpm': 100}, 'efekty': [
            {'t': 0.0, 'typ': 'pop', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.9, 'typ': 'spovishchennia', 'v': 0.6},
            {'t': 7.6, 'typ': 'klik', 'h': 1.1}, {'t': 10.9, 'typ': 'pop', 'h': 1.2}, {'t': 14.5, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}]},
        'pidpys': ['Запис справжнього кабінету ОСББ і щомісячної довідки «Моєї вулиці» (тестова оплата). Номер будинку приховано. '
                   'Скарги — звернення до 1551, не перевірені факти.', 'Для ОСББ — 1 490 грн/рік, посилання в профілі.'],
    }


def p6(stan, P, ix):
    """«Судова практика» — як скоро: вітрина й «залиште пошту». Темна, не карта."""
    t = tekst_storinky(stan, '/sudova-praktyka/')
    dni, porohy = kalendar_2025(P)
    T = 13.5
    R = vstup('p6', 'temna', {'typ': 'kalendar', 'zag': '', 'rik': 2025, 'dni': dni, 'porohy': porohy,
                              'maks_den': dni.index(max(dni)), 'tryv': 3.0, 'pid': f'{fp(sum(dni))} за 2025 рік'},
              (30.5234, 50.4501), (10, 10), (0, 0), (0, 0), 'Чим закінчуються\n*такі справи?*', P)
    return R, {
        'id': '155-p6-sudova-praktyka-skoro', 'tryvalist': T, 'tema': 'temna', 'start': '/sudova-praktyka/', 'kuka': None,
        'meta': dict(nazva='«Судова практика» — скоро', typ='Стежу за вулицею · Рієлтор · ОСББ', hrupa='Потреба → продукт',
                     meta='потреба (юрист: чим закінчуються такі справи) → «Судова практика», скоро — залиште пошту',
                     hachok='«Клієнт питає: „Чим такі справи закінчуються?"» над календарем року', liniia='Судова практика',
                     kudy='/sudova-praktyka/', shar='zapys', riven='misto', vyhliad='kalendar (139), темна, не карта',
                     sudova_tekst=t[:400]),
        'tekst': [
            {'t0': 3.5, 't1': 5.8, 'styl': 'velykyi', 'tekst': 'Для юриста —\n*«Судова практика»*', 'y': 330},
            {'t0': 5.9, 't1': 8.2, 'styl': 'velykyi', 'tekst': 'Стаття + суд →\n*чим закінчуються*', 'y': 330},
            {'t0': 8.3, 't1': 10.8, 'styl': 'velykyi', 'tekst': 'Числами —\n*з рішеннями судів*', 'y': 330},
            {'t0': 10.9, 't1': 12.4, 'styl': 'velykyi', 'tekst': '*Скоро.*\nЗалиш пошту', 'y': 330},
            {'t0': 12.5, 't1': 13.5, 'styl': 'baner', 'zag': '«Судова практика» — скоро', 'knopka': PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 4.2, 'dia': 'skrol', 'do_tekst': 'Що тут буде', 'tryv': 1.2},
            {'t': 5.9, 'dia': 'tap', 'sel': 'main li:nth-of-type(1)'},
            {'t': 7.1, 'dia': 'tap', 'sel': 'main li:nth-of-type(2)'},
            {'t': 8.3, 'dia': 'tap', 'sel': 'main li:nth-of-type(3)'},
            {'t': 9.5, 'dia': 'tap', 'sel': 'a[href*="/oplata/"]'},
            {'t': 9.9, 'dia': 'goto_sel', 'sel': 'a[href*="/oplata/"]'},
            {'t': 10.9, 'dia': 'pyshy', 'sel': '#poshta', 'tekst': 'yurist@proba.ua', 'tryv': 1.2},
        ],
        'zvuk': {'muzyka': {'styl': 'napruha', 'bpm': 90}, 'efekty': [
            {'t': 0.0, 'typ': 'bas', 'v': 0.5}, {'t': 3.5, 'typ': 'vzhukh', 'v': 0.6}, {'t': 5.9, 'typ': 'klik'},
            {'t': 7.1, 'typ': 'klik', 'h': 1.1}, {'t': 8.3, 'typ': 'klik', 'h': 1.2}, {'t': 9.5, 'typ': 'klik', 'h': 1.3},
            {'t': 12.5, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}] + [{'t': round(10.9 + i * 0.08, 2), 'typ': 'druk', 'v': 0.4} for i in range(14)]},
        'pidpys': ['Запис справжньої сторінки «Судова практика» «Моєї вулиці» — товар ще не продається, можна залишити пошту. '
                   'Це статистика рішень, а не юридична допомога.', 'Залиш пошту — посилання в профілі.'],
    }


ROLYKY = {'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4, 'p5': p5, 'p6': p6}


# ------------------------------------------------------------------ перевірка всього ролика

def S_rolyka(R: Rolyk, Z: dict) -> tuple[dict, dict]:
    """Один сценарій на весь ролик: вступ (камера, вигляд, гачок) + запис (текст, дії сайту, рамка) — для perevirka.py."""
    S = json.loads(json.dumps(R.S))
    T = Z['tryvalist']
    S['id'], S['tryvalist'], S['tema'] = Z['id'], T, Z['tema']
    for it in S['tekst']:
        it['t1'] = min(it['t1'], VSTUP)
    S['tekst'] += Z['tekst']
    S['ui'] = S.get('ui', []) + [{'t0': VSTUP, 't1': T, 'typ': 'sait'}, {'t0': VSTUP, 't1': T, 'typ': 'ramka'}]
    nov = list(S.get('novynky', [])) + [VSTUP]
    for d in Z['dii']:
        nov.append(d['t'])
        x = d['t']
        while d.get('tryv') and x + 1.5 < d['t'] + d['tryv']:
            x += 1.5
            nov.append(x)
    S['novynky'] = nov
    zv = dict(Z['zvuk'])
    zv['efekty'] = list(R.S['zvuk'].get('efekty', [])) + zv.get('efekty', [])
    S['zvuk'] = zv
    S['pidpys_publikatsii'] = Z['pidpys']
    S['holos_poznaka'] = 'Голос згенеровано' if zv.get('holos') else None
    meta = dict(Z['meta'], id=Z['id'], pravyla=138, kintsivka=PROFIL, pidpys=' '.join(Z['pidpys']))
    meta.pop('sudova_tekst', None)
    return S, meta


def perevir(R, Z) -> list[str]:
    S, meta = S_rolyka(R, Z)
    z = perevirka.pereviryty(S, meta)
    from laboratoriia139 import perevirty_styl
    z += perevirty_styl(S, meta)
    for it in Z['tekst']:
        if it['t0'] < VSTUP - 1e-6:
            z.append(f"текст запису до кінця вступу ({it['t0']} < {VSTUP})")
    return z


# ------------------------------------------------------------------ запис

def zapysaty(brauzer, port, stan, R, Z, kadry=None, vykhid=VYHID, cpu=False):
    zauv = perevir(R, Z)
    if zauv:
        raise SystemExit(f"{Z['id']}: " + '; '.join(zauv))
    T = Z['tryvalist']
    teka_k = vykhid / 'kesh'
    teka_k.mkdir(parents=True, exist_ok=True)
    # 1) вступ рушієм (без звуку — звук один на весь ролик)
    KESH.mkdir(parents=True, exist_ok=True)
    f_vstup = KESH / f"{R.S['id']}.json"
    R.S['kamera'].sort(key=lambda k: k['t'])
    f_vstup.write_text(json.dumps(R.S, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    if kadry is None:
        srv_r = server_rushiia()
        try:
            rendery_rushiia(brauzer, srv_r.server_address[1], f_vstup, FPS, False, None, teka_k)
        finally:
            srv_r.shutdown()
        mp4_vstup = teka_k / f"{R.S['id']}.mp4"
    else:
        srv_r = server_rushiia()
        rendery_rushiia(brauzer, srv_r.server_address[1], f_vstup, FPS, False, [x for x in kadry if x < VSTUP], vykhid)
        srv_r.shutdown()
    # 2) запис сторінок
    holos = bool(Z['zvuk'].get('holos'))
    S_ov = {'tekst': Z['tekst'], 'dzherelo': 'Справжній сайт · тестова оплата · дані — рішення судів',
            'holos_poznaka': 'Голос згенеровано' if holos else None, 'paltsi': []}
    svitla = Z['tema'] == 'svitla'
    kont = brauzer.new_context(viewport={'width': 540, 'height': 960}, device_scale_factor=2,
                               color_scheme='light' if svitla else 'dark')
    if Z.get('kuka'):
        kont.add_cookies([dict(stan['kuky'][Z['kuka']], url=f'http://127.0.0.1:{port}/')])
    kont.add_init_script(ZS.VIRTUALNYI_CHAS)
    kont.add_init_script(ROZMYTTIA)
    s = kont.new_page()
    pomylky = []
    s.on('pageerror', lambda e: pomylky.append(str(e)))
    s.goto(f'http://127.0.0.1:{port}/__vau/zapys.html')
    if svitla:
        s.evaluate("""() => { document.documentElement.setAttribute('data-t', 'svitla');
            document.getElementById('tlo').style.background = 'radial-gradient(ellipse 90% 60% at 50% 30%, #FFFFFF 0%, #E9EBF8 70%)';
            document.getElementById('telefon').style.boxShadow = '0 0 0 5px #C9CCF2, 0 0 0 6px #4447A6, 0 20px 60px rgba(30,32,70,.25)'; }""")
    s.evaluate('s => window.zapusk(s)', S_ov)
    s.evaluate('u => { document.getElementById("sait").src = u; }', Z['start'])
    sait = lambda: s.frames[1]

    def krok(dt_ms, chekaty_ms):
        s.evaluate('dt => { const f = document.getElementById("sait").contentWindow; if (f.__krok) f.__krok(dt); window.__krok && window.__krok(dt); }', dt_ms)
        if chekaty_ms:
            s.wait_for_timeout(chekaty_ms)

    s.wait_for_timeout(2000)
    for _ in range(60):
        krok(50, 40)
    k0 = int(round(VSTUP * FPS))
    n = int(round(T * FPS))
    if kadry is None:
        tykho = teka_k / f"{Z['id']}-zapys.mp4"
        p = subprocess.Popen([ffmpeg(), '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                              '-movflags', '+faststart', str(tykho)], stdin=subprocess.PIPE)
    cdp = kont.new_cdp_session(s)
    dii = sorted(Z['dii'], key=lambda d: d['t'])
    aktyvni = []
    for k in range(k0, n):
        t = k / FPS
        for d in [d for d in dii if d['t'] <= t and not d.get('_zrobleno')]:
            d['_zrobleno'] = True
            vykonaty(s, sait, d, t, krok)
            if d['dia'] in ('skrol', 'pyshy'):
                aktyvni.append(d)
        for d in list(aktyvni):
            k_ = min(1.0, (t - d['t']) / d['tryv'])
            if d['dia'] == 'pyshy':
                sait().evaluate('([sel, v]) => { const e = document.querySelector(sel); if (e) e.value = v; }',
                                [d['sel'], d['tekst'][:max(1, round(len(d['tekst']) * k_))]])
            else:
                y = d['_z'] + (d['_do'] - d['_z']) * (1 - (1 - k_) ** 3)
                sait().evaluate('y => window.scrollTo(0, y)', y)
            if k_ >= 1:
                aktyvni.remove(d)
        krok(1000 / FPS, 25)
        s.evaluate('t => window.kadrZapysu(t)', t)
        if kadry is not None:
            if any(abs(t - x) < 0.5 / FPS for x in kadry):
                (vykhid / 'znimky').mkdir(parents=True, exist_ok=True)
                s.screenshot(path=str(vykhid / 'znimky' / f"{Z['id']}-{t:05.2f}.png"))
            continue
        r = cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 93,     # кадр 1080×1920: вікно 540×960 × 2
                                                     'clip': {'x': 0, 'y': 0, 'width': 540, 'height': 960, 'scale': 2}})
        p.stdin.write(base64.b64decode(r['data']))
        if k % (FPS * 5) == 0:
            print(f"  {Z['id']}: {k}/{n}", flush=True)
    kont.close()
    if pomylky:
        print('помилки сторінки:', pomylky[:3])
    if kadry is not None:
        return None
    p.stdin.close()
    p.wait()
    # 3) склеїти, звук на весь ролик
    S, _ = S_rolyka(R, Z)
    import zvuk
    wav = teka_k / f"{Z['id']}.wav"
    zv = zvuk.zibraty({'tryvalist': T, 'zvuk': S['zvuk']}, wav)
    if zv.get('srt'):
        (vykhid / f"{Z['id']}.srt").write_text(zv['srt'], encoding='utf-8')
    mp4 = vykhid / f"{Z['id']}.mp4"
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(mp4_vstup), '-i', str(tykho), '-i', str(wav),
                    '-filter_complex', '[0:v]scale=1080:1920,setsar=1[a];[1:v]scale=1080:1920,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                    '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-t', str(T),
                    '-movflags', '+faststart', str(mp4)], check=True)
    lehka(mp4, vykhid / 'lehki' / mp4.name, T)
    arkush(mp4, vykhid / 'arkushi' / f"{Z['id']}.jpg", T)
    KESH.mkdir(parents=True, exist_ok=True)
    (KESH / f"{Z['id']}.json").write_text(json.dumps(dict(S, meta=Z['meta']), ensure_ascii=False), encoding='utf-8')
    print(f"{mp4.name}: {T} с", flush=True)
    return mp4


def vykonaty(s, sait, d, t, krok):
    dia = d['dia']
    if dia == 'tap':
        xy = s.evaluate('sel => window.dePalets(sel)', d['sel'])
        if xy:
            s.evaluate('f => window.dodatyPalets(f)', {'t': t, 'x': xy[0], 'y': xy[1]})
    elif dia in ('goto', 'goto_sel'):
        url = d.get('url') or sait().evaluate('sel => { const a = document.querySelector(sel); return a ? a.getAttribute("href") : null; }', d['sel'])
        if not url:
            raise SystemExit(f"немає посилання {d.get('sel')}")
        s.evaluate('u => { document.getElementById("sait").src = u; }', url)
        s.wait_for_timeout(1500)
        for _ in range(12):
            krok(50, 60)
    elif dia == 'js':
        sait().evaluate(d['kod'])
    elif dia == 'skrol':
        d['_z'] = sait().evaluate('() => window.scrollY')
        if d.get('do_sel'):
            d['_do'] = sait().evaluate('sel => { const e = document.querySelector(sel); return e ? Math.max(0, e.getBoundingClientRect().top + window.scrollY - 70) : window.scrollY; }', d['do_sel'])
        elif d.get('do_tekst'):
            d['_do'] = sait().evaluate('''t => { const e = [...document.querySelectorAll('h1,h2,h3,h4')].find(x => x.textContent.includes(t));
                return e ? Math.max(0, e.getBoundingClientRect().top + window.scrollY - 60) : window.scrollY; }''', d['do_tekst'])
        elif d.get('do_dy') is not None:
            d['_do'] = d['_z'] + d['do_dy']
        elif d.get('do_frac') is not None:
            d['_do'] = sait().evaluate('f => Math.round((document.documentElement.scrollHeight - innerHeight) * f)', d['do_frac'])
        else:
            d['_do'] = d['do_px']


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--indeks', type=Path, required=True, help='indeks.json (bot/indeks.py) — точки будинків для вступу')
    a.add_argument('--stan', type=Path, default=VYHID / 'stan.json')
    a.add_argument('--lyshe')
    a.add_argument('--kadry')
    a.add_argument('--pachka', action='store_true', help='лише перевірки всіх роликів і чергування В2')
    a.add_argument('--vykhid', type=Path, default=VYHID)
    a.add_argument('--cpu', action='store_true')
    arg = a.parse_args()
    stan = json.loads(arg.stan.read_text(encoding='utf-8'))
    Proksi.prodazh = stan['server']
    ix = {b['u']: b for b in json.loads(arg.indeks.read_text(encoding='utf-8'))['budynky']}
    P = D.Vypusk(arg.baza).podii
    vybir = arg.lyshe.split(',') if arg.lyshe else PACHKA
    zibrani = {k: ROLYKY[k](stan, P, ix) for k in (PACHKA if arg.pachka else vybir)}
    if 'p2' in zibrani:                     # лист «Стежу» — у рамці як сторінка пошти (той самий HTML, що піде підписнику)
        VYHID.mkdir(parents=True, exist_ok=True)
        (VYHID / 'lyst155.html').write_text(zibrani['p2'][1].pop('lyst'), encoding='utf-8')
    zauv = []
    for k, (R, Z) in zibrani.items():
        zauv += [f'{Z["id"]}: {x}' for x in perevir(R, Z)]
    if arg.pachka:
        zauv += perevirka.pereviryty_pachku([S_rolyka(*zibrani[k]) for k in PACHKA])
        for k in PACHKA:
            S, m = S_rolyka(*zibrani[k])
            print(k, S['tryvalist'], 'с', perevirka.osi(S, m))
        print('\n'.join(zauv) or 'пачка 155: перевірки й В2 — гаразд')
        sys.exit(1 if zauv else 0)
    if zauv:
        sys.exit('\n'.join(zauv))
    Proksi.sait = TUT
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Proksi)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    kadry = [float(x) for x in arg.kadry.split(',')] if arg.kadry else None
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=ARG_CPU if arg.cpu else ARG_GPU)
        for k in vybir:
            R, Z = zibrani[k]
            zapysaty(b, srv.server_address[1], stan, R, Z, kadry, arg.vykhid, arg.cpu)
        b.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
