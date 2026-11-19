"""Викладка сайту «Моя вулиця» на Cloudflare Workers одним запуском (ZAVDANNYA-132; покроково — docs/ZAPUSK-SAITU.md).

    python site/vyklasty.py <тека випуску або events-<дата>.db[.xz]> [--dani-edrsr ../dani-edrsr] [--suho]

Що робить, по черзі (зупиняється на першій помилці й пише, що не так):
  1. перевіряє змінні середовища (нижче) і знаходить файли випуску в теці: events-*.db (або .db.xz — розпаковує),
     budynky*.json, perekazy*.json, sudova-praktyka*.json, koloda*.json — що є, те й бере; чого немає — сайт без цього
     розділу (код міняти не треба: пробний випуск 08.11 і повний Київ збираються однаково);
  2. збирає сайт (site/zibraty_sait.py --khostynh workers) у робочу теку;
  3. створює таблиці бази D1, яких ще немає (skhema.sql — лише CREATE … IF NOT EXISTS, дані не зачіпає);
  4. викладає (`npx wrangler deploy`): сайт, скрипт Workers, свій домен;
  5. перевіряє живий сайт: головна, карта, robots.txt, карта сайту, «Про дані», оплата/«скоро», оферта без
     незаповнених місць, форма (тестовий запис з каналом «perevirka»), будинок.

З --suho — лише кроки 1–2 і `wrangler deploy --dry-run`: нічого не створює й не викладає (перевірка на своєму ПК).

Змінні середовища (ключі — ЛИШЕ тут або в секретах GitHub/Cloudflare, ніколи у файлах):
  CLOUDFLARE_API_TOKEN   токен Cloudflare партнера (шаблон «Edit Cloudflare Workers» + права D1 Edit); читає сам wrangler
  CLOUDFLARE_ACCOUNT_ID  ідентифікатор акаунта (якщо токен бачить кілька акаунтів)
  MV_DOMEN               moyavulytsya.com.ua (без https://)
  MV_D1                  ідентифікатор бази D1 (`npx wrangler d1 create moya-vulytsya-prodazh`)
  MV_OPLATA              skoro (типово: «Скоро — залиште пошту») | tak (справжня оплата)
  MV_PLATIZHNYI_SERVIS   liqpay | mono | test — потрібен лише з MV_OPLATA=tak
  MV_LIQPAY_SANDBOX      tak — пісочниця LiqPay (гроші не списуються); прибрати перед справжнім продажем
  MV_POSHTA_SERVIS       zahlushka (типово: листи не йдуть) | http-json (напр. Resend; ключ — секрет POSHTA_KLIUCH)
  MV_POSHTA_PARTNERA     куди писати про нові звернення, невдалі довідки, чужі суми
  MV_POSHTA_VID, MV_POSHTA_URL   відправник і адреса сервісу листів (для http-json)
  MV_CF_ANALITYKA        публічний токен Cloudflare Web Analytics (лічба відвідувань без кукі); порожньо — без лічби
  MV_ZAPOVNENNYA         шлях до JSON з даними партнера для оферти й політики ({"ВЛАСНИК": "…", …}); без нього
                         викладка зупиняється (оферта з [ВЛАСНИК] — не публікуємо). У --suho можна без нього.
"""
from __future__ import annotations

import argparse
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DZHERELO = Path(__file__).resolve().parent
KORIN = DZHERELO.parent
sys.path.insert(0, str(DZHERELO))
sys.path.insert(0, str(DZHERELO / 'sait'))
sys.path.insert(0, str(DZHERELO / 'zahlushka'))

WRANGLER = ['npx', '--yes', 'wrangler@4']
NAZVA_BAZY = 'moya-vulytsya-prodazh'          # як у site/khostynh.py: f'{nazva}-prodazh'
DOMEN = re.compile(r'^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$')
D1_ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


class Zupynka(Exception):
    """Зупинитися з поясненням для людини."""


def krok(n: int, tekst: str) -> None:
    print(f'\n== {n}. {tekst}', flush=True)


# ---------------------------------------------------------------- 1. змінні й файли випуску

