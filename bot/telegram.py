"""Запуск бота «Мій будинок» (ZAVDANNYA-97): Telegram або розмова в терміналі.

    # розмова в терміналі — без Telegram і без токена:
    python bot/telegram.py --indeks indeks.json --konsol [--scenarii a|b|v]
    # справжній бот (на сервері партнера; токен — лише у змінній середовища, ніколи у файлах):
    MV_TELEGRAM_TOKEN=… python bot/telegram.py --indeks indeks.json --skhovyshche stezhennia.db [--scenarii a]
    # щотижнева розсилка «нове біля дому» (раз на тиждень із розкладу сервера):
    MV_TELEGRAM_TOKEN=… python bot/telegram.py --indeks indeks.json --skhovyshche stezhennia.db --rozsylka

Без сторонніх бібліотек: Bot API через urllib, довге опитування getUpdates (вебхук не потрібен).
У терміналі кнопку натискають так: «!1» — перша кнопка з даними.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rozmova import ADRESA_SAITU, Bot, Vidpovid  # noqa: E402
from stezhennia import Skhovyshche, rozsylka  # noqa: E402

ZMINNA_TOKENA = 'MV_TELEGRAM_TOKEN'


class Telegram:
    def __init__(self, token: str):
        if not token or ':' not in token:
            raise SystemExit(f'Немає токена: задайте змінну середовища {ZMINNA_TOKENA} (токен заводить партнер).')
        self._baza = f'https://api.telegram.org/bot{token}/'

    def vyklyk(self, metod: str, **params) -> dict:
        dani = json.dumps(params, ensure_ascii=False).encode('utf-8')
        zapyt = urllib.request.Request(self._baza + metod, data=dani, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(zapyt, timeout=70) as v:
                return json.loads(v.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            # токен в адресі — у повідомлення про помилку його не пишемо
            return json.loads(e.read().decode('utf-8') or '{}') or {'ok': False, 'error_code': e.code}

    def nadislaty(self, chat_id: int, v: Vidpovid) -> dict:
        return self.vyklyk('sendMessage', chat_id=chat_id, text=v.tekst, disable_web_page_preview=True,
                           **({'reply_markup': rozmitka(v)} if v.knopky else {}))


def rozmitka(v: Vidpovid) -> dict:
    return {'inline_keyboard': [[({'text': k.tekst, 'url': k.url} if k.url else {'text': k.tekst, 'callback_data': k.dani})
                                 for k in ryad] for ryad in v.knopky]}


def tsykl(bot: Bot, tg: Telegram) -> None:
    zsuv = 0
    while True:
        r = tg.vyklyk('getUpdates', offset=zsuv, timeout=50, allowed_updates=['message', 'callback_query'])
        if not r.get('ok'):
            time.sleep(5)
            continue
        for u in r['result']:
            zsuv = u['update_id'] + 1
            sohodni = date.today().isoformat()
            if 'message' in u and 'text' in u['message']:
                m = u['message']
                if m['chat'].get('type') != 'private':
                    continue                      # лише особисті чати: у групах адреси бачили б інші
                tg.nadislaty(m['chat']['id'], bot.povidomlennia(m['chat']['id'], m['text'], time.time()))
            elif 'callback_query' in u:
                q = u['callback_query']
                chat = q['message']['chat']['id']
                tg.vyklyk('answerCallbackQuery', callback_query_id=q['id'])
                tg.nadislaty(chat, bot.natysnuto(chat, q.get('data', ''), sohodni))


def konsol(bot: Bot, vkhid=sys.stdin, vykhid=sys.stdout) -> None:
    chat = 1
    ostanni = []

    def pokazaty(v: Vidpovid):
        nonlocal ostanni
        print('\n' + v.tekst, file=vykhid)
        ostanni = [k for ryad in v.knopky for k in ryad]
        for i, k in enumerate(ostanni, 1):
            print(f'  [{i}] {k.tekst}' + (f' → {k.url}' if k.url else ''), file=vykhid)

    pokazaty(bot.povidomlennia(chat, '/start'))
    for ryadok in vkhid:
        t = ryadok.strip()
        if not t:
            continue
        print(f'\n> {t}', file=vykhid)
        if t.startswith('!') and t[1:].isdigit() and 0 < int(t[1:]) <= len(ostanni) and ostanni[int(t[1:]) - 1].dani:
            pokazaty(bot.natysnuto(chat, ostanni[int(t[1:]) - 1].dani, date.today().isoformat()))
        else:
            pokazaty(bot.povidomlennia(chat, t, time.time()))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Бот «Мій будинок».')
    p.add_argument('--indeks', type=Path, required=True, help='покажчик з bot/indeks.py')
    p.add_argument('--scenarii', choices=('a', 'b', 'v'), default='a')
    p.add_argument('--skhovyshche', default=':memory:', help='файл SQLite стеження (на сервері)')
    p.add_argument('--adresa-saitu', default=ADRESA_SAITU)
    p.add_argument('--konsol', action='store_true', help='розмова в терміналі, без Telegram')
    p.add_argument('--rozsylka', action='store_true', help='надіслати щотижневе «нове біля дому» й вийти')
    a = p.parse_args(argv)
    indeks = json.loads(a.indeks.read_text(encoding='utf-8'))
    skh = Skhovyshche(a.skhovyshche)
    bot = Bot(indeks, skh, a.scenarii, a.adresa_saitu)
    if a.konsol:
        konsol(bot)
        return 0
    tg = Telegram(os.environ.get(ZMINNA_TOKENA, ''))
    if a.rozsylka:
        def nadislaty(chat_id, v):
            r = tg.nadislaty(chat_id, v)
            time.sleep(0.05)                       # ≤ 20 повідомлень на секунду — нижче ліміту Telegram
            return bool(r.get('ok')) or r.get('error_code') != 403
        print(rozsylka(bot, skh, date.today().isoformat(), nadislaty))
        return 0
    tsykl(bot, tg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
