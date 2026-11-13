"""Картинки «Моєї вулиці» для соцмереж: HTML-шаблон + JSON → PNG (ZAVDANNYA-12).

Один пост чи десятки — одним рядком:
    python brend/zrobyty.py brend/dani/post-tsyfry-kadetskyi-hai.json
Усе разом (аватари, обкладинки, усі приклади з brend/dani/):
    python brend/zrobyty.py --vse
Перевірити дані без малювання:
    python brend/zrobyty.py --perevirka brend/dani/*.json

Формат JSON:  {"shablon": "post-tsyfry", "posty": [ {"nazva": "file", ...поля шаблону...}, ... ]}
Поля кожного шаблону — у brend/README.md. Картинки лягають у brend/hotovi/<shablon>/<nazva>.png
(або в теку з ключем -o).

Перед малюванням дані перевіряються: заборонені слова («безпечно», «рейтинг»…), емодзі,
чутливі категорії (MV-4), номер будинку в місці події (MV-60: лише для публічних місць —
поле typ_mistsia, правило в brend/adresa_pokazu.py), довжина текстів, номер рішення для історій.
Номер будинку прибирається сам (pidhotuvaty) — вручну в даних його стирати не треба. Після малювання — що жоден текст не вилазить за межі картинки.
Потрібні: Python-бібліотека playwright і Chrome (google-chrome або chromium).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adresa_pokazu import (PUBLICHNI, adresa_dlia_pokazu, chutlyva, maie_nomer,  # noqa: E402
                           mozhna_nomer, nevidomyi_typ)

TEKA = Path(__file__).resolve().parent
SHABLONY = TEKA / 'shablony'
HOTOVI = TEKA / 'hotovi'
DANI = TEKA / 'dani'

# Розмір макета в пікселях системи; картинка — вдвічі більша (щільність 2).
ROZMIRY = {
    'avatar': (512, 512),             # 1024×1024
    'youtube': (1280, 720),           # 2560×1440
    'facebook': (820, 312),           # 1640×624
    'post-tsyfry': (540, 675),        # 1080×1350
    'post-istoriya': (540, 675),      # 1080×1350
    'storis-vhadai': (540, 960),      # 1080×1920
    'oblozhka-rolyka': (540, 960),    # 1080×1920
}
SHCHILNIST = 2

# Слова, яких у нас не буває (AGENTS.md, розд. 4; система дизайну, «Голос»; MV-24).
ZABORONENI = ['небезпеч', 'безпечн', 'рейтинг', 'кримінальний район', 'страшн', 'страх', 'криміногенн']
# Чутливі категорії — на всіх рівнях лише числом по соті (MV-4).
CHUTLYVI = ['насильств', 'статев', 'згвалт', 'сексуал', 'розбещ', 'неповнолітн', 'дитин', 'дітей', 'малолітн']
EMODZI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
NOMER_BUDYNKU = re.compile(r'\d')

# Межі довжини (знаків) — щоб текст вміщався великим шрифтом.
MEZHI = {
    'post-tsyfry': {'vulytsya': 34, 'pidpys': 80, 'fakt': 72, 'roky_prymitka': 90},
    'post-istoriya': {'tekst': 230, 'mistse': 36, 'vyd': 40},
    'storis-vhadai': {'tekst': 200, 'pidkazka': 60, 'mistse': 30},
    'oblozhka-rolyka': {'zahalovok': 40, 'pidzahalovok': 90, 'seriya': 30},
}


def ryadky(o, shlyakh=''):
    """Усі текстові значення з їхнім шляхом у JSON."""
    if isinstance(o, str):
        yield shlyakh, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from ryadky(v, f'{shlyakh}.{k}' if shlyakh else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from ryadky(v, f'{shlyakh}[{i}]')


def pidhotuvaty(shablon: str, d: dict) -> dict:
    """Дані, як їх побачить людина: номер будинку — лише для публічного місця (MV-60)."""
    d = json.loads(json.dumps(d))
    if shablon == 'post-istoriya' and d.get('mistse'):
        d['mistse'] = adresa_dlia_pokazu(d['mistse'], d.get('typ_mistsia'), chutlyva(d.get('vyd'), d.get('tekst')))
    if shablon == 'storis-vhadai' and (d.get('vidpovid') or {}).get('mistse'):
        v = d['vidpovid']
        v['mistse'] = adresa_dlia_pokazu(v['mistse'], v.get('typ_mistsia'), chutlyva(d.get('tekst')))
    return d


def _nomer_budynku(p: list[str], kde: str, mistse: str | None, typ: str | None, sprava: bool) -> None:
    if nevidomyi_typ(typ):
        p.append(f'{kde}: невідомий typ_mistsia «{typ}»; публічні: {", ".join(PUBLICHNI)}')
    if mistse and maie_nomer(mistse) and not mozhna_nomer(typ, sprava):
        p.append(f'{kde}: лише вулиця, без номера будинку — номер лише для публічних місць (MV-60)')


def perevirka(shablon: str, d: dict) -> list[str]:
    """Повертає список помилок (порожній — усе гаразд)."""
    p: list[str] = []
    if shablon not in ROZMIRY:
        return [f'невідомий шаблон «{shablon}»; є: {", ".join(ROZMIRY)}']
    for kde, t in ryadky(d):
        if kde in ('nazva', 'adresa_saitu'):
            continue
        n = t.lower()
        for z in ZABORONENI:
            if z in n:
                p.append(f'{kde}: заборонене слово «{z}…» — пишемо, що ставалося і скільки, без оцінки')
        for z in CHUTLYVI:
            if z in n:
                p.append(f'{kde}: схоже на чутливу категорію («{z}…», MV-4) — такі події лише числом по соті')
        if EMODZI.search(t):
            p.append(f'{kde}: емодзі не використовуємо')
    m = MEZHI.get(shablon, {})

    def dovzhyna(kde, t, mezha):
        if t and len(t) > mezha:
            p.append(f'{kde}: {len(t)} знаків, можна до {mezha}')

    if shablon == 'post-tsyfry':
        for k in ('vulytsya', 'pidpys', 'roky_prymitka'):
            dovzhyna(k, d.get(k), m[k])
        if not d.get('vulytsya'):
            p.append('vulytsya: потрібна назва вулиці чи місцевості')
        fakty = d.get('fakty') or []
        if not 1 <= len(fakty) <= 3:
            p.append('fakty: потрібно від 1 до 3 фактів')
        for i, f in enumerate(fakty):
            if 'chyslo' not in f or not f.get('tekst'):
                p.append(f'fakty[{i}]: потрібні chyslo і tekst')
            dovzhyna(f'fakty[{i}].tekst', f.get('tekst'), m['fakt'])
            if len(str(f.get('chyslo', ''))) > 7:
                p.append(f'fakty[{i}].chyslo: до 7 знаків, інакше не вміщується')
        if not d.get('dzherelo'):
            p.append('dzherelo: напишіть, звідки й станом на коли дані («Дані: судові рішення ЄДРСР, станом на …»)')
        for i, r in enumerate(d.get('roky') or []):
            if not isinstance(r.get('podii'), int) or 'rik' not in r:
                p.append(f'roky[{i}]: потрібні rik і podii (ціле число)')
        if len(d.get('roky') or []) > 10:
            p.append('roky: не більше 10 років')
    elif shablon == 'post-istoriya':
        for k in ('tekst', 'mistse', 'vyd'):
            dovzhyna(k, d.get(k), m[k])
        for k in ('tekst', 'mistse', 'rishennya_nomer'):
            if not d.get(k):
                p.append(f'{k}: обов\'язкове поле')
        _nomer_budynku(p, 'mistse', d.get('mistse'), d.get('typ_mistsia'), chutlyva(d.get('vyd'), d.get('tekst')))
        if d.get('rishennya_nomer') and not str(d['rishennya_nomer']).isdigit():
            p.append('rishennya_nomer: лише цифри номера рішення в ЄДРСР')
    elif shablon == 'storis-vhadai':
        dovzhyna('tekst', d.get('tekst'), m['tekst'])
        dovzhyna('pidkazka', d.get('pidkazka'), m['pidkazka'])
        if not d.get('tekst'):
            p.append('tekst: обов\'язкове поле')
        v = d.get('vidpovid')
        if v is not None:
            if not v.get('mistse') or not v.get('rishennya_nomer'):
                p.append('vidpovid: потрібні mistse і rishennya_nomer')
            _nomer_budynku(p, 'vidpovid.mistse', v.get('mistse'), v.get('typ_mistsia'), chutlyva(d.get('tekst')))
            dovzhyna('vidpovid.mistse', v.get('mistse'), m['mistse'])
        if d.get('pidkazka') and NOMER_BUDYNKU.search(d['pidkazka']):
            p.append('pidkazka: без номерів будинків')
    elif shablon == 'oblozhka-rolyka':
        for k in ('zahalovok', 'pidzahalovok', 'seriya'):
            dovzhyna(k, d.get(k), m[k])
        if not d.get('zahalovok'):
            p.append('zahalovok: обов\'язкове поле')
    return p


def znayty_chrome() -> str | None:
    for s in (os.environ.get('MV_CHROME'), shutil.which('google-chrome'), shutil.which('chromium'),
              shutil.which('chromium-browser')):
        if s:
            return s
    return None


# Перевірка після малювання: жоден текстовий блок не вилазить за картинку чи за свою картку.
JS_VYLAZYT = '''() => {
  const p = document.querySelector('.polotno').getBoundingClientRect(), bidy = [];
  document.querySelectorAll('.polotno p, .polotno span, .polotno h1, .polotno .kartka').forEach(el => {
    if (el.closest('[hidden]') || el.classList.contains('maket')) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0) return;
    if (r.bottom > p.bottom + 0.5 || r.right > p.right + 0.5 || r.left < p.left - 0.5 || r.top < p.top - 0.5)
      bidy.push((el.id || el.className) + ' виходить за межі картинки');
    if (el.classList.contains('kartka') && el.scrollHeight > el.clientHeight + 1)
      bidy.push((el.id || el.className) + ': текст не вміщується в картку');
  });
  return bidy;
}'''


class Malyar:
    """Один браузер на всі картинки — десятки постів малюються за секунди."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        chrome = znayty_chrome()
        self.pw = sync_playwright().start()
        kw = {'args': ['--no-sandbox', '--font-render-hinting=none', '--no-first-run',
                          '--disable-background-networking', '--disable-sync', '--disable-component-update']}
        if chrome:
            kw['executable_path'] = chrome
        self.brauzer = self.pw.chromium.launch(**kw)
        return self

    def __exit__(self, *a):
        self.brauzer.close()
        self.pw.stop()

    def namalyuvaty(self, shablon: str, d: dict, kudy: Path) -> list[str]:
        w, h = ROZMIRY[shablon]
        s = self.brauzer.new_page(viewport={'width': w, 'height': h}, device_scale_factor=SHCHILNIST)
        try:
            s.goto((SHABLONY / f'{shablon}.html').as_uri())
            s.evaluate('d => window.pokazaty(d)', d)
            s.evaluate('() => document.fonts.ready')
            # Перевіряємо, що наші шрифти справді завантажилися, а не підмінилися системними.
            # (Аватар без тексту шрифтів не вантажить — тоді перевіряти нічого.)
            shryfty = s.evaluate('''() => !document.body.innerText.trim() ? [] : ['800 20px Plex', '400 16px Plex']
                .filter(f => !document.fonts.check(f, 'Моя вулиця'))''')
            bidy = [f'шрифт не завантажився: {f}' for f in shryfty]
            bidy += s.evaluate(JS_VYLAZYT)
            kudy.parent.mkdir(parents=True, exist_ok=True)
            s.screenshot(path=str(kudy), clip={'x': 0, 'y': 0, 'width': w, 'height': h})
            return bidy
        finally:
            s.close()


