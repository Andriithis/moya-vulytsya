"""Один раз отримати ключі для автопостингу й замірів — на ПК партнера (ZAVDANNYA-159). Ключі лише друкуються на екран:
звідти — одразу в «секрети» приватного репозиторію GitHub; у файли, чат і листи — ніколи (AGENTS.md, розд. 13).

    python avtopostynh/kliuchi.py google --client-id …          (секрет клієнта питає сам, без показу на екрані)
        Відкриває вікно згоди Google (YouTube: завантаження, видалення, статистика) і друкує ключ оновлення
        → секрет MV_YOUTUBE_REFRESH_TOKEN. Клієнт OAuth — типу «Desktop app» (повернення на 127.0.0.1).

    python avtopostynh/kliuchi.py meta --app-id …                (секрет застосунку й короткий ключ питає сам)
        Короткий ключ користувача з Graph API Explorer → довгий → безстроковий ключ сторінки й id Instagram
        → секрети MV_META_PAGE_TOKEN, MV_META_PAGE_ID, MV_INSTAGRAM_ID.

Покроково — `docs/SPYSOK-DLIA-MYKYTY.md`, розділ «Автопостинг і заміри роликів».
"""
from __future__ import annotations

import argparse
import getpass
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merezhi as M  # noqa: E402

# Що дозволяє ключ Google: завантажувати (`youtube.upload`), видаляти свої ролики («Прибрати» — `youtube`) і читати
# статистику каналу (`yt-analytics.readonly`, заміри). Більше нічого.
GOOGLE_DOZVOLY = ('https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube',
                  'https://www.googleapis.com/auth/yt-analytics.readonly')
# Дозволи застосунку Meta (вхід через Facebook): публікація й видалення на сторінці та в Instagram, статистика.
META_DOZVOLY = ('pages_show_list', 'pages_read_engagement', 'pages_manage_posts', 'read_insights',
                'instagram_basic', 'instagram_content_publish', 'instagram_manage_contents',
                'instagram_manage_insights', 'business_management')


def google_adresa(client_id: str, povernennia: str, stan: str) -> str:
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
        'client_id': client_id, 'redirect_uri': povernennia, 'response_type': 'code', 'scope': ' '.join(GOOGLE_DOZVOLY),
        'access_type': 'offline', 'prompt': 'consent', 'state': stan})


def google_obmin(kod: str, client_id: str, client_secret: str, povernennia: str, http_=None) -> dict:
    http_ = http_ or M.http
    v = http_('POST', 'https://oauth2.googleapis.com/token', {'Content-Type': 'application/x-www-form-urlencoded'},
              urllib.parse.urlencode({'code': kod, 'client_id': client_id, 'client_secret': client_secret,
                                      'redirect_uri': povernennia, 'grant_type': 'authorization_code'}).encode())
    j = v.json()
    if v.status != 200 or not j.get('refresh_token'):
        raise SystemExit(f'Google не дав ключ оновлення: {j.get("error_description") or j.get("error") or v.status}. '
                         'Чи клієнт типу «Desktop app»? Чи екран згоди «In production»?')
    brakuie = set(GOOGLE_DOZVOLY) - set(j.get('scope', '').split())
    if brakuie:
        print('Увага: Google не дав дозволів ' + ', '.join(sorted(brakuie)) + ' — у вікні згоди треба ставити всі галочки.')
    return j


def google(a) -> int:
    stan = secrets.token_urlsafe(16)
    otrymano: dict = {}

    class Obrobnyk(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if q.get('state', [''])[0] == stan:
                otrymano.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('Готово — поверніться до вікна команди.'.encode())

        def log_message(self, *x):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Obrobnyk)
    povernennia = f'http://127.0.0.1:{server.server_port}/'
    adresa = google_adresa(a.client_id, povernennia, stan)
    print('Відкриваю вікно згоди Google. Якщо не відкрилось — скопіюйте адресу в браузер:\n' + adresa)
    webbrowser.open(adresa)
    t = threading.Thread(target=server.handle_request)
    t.start()
    t.join(timeout=600)
    server.server_close()
    if not otrymano.get('code'):
        raise SystemExit(f'Згоди не отримано ({otrymano.get("error", "минуло 10 хвилин")}).')
    j = google_obmin(otrymano['code'], a.client_id, a.client_secret, povernennia)
    print('\nСекрет MV_YOUTUBE_REFRESH_TOKEN (вставити в GitHub і закрити це вікно):\n' + j['refresh_token'])
    return 0


