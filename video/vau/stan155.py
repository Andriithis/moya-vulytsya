"""Стан місцевого сервера продажу для записів ZAVDANNYA-155: справжні замовлення з тестовою оплатою, справжні довідки.

    node site/worker/testy/mistsevyi.mjs 8799 <тека зібраного сайту>         # сервер продажу (тестова оплата, пам'ять)
    ZVIT_DB=<events.db> ZVIT_SKARGY=<тека 1551> ZVIT_OSM=<kiev.osm.pbf> \\
      python video/vau/stan155.py --server http://127.0.0.1:8799 --vykhid video/vyhid/155/stan.json

Що робить (лише HTTP до сервера, як браузер і видавач; нічого не підробляє в базі):
  1. п'ять покупців оформлюють замовлення й «платять» кнопкою тестової оплати: довідка (орендар), повний звіт (покупець),
     рієлтор (799), ОСББ (1 490), підписка (399);
  2. рієлтор у кабінеті бере довідки на 3 об'єкти, підписник додає будинок у «Стежу»;
  3. видавач (`site/prodazh/vydavach.py`) збирає всі довідки справжнім генератором `dani-edrsr` і віддає серверу;
  4. кожен покупець входить у кабінет листом-посиланням — кука сесії йде у stan.json (для запису екрана).
Пошти — вигадані (@proba.ua), листи лише в журнал місцевого сервера.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]

# Будинки — з пробного випуску 08.11 (сторінки будинків сайту); у кадрі номер прихований (MV-25)
BUDYNKY = {
    'pryozerna': '/budynok/pryozerna/10/',
    'beresteiskyi': '/budynok/beresteiskyi-prospekt/20/',
    'lesi': '/budynok/bulvar-lesi-ukrainky/24/',
    'palladina': '/budynok/prospekt-akademika-palladina/22/',     # «Стежу»: 6 нових подій за жовтень у 300 м
}
POKUPTSI = {
    'orendar': ('orendar@proba.ua', 'dovidka', BUDYNKY['pryozerna']),
    'kupets': ('kupets@proba.ua', 'zvit', BUDYNKY['beresteiskyi']),
    'rieltor': ('rieltor@proba.ua', 'rieltor', None),
    'osbb': ('osbb@proba.ua', 'osbb', BUDYNKY['lesi']),
    'pidpysnyk': ('pidpysnyk@proba.ua', 'pidpyska', None),
}


class BezPereadresatsii(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


VIDKRYVACH = urllib.request.build_opener(BezPereadresatsii)


def zapyt(server, metod, shliakh, forma=None, kuka=None, origin=True, zaholovky=None):
    h = dict(zaholovky or {})
    if origin:
        h['origin'] = server
    if kuka:
        h['cookie'] = kuka
    tilo = urllib.parse.urlencode(forma).encode() if forma is not None else None
    if tilo is not None:
        h['content-type'] = 'application/x-www-form-urlencoded'
    r = urllib.request.Request(server + shliakh, data=tilo, method=metod, headers=h)
    try:
        v = VIDKRYVACH.open(r, timeout=60)
        return v.status, v.read().decode('utf-8', 'replace'), dict(v.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace'), dict(e.headers)


def oplatyty(server, tovar, poshta, budynok=None):
    f = {'tovar': tovar, 'poshta': poshta, 'zghoda': 'tak', 'odrazu': 'tak'}
    if budynok:
        f['budynok'] = budynok
    kod, tekst, zag = zapyt(server, 'POST', '/api/zamovlennia', f)
    kudy = zag.get('Location') or zag.get('location')
    if kod != 303 or not kudy:
        raise SystemExit(f'{poshta}: замовлення {tovar} — код {kod}: {re.sub("<[^>]+>", " ", tekst)[:300]}')
    id_ = re.search(r'/oplata/test/(z[a-z2-7]+)/', kudy).group(1)
    _, tekst, _ = zapyt(server, 'GET', f'/oplata/test/{id_}/')
    for blok in re.findall(r'<form method="post" action="/api/spovishchennia/test">([\s\S]*?)</form>', tekst):
        if 'Оплата пройшла' in blok:
            pola = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', blok))
            kod, _, _ = zapyt(server, 'POST', '/api/spovishchennia/test', pola, origin=False)
            print(f'  {poshta}: {tovar} оплачено ({kod})', flush=True)
            return id_
    raise SystemExit(f'{poshta}: немає кнопки «Оплата пройшла»')


def lysty(server):
    return json.loads(urllib.request.urlopen(server + '/__lysty', timeout=30).read())


def uviity(server, poshta):
    zapyt(server, 'POST', '/kabinet/vkhid', {'poshta': poshta})
    lyst = [x for x in lysty(server) if x['komu'] == poshta and x['tema'].startswith('Вхід')][-1]
    t = re.search(r'\?t=([a-z2-7]+)', lyst['tekst']).group(1)
    _, _, zag = zapyt(server, 'GET', f'/kabinet/vkhid/?t={t}')
    kuka = (zag.get('Set-Cookie') or zag.get('set-cookie')).split(';')[0]
    imia, znach = kuka.split('=', 1)
    return {'name': imia, 'value': znach}


def lyst_html(server, strichka: Path, indeks: Path, period: str, kudy: Path):
    """Лист «Нове біля дому» підписнику — той самий збирач, що в site/prodazh/lyst_stezhu.py (черга сервера, стрічка
    місяця з dani-edrsr/src/nove_tyzhnia.py --dniv 30), але в HTML-вигляді листа (lyst.html_lysta) і нікому не надсилається."""
    sys.path.insert(0, str(KORIN / 'lyst'))
    sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))
    import lyst as L
    import lyst_stezhu as LS
    from vydavach import zapyt as zapyt_v
    _, tilo = zapyt_v(server, os.environ.get('VYDACHA_KLIUCH', 'mistsevyi-vydavach'), 'GET',
                      f'/api/vnutr/stezhu?period={urllib.parse.quote(period)}')
    ix = json.loads(indeks.read_text(encoding='utf-8'))
    tochky = {b['u']: b for b in ix['budynky']}
    st = json.loads(strichka.read_text(encoding='utf-8'))
    for x in json.loads(tilo)['pidpysnyky']:
        adresy = [L.Adresa(a['adresa'], tochky[a['budynok']]['la'], tochky[a['budynok']]['lo']) for a in x['adresy'] if a['budynok'] in tochky]
        l = L.zibraty(st, L.Pidpysnyk(x['id'], 'pidpyska', adresy, tykhyi_lyst=True))
        if l is None:
            continue
        pos = LS.posylannia(server)
        if L.vady_tekstu(L.tekst(l, pos)):
            raise SystemExit('лист не пройшов перевірку слів')
        kudy.parent.mkdir(parents=True, exist_ok=True)
        kudy.write_text(L.html_lysta(l, pos), encoding='utf-8')
        print(f'лист: {L.tema(l)} → {kudy}')
        return L.tema(l)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--server', default='http://127.0.0.1:8799')
    a.add_argument('--vykhid', type=Path, default=KORIN / 'video' / 'vyhid' / '155' / 'stan.json')
    a.add_argument('--bez-vydavacha', action='store_true', help='не збирати довідки (лише замовлення)')
    a.add_argument('--lyst', nargs=3, metavar=('STRICHKA', 'INDEKS', 'PERIOD'),
                   help='лише лист «Стежу» в HTML (стан сервера вже є): nove-<дата>.json indeks.json РРРР-ММ')
    arg = a.parse_args()
    s = arg.server.rstrip('/')
    if arg.lyst:
        stan = json.loads(arg.vykhid.read_text(encoding='utf-8'))
        stan['lyst'] = {'tema': lyst_html(s, Path(arg.lyst[0]), Path(arg.lyst[1]), arg.lyst[2], arg.vykhid.parent / 'lyst-stezhu.html'),
                        'fail': 'lyst-stezhu.html'}
        arg.vykhid.write_text(json.dumps(stan, ensure_ascii=False, indent=1), encoding='utf-8')
        return
    for kh, (poshta, tovar, budynok) in POKUPTSI.items():
        oplatyty(s, tovar, poshta, budynok)
    kuky = {kh: uviity(s, p) for kh, (p, _, _) in POKUPTSI.items()}
    k = lambda kh: f"{kuky[kh]['name']}={kuky[kh]['value']}"
    for b in ('beresteiskyi', 'pryozerna', 'lesi'):          # рієлтор: 3 з 5 об'єктів
        kod, tekst, _ = zapyt(s, 'POST', '/kabinet/dovidka', {'budynok': BUDYNKY[b]}, kuka=k('rieltor'))
        print(f'  рієлтор: {b} — {kod}', flush=True)
    zapyt(s, 'POST', '/kabinet/stezhu', {'budynok': BUDYNKY['palladina']}, kuka=k('pidpysnyk'))
    if not arg.bez_vydavacha:
        env = dict(os.environ, VYDACHA_KLIUCH=os.environ.get('VYDACHA_KLIUCH', 'mistsevyi-vydavach'))
        subprocess.run([sys.executable, str(KORIN / 'site' / 'prodazh' / 'vydavach.py'), '--server', s, '--do-porozhnoi',
                        '--dani-edrsr', str(KORIN.parent / 'dani-edrsr')], env=env, check=True)
    dovidky = {}
    for l in lysty(s):
        for u in re.findall(r'(/dovidka/d[a-z2-7]+/?\?k=[A-Za-z0-9_-]+)', l.get('tekst', '')):
            dovidky.setdefault(l['komu'], []).append(u)
    stan = {'server': s, 'kuky': kuky, 'dovidky': dovidky, 'budynky': BUDYNKY}
    arg.vykhid.parent.mkdir(parents=True, exist_ok=True)
    arg.vykhid.write_text(json.dumps(stan, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dovidky, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