def zavantazhyty(shlyakh: Path) -> tuple[str, list[dict]]:
    o = json.loads(shlyakh.read_text(encoding='utf-8'))
    posty = o.get('posty') or [o]
    for i, d in enumerate(posty):
        d.setdefault('nazva', f'{shlyakh.stem}-{i + 1:02d}' if len(posty) > 1 else shlyakh.stem)
    return o['shablon'], posty


def zrobyty_fail(m: Malyar | None, shlyakh: Path, teka: Path | None) -> int:
    shablon, posty = zavantazhyty(shlyakh)
    pomylok = 0
    for i, d in enumerate(posty):
        d = posty[i] = pidhotuvaty(shablon, d)
        p = perevirka(shablon, d)
        if p:
            pomylok += 1
            print(f'ПОМИЛКА {shlyakh.name} / {d["nazva"]}:')
            for x in p:
                print('   ', x)
            continue
        if m is None:
            print(f'гаразд  {shlyakh.name} / {d["nazva"]}')
            continue
        kudy = (teka or HOTOVI / shablon) / f'{d["nazva"]}.png'
        bidy = m.namalyuvaty(shablon, d, kudy)
        if bidy:
            pomylok += 1
            print(f'ПОМИЛКА {kudy.name}: ' + '; '.join(bidy))
        else:
            print(f'готово  {kudy.relative_to(TEKA.parent) if kudy.is_relative_to(TEKA.parent) else kudy}')
    return pomylok


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description='Картинки «Моєї вулиці» для соцмереж: JSON → PNG.')
    a.add_argument('faily', nargs='*', type=Path, help='JSON-файли з даними')
    a.add_argument('--vse', action='store_true', help='намалювати все з brend/dani/')
    a.add_argument('--perevirka', action='store_true', help='лише перевірити дані, без малювання')
    a.add_argument('-o', '--teka', type=Path, help='куди класти картинки (інакше brend/hotovi/<шаблон>/)')
    args = a.parse_args(argv)
    faily = sorted(DANI.glob('*.json')) if args.vse else args.faily
    if not faily:
        a.print_help()
        return 2
    if args.perevirka:
        return 1 if sum(zrobyty_fail(None, f, None) for f in faily) else 0
    with Malyar() as m:
        pomylok = sum(zrobyty_fail(m, f, args.teka) for f in faily)
    return 1 if pomylok else 0


if __name__ == '__main__':
    sys.exit(main())
