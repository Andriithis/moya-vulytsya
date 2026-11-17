"""Сховище стеження бота «Мій будинок» (ZAVDANNYA-97) — SQLite на сервері партнера.

Що зберігаємо (мінімум для розсилки, `docs/BOT-I-KANALY.md`, розд. «Правові межі»):
  chat_id      — ідентифікатор чату Telegram (без імені, ніка й телефону);
  url          — сторінка будинку, за яким стежать (одна адреса на чат безкоштовно);
  stvoreno     — коли почали стежити (дата);
  versiia, misiats_1551, podii_vsi — що вже надіслано, щоб наступного разу рахувати лише нове.
Текстів повідомлень не зберігаємо. «Не стежити» / /stop або блокування бота людиною — запис видаляється одразу.
Запис без активності понад 12 місяців — видаляється (`prybraty_stari`).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

SKHEMA = '''CREATE TABLE IF NOT EXISTS stezhennia (
  chat_id      INTEGER PRIMARY KEY,
  url          TEXT NOT NULL,
  stvoreno     TEXT NOT NULL,
  versiia      TEXT,
  misiats_1551 TEXT,
  podii_vsi    INTEGER,
  nadislano    TEXT
)'''
STROK_ZBERIHANNIA_DNIV = 365


class Skhovyshche:
    def __init__(self, shlyakh: str | Path = ':memory:'):
        self.con = sqlite3.connect(str(shlyakh))
        self.con.execute(SKHEMA)
        self.con.commit()

    def stezhyty(self, chat_id: int, url: str, data: str, versiia: str, misiats_1551: str, podii_vsi: int) -> None:
        """Одна адреса на чат: нова замінює попередню. Відлік «нового» — з цього моменту."""
        data = data or date.today().isoformat()
        self.con.execute('INSERT OR REPLACE INTO stezhennia VALUES (?,?,?,?,?,?,?)',
                         (chat_id, url, data, versiia, misiats_1551, podii_vsi, data))
        self.con.commit()

    def vydalyty(self, chat_id: int) -> None:
        self.con.execute('DELETE FROM stezhennia WHERE chat_id = ?', (chat_id,))
        self.con.commit()

    def usi(self) -> list[dict]:
        cur = self.con.execute('SELECT chat_id, url, stvoreno, versiia, misiats_1551, podii_vsi, nadislano '
                               'FROM stezhennia ORDER BY chat_id')
        kl = [c[0] for c in cur.description]
        return [dict(zip(kl, r)) for r in cur.fetchall()]

    def nadislano(self, chat_id: int, data: str, versiia: str, misiats_1551: str, podii_vsi: int) -> None:
        self.con.execute('UPDATE stezhennia SET nadislano = ?, versiia = ?, misiats_1551 = ?, podii_vsi = ? WHERE chat_id = ?',
                         (data, versiia, misiats_1551, podii_vsi, chat_id))
        self.con.commit()

    def prybraty_stari(self, sohodni: str) -> int:
        """Видалити записи, яким нічого не надсилали й які не оновлювали понад рік."""
        mezha = (date.fromisoformat(sohodni) - timedelta(days=STROK_ZBERIHANNIA_DNIV)).isoformat()
        n = self.con.execute('DELETE FROM stezhennia WHERE COALESCE(nadislano, stvoreno) < ?', (mezha,)).rowcount
        self.con.commit()
        return n


def rozsylka(bot, skh: Skhovyshche, sohodni: str, nadislaty) -> dict:
    """Щотижнева розсилка: для кожного запису — «нове біля дому» або нічого.
    nadislaty(chat_id, vidpovid) -> True (надіслано) | False (людина заблокувала бота: запис видаляємо) ."""
    zvit = {'zapysiv': 0, 'nadislano': 0, 'bez_novoho': 0, 'vydaleno': 0}
    zvit['vydaleno'] += skh.prybraty_stari(sohodni)
    for z in skh.usi():
        zvit['zapysiv'] += 1
        v = bot.nove(z)
        if v is None:
            zvit['bez_novoho'] += 1
            continue
        if nadislaty(z['chat_id'], v):
            b = bot.za_url[z['url']]
            n = bot.navkolo(b)
            skh.nadislano(z['chat_id'], sohodni, bot.indeks.get('versiia', ''),
                          bot.misiatsi[-1] if bot.misiatsi else '', n['podii_vsi'])
            zvit['nadislano'] += 1
        else:
            skh.vydalyty(z['chat_id'])
            zvit['vydaleno'] += 1
    return zvit
