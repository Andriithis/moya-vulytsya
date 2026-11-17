"""Сторінка-перегляд опублікованого (MV-114, ZAVDANNYA-107, п. 3).

Андрій відкриває посилання, вводить пароль (змінна MV_PEREHLIAD_PAROL на сервері) і бачить, що вийшло за тиждень —
по мережах і каналах, з прев'ю. Кнопка «Прибрати» з причиною: сервіс видаляє допис через інтерфейс мережі, причину пише
в журнал і більше такої події / ролика / (за галочкою) місця не публікує. Доступу до акаунтів Андрій не має.

Сервер — стандартна бібліотека Python, один потік (одна людина), слухає 127.0.0.1; назовні — через HTTPS-проксі партнера (Caddy чи Nginx),
`docs/AVTOPOSTYNH.md`, крок 8. Вхід: пароль → кука з підписом (HMAC) на 30 днів; форми — з токеном від підробки запиту.
Той самий вигляд без кнопок — `perehliad.html` у теці пачки (пробний режим).
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import mimetypes
import os
import time
from collections import defaultdict
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import cherha as C
import rozklad as R

MEREZHI_NAZVY = {'telegram': 'Telegram', 'youtube': 'YouTube', 'facebook': 'Facebook', 'instagram': 'Instagram',
                 'tiktok': 'TikTok'}
STANY = {'chekaie': 'у черзі', 'opublikovano': 'вийшло', 'vidkhyleno': 'не пройшло перевірку', 'pomylka': 'помилка',
         'propushcheno': 'пропущено', 'prybrano': 'прибрано', 'prybraty_vruchnu': 'прибрати вручну (партнер)'}
PRYCHYNY = ['видно номер будинку чи людину', 'неточно або більше, ніж у рішенні', 'лякає чи ранжує', 'не те місце',
            'нецікаво', 'інше']
KUKA = 'mv_perehliad'
TYPY = {'dopys': 'допис', 'vikteryna': 'вікторина', 'rolyk': 'ролик', 'kartka': 'картка'}
HRUPY = {**R.HRUPY, 'istoriia': 'історія з вулиці', 'vhadai': '«Вгадай, де це було?»', 'tsyfry': 'цифри'}

CSS = """
:root{--ground:#F4F5FB;--surface:#FFF;--tint:#EDEFFE;--ink:#1C1E2D;--muted:#5F6275;--line:#DFE1E9;--accent:#4447A6;
--accent-soft:#DFE3FC;--vyd:#3C3CA1;--mint:#31B88D}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 'IBM Plex Sans',system-ui,sans-serif;background:var(--ground);color:var(--ink)}
header{padding:16px 20px;background:var(--surface);border-bottom:1px solid var(--line)}
h1{font-size:20px;margin:0 0 4px}h2{font-size:17px;margin:24px 0 8px}h3{font-size:15px;margin:16px 0 6px;color:var(--muted)}
main{padding:0 20px 40px;max-width:1100px;margin:auto}.pidpys{color:var(--muted);font-size:13px}
nav a,.knopka{display:inline-block;padding:6px 12px;margin:4px 4px 0 0;border:1px solid var(--accent);border-radius:8px;
color:var(--accent);text-decoration:none;background:var(--surface)}nav a.tut{background:var(--accent);color:#fff}
.sitka{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.kartka{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px}
.kartka.vidkhyleno,.kartka.pomylka,.kartka.prybraty_vruchnu{border:2px solid var(--vyd)}
.kartka.prybrano,.kartka.propushcheno{opacity:.55}
.tekst{white-space:pre-wrap;font-size:14px;background:var(--tint);border-radius:8px;padding:8px;margin:8px 0;max-height:260px;overflow:auto}
.stan{font-weight:600}.stan.opublikovano{color:var(--mint)}.stan.vidkhyleno,.stan.pomylka,.stan.prybraty_vruchnu{color:var(--vyd)}
img,video{max-width:100%;max-height:360px;border-radius:8px;display:block;margin:6px 0}
.zauv{color:var(--vyd);font-weight:600;font-size:13px}details{margin-top:8px}
select,input[type=text],input[type=password]{font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;width:100%;margin:4px 0}
button{font:inherit;padding:6px 14px;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
.zupyn{background:var(--accent-soft);border-radius:8px;padding:8px 12px;margin:8px 0}
table{border-collapse:collapse;font-size:13px;width:100%}td{border-bottom:1px solid var(--line);padding:4px 6px;vertical-align:top}
"""


def e(t) -> str:
    return html.escape(str(t if t is not None else ''))


def pidpys(parol: str, shcho: str) -> str:
    return hmac.new(parol.encode('utf-8'), shcho.encode('utf-8'), hashlib.sha256).hexdigest()


def prevyu(o: dict, media_url: str) -> str:
    r = []
    if o.get('fail'):
        src = f'{media_url}/{quote(o["fail"])}'
        r.append(f'<video src="{e(src)}" controls preload="metadata"></video>' if o['typ'] == 'rolyk'
                 else f'<img src="{e(src)}" alt="картка">')
    if o.get('nazva'):
        r.append(f'<b>{e(o["nazva"])}</b>')
    if o['typ'] == 'vikteryna':
        r.append(f'<div class="tekst">Вікторина: {e(o["pytannia"])}\n' +
                 '\n'.join(f'{"✓" if i == o["pravylna"] else "·"} {e(v)}' for i, v in enumerate(o['varianty'])) +
                 f'\n\nПояснення: {e(o.get("poiasnennia", ""))}</div>')
    else:
        r.append(f'<div class="tekst">{e(o.get("tekst", ""))}</div>')
    for k in o.get('knopky') or []:
        r.append(f'<a class="knopka" href="{e(k["url"])}" target="_blank" rel="noopener">{e(k["tekst"])}</a>')
    return '\n'.join(r)


def kartka(o: dict, media_url: str, statychna: bool, csrf: str, tyzhden: str) -> str:
    st = o['stan']
    r = [f'<div class="kartka {st}" id="o-{e(o["id"])}">',
         f'<div class="pidpys">{e(R.po_kyievu(o["chas"]))} · {e(TYPY.get(o["typ"], o["typ"]))} · {e(HRUPY.get(o.get("hrupa", ""), o.get("hrupa", "")))}</div>',
         f'<div class="stan {st}">{e(STANY.get(st, st))}'
         + (f' · <a href="{e(o["url_dopysu"])}" target="_blank" rel="noopener">відкрити допис</a>'
            if o.get('url_dopysu') else '') + '</div>']
    if o.get('zauvazhennia'):
        r.append('<div class="zauv">' + '<br>'.join(e(z) for z in o['zauvazhennia']) + '</div>')
    r.append(prevyu(o, media_url))
    if not statychna and st in ('opublikovano', 'chekaie'):
        opts = ''.join(f'<option>{e(p)}</option>' for p in PRYCHYNY)
        dod = ('<label><input type="checkbox" name="usi_merezhi" value="1" checked> і з інших мереж (той самий ролик)'
               '</label><br>' if o.get('pozytsiia') else '')
        r.append(f'<details><summary>Прибрати</summary><form method="post" action="/prybraty">'
                 f'<input type="hidden" name="id" value="{e(o["id"])}"><input type="hidden" name="csrf" value="{csrf}">'
                 f'<input type="hidden" name="tyzhden" value="{e(tyzhden)}">'
                 f'<select name="prychyna">{opts}</select><input type="text" name="dokladno" placeholder="Коротко, що не так">'
                 f'{dod}<label><input type="checkbox" name="mistse" value="1"> і більше не писати про це місце</label><br>'
                 f'<button type="submit">Прибрати</button></form></details>')
    r.append('</div>')
    return '\n'.join(r)


def storinka(sv, tyzhden: str | None = None, statychna: bool = False, media_url: str = '/media', csrf: str = '',
             povidomlennia: str = '') -> str:
    tyzhni = sv.q.tyzhni()
    if not tyzhden:
        tyzhden = R.nazva_tyzhnia(R.ponedilok(C.teper().astimezone(R.KYIV).date()))
        if tyzhden not in tyzhni and tyzhni:
            tyzhden = tyzhni[0]
    vsi = sv.q.vsi(tyzhden)
    lich = defaultdict(int)
    for o in vsi:
        lich[o['stan']] += 1
    ch = [f'<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" '
          f'content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">'
          f'<title>Перегляд опублікованого · {e(tyzhden)}</title><style>{CSS}</style></head><body>',
          '<header><h1>Що вийшло в мережах · Моя вулиця</h1>',
          f'<div class="pidpys">Тиждень {e(tyzhden)} · ' + ' · '.join(f'{e(STANY.get(k, k))}: {n}' for k, n in sorted(lich.items()))
          + (' · <b>пробний режим — у мережі нічого не пішло</b>' if sv.probnyi else '') + '</div>']
    if not statychna and tyzhni:
        ch.append('<nav>' + ''.join(f'<a href="/?tyzhden={e(t)}" class="{"tut" if t == tyzhden else ""}">{e(t)}</a>'
                                    for t in tyzhni[:8]) + '</nav>')
    ch.append('</header><main>')
    if povidomlennia:
        ch.append(f'<div class="zupyn">{e(povidomlennia)}</div>')
    for z in sv.q.stan_merezh():
        if z.get('zupyneno_do') and z['zupyneno_do'] > C.iso(C.teper()):
            ch.append(f'<div class="zupyn"><b>{e(MEREZHI_NAZVY.get(z["merezha"]))} зупинено</b>: {e(z["prychyna"])}. '
                      'Партнер розбирається; після — команда «vidnovyty».</div>')
    po_merezhi = defaultdict(lambda: defaultdict(list))
    for o in vsi:
        po_merezhi[o['merezha']][o.get('kanal') or ''].append(o)
    for m in MEREZHI_NAZVY:
        if m not in po_merezhi:
            continue
        ch.append(f'<h2>{MEREZHI_NAZVY[m]}</h2>')
        for kanal, spysok in sorted(po_merezhi[m].items()):
            if kanal:
                ch.append(f'<h3>{e(kanal)} район</h3>')
            ch.append('<div class="sitka">' + ''.join(kartka(o, media_url, statychna, csrf, tyzhden) for o in spysok)
                      + '</div>')
    if not vsi:
        ch.append('<p>За цей тиждень у черзі нічого немає.</p>')
    zh = sv.q.zhurnal(C.iso(C.teper() - timedelta(days=14)), 200)
    ch.append('<h2>Журнал (14 днів)</h2><details><summary>Показати</summary><table>' + ''.join(
        f'<tr><td>{e(R.po_kyievu(z["chas"]))}</td><td>{e(z["merezha"])}</td><td>{e(z["kanal"])}</td>'
        f'<td>{e(z["podiia"])}</td><td>{e(z["povidomlennia"])}</td></tr>' for z in zh) + '</table></details>')
    ch.append('</main></body></html>')
    return '\n'.join(ch)


VKHID = ('<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
         'initial-scale=1"><meta name="robots" content="noindex"><title>Вхід</title><style>' + CSS + '</style></head><body>'
         '<main style="max-width:360px;padding-top:60px"><h1>Перегляд опублікованого</h1>@P@<form method="post" '
         'action="/vkhid"><input type="password" name="parol" placeholder="Пароль" autofocus><button>Увійти</button>'
         '</form></main></body></html>')


def obrobnyk(sv, parol: str):
    kuka_ok = pidpys(parol, 'vkhid')
    csrf = pidpys(parol, 'csrf')

    class O(BaseHTTPRequestHandler):
        server_version = 'mv'

        def log_message(self, *a):
            pass

        def _vidpovid(self, kod: int, tilo: str | bytes, typ='text/html; charset=utf-8', zah=None):
            b = tilo.encode('utf-8') if isinstance(tilo, str) else tilo
            self.send_response(kod)
            self.send_header('Content-Type', typ)
            self.send_header('Content-Length', str(len(b)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            for k, v in (zah or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(b)

        def _uviishov(self) -> bool:
            for ch in (self.headers.get('Cookie') or '').split(';'):
                k, _, v = ch.strip().partition('=')
                if k == KUKA and hmac.compare_digest(v, kuka_ok):
                    return True
            return False

        def _forma(self) -> dict:
            n = min(int(self.headers.get('Content-Length') or 0), 20000)
            return {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode('utf-8', 'replace')).items()}

        def do_GET(self):
            u = urlsplit(self.path)
            if not self._uviishov():
                return self._vidpovid(200 if u.path == '/' else 401, VKHID.replace('@P@', ''))
            if u.path.startswith('/media/') and sv.media:
                f = (sv.media / u.path[len('/media/'):]).resolve()
                if sv.media.resolve() in f.parents and f.is_file():
                    return self._vidpovid(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or 'application/octet-stream')
                return self._vidpovid(404, 'немає')
            if u.path != '/':
                return self._vidpovid(404, 'немає')
            q = parse_qs(u.query)
            self._vidpovid(200, storinka(sv, q.get('tyzhden', [None])[0], csrf=csrf, povidomlennia=q.get('p', [''])[0]))

        def do_POST(self):
            u = urlsplit(self.path)
            f = self._forma()
            if u.path == '/vkhid':
                if hmac.compare_digest(f.get('parol', ''), parol):
                    return self._vidpovid(303, '', zah={'Location': '/', 'Set-Cookie':
                                          f'{KUKA}={kuka_ok}; Max-Age=2592000; Path=/; HttpOnly; Secure; SameSite=Strict'})
                time.sleep(2)
                return self._vidpovid(401, VKHID.replace('@P@', '<p class="zauv">Пароль не той.</p>'))
            if not self._uviishov() or not hmac.compare_digest(f.get('csrf', ''), csrf):
                return self._vidpovid(403, 'Увійдіть ще раз.')
            if u.path == '/prybraty':
                prychyna = f.get('prychyna', 'інше') + (f' — {f["dokladno"]}' if f.get('dokladno') else '')
                r = sv.prybraty(f.get('id', ''), prychyna, f.get('mistse') == '1', f.get('usi_merezhi') == '1')
                return self._vidpovid(303, '', zah={'Location': f'/?tyzhden={quote(f.get("tyzhden", ""))}&p='
                                                                + quote('; '.join(r))})
            self._vidpovid(404, 'немає')

    return O


def zapustyty(sv, host: str = '127.0.0.1', port: int = 8107):
    parol = os.environ.get('MV_PEREHLIAD_PAROL', '')
    if len(parol) < 12:
        raise SystemExit('Задайте змінну MV_PEREHLIAD_PAROL (щонайменше 12 знаків) — пароль сторінки-перегляду.')
    srv = HTTPServer((host, port), obrobnyk(sv, parol))
    print(f'Перегляд: http://{host}:{port}/ (назовні — лише через HTTPS-проксі)')
    srv.serve_forever()


if __name__ == '__main__':
    print(json.dumps({'див.': 'python avtopostynh/servis.py perehliad'}, ensure_ascii=False))
