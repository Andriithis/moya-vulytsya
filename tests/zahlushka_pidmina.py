"""Локальна підміна сховища Supabase для перевірок заглушки.

Справжнього сховища немає (обліковий запис створює власник). Цей маленький
сервер на 127.0.0.1 водночас:
  * віддає зібрану заглушку як звичайні файли;
  * поводиться як REST-адреса Supabase для таблиць zayavka і podiya:
      - POST публічним ключем — додає рядок (як RLS «лише додавати»);
      - GET публічним ключем — 401 (читати не можна);
      - GET / DELETE секретним ключем — читає / видаляє з фільтром kanal=eq.…
  * у режимі zbii=True відповідає 503 на заявки — для перевірки помилки мережі.

Записи живуть лише в пам'яті процесу і нікуди не зберігаються.
Ключі тут — умовні слова, а не справжні ключі.
"""
from __future__ import annotations

import functools
import json
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PUBLICHNYI = 'test-publichnyi'
SEKRETNYI = 'test-sekretnyi'
STOVPTSI = {
    'zayavka': {'shcho', 'misto', 'adresa', 'kontakt', 'zghoda', 'kanal'},
    'podiya': {'nazva', 'kanal'},
    # ZAVDANNYA-06: звернення про виправлення або видалення
    'zvernennya': {'posylannya', 'shcho_ne_tak', 'poyasnennya', 'kontakt', 'zghoda'},
}


class Skhovyshche:
    def __init__(self):
        self.ryadky = {t: [] for t in STOVPTSI}
        self.zapyty = []          # (метод, шлях, заголовки) — для перевірок
        self.zbii = False
        self.lichylnyk = 0
        self.zamok = threading.Lock()


class Obrobnyk(SimpleHTTPRequestHandler):
    skhovyshche: Skhovyshche

    def log_message(self, *a):  # тиша в журналі тестів
        pass

    def _tablytsya(self):
        shlyakh = urllib.parse.urlsplit(self.path)
        if not shlyakh.path.startswith('/rest/v1/'):
            return None, None
        return shlyakh.path[len('/rest/v1/'):], urllib.parse.parse_qs(shlyakh.query)

    def _vidpovid(self, kod, tilo=None):
        dani = b'' if tilo is None else json.dumps(tilo, ensure_ascii=False).encode('utf-8')
        self.send_response(kod)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(dani)))
        self.end_headers()
        self.wfile.write(dani)

    def _klyuch(self):
        return self.headers.get('apikey', '')

    def _filtr(self, q):
        f = q.get('kanal', [''])[0]
        return f[3:] if f.startswith('eq.') else None

    def _zapysaty(self):
        s = self.skhovyshche
        with s.zamok:
            s.zapyty.append((self.command, self.path, {k.lower(): v for k, v in self.headers.items()}))

    def do_POST(self):
        t, q = self._tablytsya()
        if t is None:
            return self._vidpovid(404)
        self._zapysaty()
        s = self.skhovyshche
        dovzhyna = int(self.headers.get('Content-Length') or 0)
        ryadok = json.loads(self.rfile.read(dovzhyna) or b'{}')
        if t not in STOVPTSI:
            return self._vidpovid(404, {'message': 'немає таблиці'})
        if self._klyuch() not in (PUBLICHNYI, SEKRETNYI):
            return self._vidpovid(401, {'message': 'невідомий ключ'})
        if s.zbii and t in ('zayavka', 'zvernennya'):
            return self._vidpovid(503, {'message': 'умовний збій'})
        if set(ryadok) - STOVPTSI[t]:
            return self._vidpovid(401, {'message': 'permission denied'})
        if t in ('zayavka', 'zvernennya') and ryadok.get('zghoda') is not True:
            return self._vidpovid(403, {'message': 'row-level security'})
        with s.zamok:
            s.lichylnyk += 1
            ryadok = dict(ryadok, id=s.lichylnyk, chas=datetime.now(timezone.utc).isoformat())
            s.ryadky[t].append(ryadok)
        return self._vidpovid(201)

    def do_GET(self):
        t, q = self._tablytsya()
        if t is None:
            return super().do_GET()
        self._zapysaty()
        if self._klyuch() != SEKRETNYI:
            return self._vidpovid(401, {'message': 'permission denied'})
        kanal = self._filtr(q)
        rows = [r for r in self.skhovyshche.ryadky.get(t, []) if kanal is None or r.get('kanal') == kanal]
        return self._vidpovid(200, [{'id': r['id']} for r in rows])

    def do_DELETE(self):
        t, q = self._tablytsya()
        if t is None:
            return self._vidpovid(404)
        self._zapysaty()
        if self._klyuch() != SEKRETNYI:
            return self._vidpovid(401, {'message': 'permission denied'})
        kanal = self._filtr(q)
        s = self.skhovyshche
        with s.zamok:
            vydaleni = [r for r in s.ryadky[t] if r.get('kanal') == kanal]
            s.ryadky[t] = [r for r in s.ryadky[t] if r.get('kanal') != kanal]
        return self._vidpovid(200, vydaleni)


def zapustyty(teka: str):
    """Запускає підміну у фоні. Повертає (сервер, сховище, адреса)."""
    s = Skhovyshche()
    klas = type('ObrobnykZ', (Obrobnyk,), {'skhovyshche': s})
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(klas, directory=teka))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, s, f'http://127.0.0.1:{server.server_address[1]}'