def zminni(suho: bool) -> dict:
    e = os.environ
    z = {
        'domen': e.get('MV_DOMEN', '').strip().lower().removeprefix('https://').rstrip('/'),
        'd1': e.get('MV_D1', '').strip(),
        'oplata': e.get('MV_OPLATA', 'skoro').strip() or 'skoro',
        'servis': e.get('MV_PLATIZHNYI_SERVIS', '').strip() or None,
        'poshta': e.get('MV_POSHTA_SERVIS', 'zahlushka').strip() or 'zahlushka',
        'analityka': e.get('MV_CF_ANALITYKA', '').strip(),
        'karta': e.get('MV_KARTA_R2', '').strip() == 'tak',   # карта підписника зі сховища R2 (docs/PLATNA-CHASTYNA.md)
        'zapovnennya': e.get('MV_ZAPOVNENNYA', '').strip(),
        'vars': {k: e.get(f'MV_{k}', '').strip() for k in ('POSHTA_PARTNERA', 'POSHTA_VID', 'POSHTA_URL', 'LIQPAY_SANDBOX')},
    }
    pomylky = []
    if z['oplata'] not in ('skoro', 'tak'):
        pomylky.append(f'MV_OPLATA={z["oplata"]!r}: має бути skoro або tak')
    if z['oplata'] == 'tak' and z['servis'] not in ('liqpay', 'mono', 'test'):
        pomylky.append('MV_OPLATA=tak: потрібен MV_PLATIZHNYI_SERVIS (liqpay | mono | test)')
    if z['poshta'] not in ('zahlushka', 'http-json'):
        pomylky.append('MV_POSHTA_SERVIS: zahlushka або http-json')
    if z['domen'] and not DOMEN.match(z['domen']):
        pomylky.append(f'MV_DOMEN={z["domen"]!r}: лише домен, напр. moyavulytsya.com.ua')
    if z['d1'] and not D1_ID.match(z['d1']):
        pomylky.append('MV_D1: ідентифікатор бази виду xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (wrangler d1 create / d1 list)')
    if not suho:
        for k, n in (('domen', 'MV_DOMEN'), ('d1', 'MV_D1'), ('zapovnennya', 'MV_ZAPOVNENNYA')):
            if not z[k]:
                pomylky.append(f'не задано {n}')
        if not e.get('CLOUDFLARE_API_TOKEN'):
            pomylky.append('не задано CLOUDFLARE_API_TOKEN (токен Cloudflare партнера)')
    if z['zapovnennya'] and not Path(z['zapovnennya']).is_file():
        pomylky.append(f'MV_ZAPOVNENNYA: файлу {z["zapovnennya"]} немає')
    if pomylky:
        raise Zupynka('Змінні середовища:\n  - ' + '\n  - '.join(pomylky))
    if not z['domen']:
        z['domen'] = 'moyavulytsya.com.ua'      # лише для --suho: адреси в карті сайту
    if not z['d1'] and suho:
        z['d1'] = '00000000-0000-0000-0000-000000000000'
    return z


def ostannii(teka: Path, vzirets: str, bez: str = 'probnyi-') -> Path | None:
    """Найновіший файл за назвою (дата в назві); «пробні» — лише якщо інших немає."""
    vsi = sorted(teka.glob(vzirets))
    spravzhni = [f for f in vsi if not f.name.startswith(bez)]
    return (spravzhni or vsi or [None])[-1]


def faily_vypusku(vkhid: Path, robocha: Path, dani_edrsr: Path | None) -> dict:
    if vkhid.is_file():
        teka, baza = vkhid.parent, vkhid
    elif vkhid.is_dir():
        teka = vkhid
        baza = ostannii(teka, 'events-*.db') or ostannii(teka, 'events-*.db.xz')
    else:
        raise Zupynka(f'Немає {vkhid}: дайте теку випуску або файл events-<дата>.db')
    if baza is None:
        raise Zupynka(f'У {teka} немає events-*.db чи events-*.db.xz')
    if baza.suffix == '.xz':
        rozp = robocha / baza.name[:-3]
        if not rozp.exists() or rozp.stat().st_mtime < baza.stat().st_mtime:
            print(f'   розпаковую {baza.name} …', flush=True)
            with lzma.open(baza) as vh, open(str(rozp) + '.chast', 'wb') as out:
                shutil.copyfileobj(vh, out, 1 << 22)
            os.replace(str(rozp) + '.chast', rozp)
        baza = rozp
    f = {'baza': baza, 'budynky': ostannii(teka, 'budynky*.json'), 'perekazy': ostannii(teka, 'perekazy*.json'),
         'sudova_praktyka': ostannii(teka, 'sudova-praktyka*.json'), 'koloda': ostannii(teka, 'koloda*.json'),
         'pereimenuvannya': None}
    if dani_edrsr and (dani_edrsr / 'config' / 'pereimenuvannia-kyiv.csv').is_file():
        f['pereimenuvannya'] = dani_edrsr / 'config' / 'pereimenuvannia-kyiv.csv'
    if f['koloda'] is not None:       # колода гри — лише якщо проходить перевірку для публікації (MV-12), інакше без гри
        import zibraty as zahlushka
        K = zahlushka.koloda_hry
        try:
            K.dlya_publikatsiyi(K.pidhotuvaty(K.prochytaty(f['koloda'])))
        except Exception as pomylka:      # noqa: BLE001 — будь-яка вада колоди = сайт без гри, а не зупинка
            print(f'   увага: колоду {f["koloda"].name} не взято ({pomylka}) — сайт без гри', flush=True)
            f['koloda'] = None
    for k, v in f.items():
        print(f'   {k:16} {v if v else "— немає (розділу не буде)"}', flush=True)
    return f