def meta_kliuchi(app_id: str, app_secret: str, user_token: str, versiia: str = 'v27.0', http_=None) -> list[dict]:
    """Короткий ключ користувача → довгий (60 днів) → ключі сторінок (безстрокові, поки довгий ключ дійсний на момент
    обміну й пароль не змінювали) і прив'язаний Instagram."""
    http_ = http_ or M.http
    baza = f'https://graph.facebook.com/{versiia}'
    v = http_('GET', f'{baza}/oauth/access_token?' + urllib.parse.urlencode({
        'grant_type': 'fb_exchange_token', 'client_id': app_id, 'client_secret': app_secret,
        'fb_exchange_token': user_token}))
    if v.status != 200:
        raise SystemExit('Meta не обміняла ключ: ' + M._meta_pomylka(v, app_secret, user_token).pomylka)
    dovhyi = v.json()['access_token']
    v = http_('GET', f'{baza}/me/accounts?' + urllib.parse.urlencode({
        'fields': 'id,name,access_token,instagram_business_account', 'access_token': dovhyi}))
    if v.status != 200:
        raise SystemExit('Meta не дала сторінок: ' + M._meta_pomylka(v, app_secret, dovhyi).pomylka)
    return [{'nazva': s.get('name', ''), 'MV_META_PAGE_ID': s['id'], 'MV_META_PAGE_TOKEN': s['access_token'],
             'MV_INSTAGRAM_ID': (s.get('instagram_business_account') or {}).get('id', '')}
            for s in v.json().get('data', [])]


def meta(a) -> int:
    storinky = meta_kliuchi(a.app_id, a.app_secret, a.user_token, a.versiia)
    if not storinky:
        raise SystemExit('Сторінок немає: під час входу в Graph API Explorer оберіть сторінку проєкту й дозволи '
                         + ', '.join(META_DOZVOLY))
    for s in storinky:
        print(f'\nСторінка «{s["nazva"]}»:')
        for k in ('MV_META_PAGE_ID', 'MV_INSTAGRAM_ID', 'MV_META_PAGE_TOKEN'):
            print(f'  {k} = {s[k] or "— (Instagram не прив’язано до цієї сторінки)"}')
    print('\nУсі три — у секрети GitHub; вікно закрити.')
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Ключі для автопостингу й замірів (друкує на екран, файлів не пише).')
    sp = p.add_subparsers(dest='komanda', required=True)
    g = sp.add_parser('google')
    g.add_argument('--client-id', required=True)
    g.add_argument('--client-secret', help='краще не вказувати: тоді спитає без показу (не лишиться в історії команд)')
    m = sp.add_parser('meta')
    m.add_argument('--app-id', required=True)
    m.add_argument('--app-secret', help='краще не вказувати: тоді спитає без показу')
    m.add_argument('--user-token', help='короткий ключ з Graph API Explorer; краще не вказувати — спитає')
    m.add_argument('--versiia', default='v27.0')
    a = p.parse_args(argv)
    if a.komanda == 'google' and not a.client_secret:
        a.client_secret = getpass.getpass('Client secret (не видно на екрані): ').strip()
    if a.komanda == 'meta':
        a.app_secret = a.app_secret or getpass.getpass('App secret (не видно): ').strip()
        a.user_token = a.user_token or getpass.getpass('Короткий ключ з Graph API Explorer (не видно): ').strip()
    return google(a) if a.komanda == 'google' else meta(a)


if __name__ == '__main__':
    sys.exit(main())