# ---------------------------------------------------------------- 2. збирання

def zibraty(f: dict, z: dict, robocha: Path) -> dict:
    import zibraty_sait as ZS
    vykhid = robocha / 'sait'
    prodazh = {'d1': z['d1'], 'servis': z['servis'] if z['oplata'] == 'tak' else None,
               'adresa': f'https://{z["domen"]}', 'poshta': z['poshta'], 'vars': z['vars'], 'karta': z.get('karta', False)}
    zapovnennya = json.loads(Path(z['zapovnennya']).read_text(encoding='utf-8')) if z['zapovnennya'] else None
    zvit = ZS.zibraty_sait(f['baza'], vykhid, f['pereimenuvannya'], KORIN / 'data' / 'borders.json',
                           adresa_saitu=f'https://{z["domen"]}', koloda=f['koloda'], budynky=f['budynky'],
                           khostynh='workers', perekazy=f['perekazy'], sudova_praktyka=f['sudova_praktyka'],
                           prodazh=prodazh, oplata=z['oplata'], zapovnennya=zapovnennya,
                           dlya_publikatsiyi=bool(zapovnennya), cf_analityka=z['analityka'], domen=z['domen'])
    for k in ('versiia', 'vulyts', 'budynkiv', 'mistsia', 'failiv', 'adres_u_sitemap', 'oplata', 'formy', 'nezapovneno', 'analityka'):
        print(f'   {k:18} {zvit.get(k)}', flush=True)
    return zvit


# ---------------------------------------------------------------- 3–4. база й викладка

def wrangler(args: list, teka: Path) -> None:
    if not shutil.which('npx'):
        raise Zupynka('Немає npx: встановіть Node.js 22 LTS (nodejs.org) і запустіть ще раз.')
    print('   $ wrangler ' + ' '.join(args), flush=True)
    r = subprocess.run(WRANGLER + args, cwd=teka)
    if r.returncode:
        raise Zupynka(f'wrangler {args[0]} завершився з помилкою {r.returncode} (повідомлення — вище).')


# ---------------------------------------------------------------- 5. перевірка живого сайту

def vidkryty(url: str, metod: str = 'GET', tilo: bytes | None = None, zaholovky: dict | None = None):
    zap = urllib.request.Request(url, data=tilo, method=metod, headers={'user-agent': 'moya-vulytsya-perevirka', **(zaholovky or {})})
    try:
        with urllib.request.urlopen(zap, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e)


def perevirky(adresa: str, oplata: str, budynok: str | None) -> list[tuple[str, bool, str]]:
    """Автоматична частина «що перевірити після» (docs/ZAPUSK-SAITU.md, розд. 6). Повертає (що, ok, деталі)."""
    rez = []

    def p(nazva, shliakh, umova, **kw):
        st, t = vidkryty(adresa + shliakh, **kw)
        ok, chomu = umova(st, t)
        rez.append((nazva, ok, f'{st} {chomu}'.strip()))

    p('головна', '/', lambda s, t: (s == 200 and 'Моя вулиця' in t, ''))
    p('карта', '/karta/', lambda s, t: (s == 200, ''))
    p('robots.txt', '/robots.txt', lambda s, t: (s == 200 and f'Sitemap: {adresa}/sitemap.xml' in t and 'Disallow: /api/' in t, ''))
    p('карта сайту', '/sitemap.xml', lambda s, t: (s == 200 and '<loc>' in t, f'{t.count("<loc>")} адрес'))
    p('«Про дані» (П4)', '/pro-dani/', lambda s, t: (s == 200 and 'не набрали законної сили' in t, ''))
    if oplata == 'skoro':
        p('«Скоро — залиште пошту»', '/oplata/?tovar=dovidka', lambda s, t: (s == 200 and 'action="/api/skoro"' in t, ''))
        p('кабінету немає (скоро)', '/kabinet/', lambda s, t: (s == 404, ''))
    else:
        p('оплата: галочка П6', '/oplata/?tovar=pidpyska', lambda s, t: (s == 200 and 'name="odrazu"' in t, ''))
        p('кабінет', '/kabinet/', lambda s, t: (s == 200 and 'Кабінет' in t, ''))
    p('оферта заповнена', '/zahlushka/oferta.html',
      lambda s, t: (s == 200 and not re.search(r"\[[А-ЯІЇЄҐ][А-ЯІЇЄҐ ,'’-]*\]", t), 'є [НЕЗАПОВНЕНЕ]' if '[' in t else ''))
    p('форма → база', '/api/forma/podiya', lambda s, t: (s == 201, ''), metod='POST',
      tilo=json.dumps({'nazva': 'pryishly', 'kanal': 'perevirka'}).encode(),
      zaholovky={'content-type': 'application/json', 'origin': adresa})
    if budynok:
        p('сторінка будинку', budynok, lambda s, t: (s == 200 and '<h1>' in t, budynok))
    return rez


def pershyi_budynok(sait: Path) -> str | None:
    """Адреса однієї сторінки будинку із зібраного пошуку будинків (vulytsi/budynky.json); немає будинків — None."""
    try:
        for _nazva, _slug, _stari, budynky in json.loads((sait / 'vulytsi' / 'budynky.json').read_text(encoding='utf-8')):
            if budynky:
                return budynky[0][1]
    except (OSError, ValueError, TypeError, IndexError):
        pass
    return None


# ---------------------------------------------------------------- головне

def main(argv=None) -> int:
    a = argparse.ArgumentParser(description='Викласти сайт «Моя вулиця» на Cloudflare Workers (docs/ZAPUSK-SAITU.md).')
    a.add_argument('vypusk', type=Path, help='тека з файлами випуску або сам events-<дата>.db[.xz]')
    a.add_argument('--dani-edrsr', type=Path, default=KORIN.parent / 'dani-edrsr', help='репозиторій конвеєра (довідник перейменувань)')
    a.add_argument('--robocha', type=Path, default=KORIN / '_vykladka', help='робоча тека (зібраний сайт; не в git)')
    a.add_argument('--suho', action='store_true', help='лише зібрати й перевірити викладку (--dry-run), нічого не міняти')
    a.add_argument('--bez-perevirky', action='store_true', help='не перевіряти живий сайт після викладки')
    x = a.parse_args(argv)
    try:
        krok(1, 'Змінні й файли випуску')
        z = zminni(x.suho)
        print(f'   домен {z["domen"]} · оплата {z["oplata"]}' + (f' ({z["servis"]})' if z['oplata'] == 'tak' else '')
              + f' · листи {z["poshta"]} · лічба {"так" if z["analityka"] else "ні"}', flush=True)
        x.robocha.mkdir(parents=True, exist_ok=True)
        f = faily_vypusku(x.vypusk, x.robocha, x.dani_edrsr if x.dani_edrsr.is_dir() else None)

        krok(2, 'Збирання сайту')
        zvit = zibraty(f, z, x.robocha)
        if zvit.get('nezapovneno') and not x.suho:
            raise Zupynka('В оферті чи політиці лишились незаповнені місця — див. MV_ZAPOVNENNYA.')
        teka_w = Path(zvit['teka_workera'])
        shutil.copyfile(DZHERELO / 'worker' / 'prodazh' / 'skhema.sql', teka_w / 'skhema.sql')

        if x.suho:
            krok(3, 'Пробна викладка (нічого не змінюється)')
            wrangler(['deploy', '--dry-run', '--outdir', str(x.robocha / 'dry-run')], teka_w)
            print(f'\nГотово (сухо). Сайт — {x.robocha / "sait"}; переглянути: python -m http.server -d {x.robocha / "sait"}')
            return 0

        krok(3, f'Таблиці бази {NAZVA_BAZY} (лише відсутні)')
        wrangler(['d1', 'execute', NAZVA_BAZY, '--remote', '--yes', '--file', 'skhema.sql'], teka_w)
        krok(4, 'Викладка')
        wrangler(['deploy'], teka_w)
        if x.bez_perevirky:
            return 0
        krok(5, 'Перевірка живого сайту')
        rez = perevirky(f'https://{z["domen"]}', z['oplata'], pershyi_budynok(x.robocha / 'sait'))
        for nazva, ok, det in rez:
            print(f'   {"✓" if ok else "✗"} {nazva:26} {det}')
        pohani = [r for r in rez if not r[1]]
        if pohani:
            print(f'\n{len(pohani)} перевірок не пройшло. Новий домен може запрацювати за кілька хвилин — запустіть ще раз '
                  'з тим самим випуском; якщо не минає — docs/ZAPUSK-SAITU.md, розд. 7 (відкат).')
            return 2
        print('\nВикладено й перевірено. Решта перевірок — очима, docs/ZAPUSK-SAITU.md, розд. 6.')
        return 0
    except Zupynka as e:
        print(f'\nЗУПИНЕНО: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
