"""Що зберігаємо для листа «Нове біля дому» і відписка в один дотик (ZAVDANNYA-119, п. 3).

**Стик із сервером продажу (ZAVDANNYA-99).** Обліковий запис, оплата й адреси «Стежу» живуть у кабінеті сервера продажу
(PostgreSQL). Розсилці від нього треба лише те, що в класі `Skhovyshche` нижче; коли ZAVDANNYA-99 зіллють, сервер дає
об'єкт із тими самими методами (`pidpysnyky`, `vymknuty`, `nadislano`, `vydalyty`) поверх своєї бази — розсилка й тести
не змінюються. До того — цей SQLite (і для тестів).

Мінімум (`docs/LYST-NOVE-BILIA-DOMU.md`, розд. 4):
  pidpysnyk: id (випадковий, не пошта) · пошта · номер чату Telegram (якщо людина під'єднала бота) · тариф ·
             які канали ввімкнено · чи слати «тихий тиждень» · коли почали · коли надіслано востаннє;
  adresa:    адреси «Стежу» (позначка людини, адреса, точка) — без них листа не скласти.
Імені, телефону, текстів листів, історії відкриттів і переходів **не зберігаємо** (жодних «пікселів» стеження в листі).
Відписка від каналу — канал вимкнено одразу; вимкнено всі — записи підписника тут видаляються (обліковий запис і
оплата — у сервері продажу, їх відписка від листа не чіпає).

Посилання відписки: `…/vidpyska/?p=<id>&k=<канал>&t=<підпис>`; підпис — HMAC-SHA256 від `id|канал` ключем зі змінної
`MV_LYST_SEKRET` (лише на сервері партнера, ніколи у файлах). Без правильного підпису нічого не вимикається: чужий не
відпише чужого й не дізнається, чи є такий підписник.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlencode

from lyst import Adresa, Pidpysnyk

ZMINNA_SEKRETU = 'MV_LYST_SEKRET'
KANALY = ('poshta', 'telegram', 'push')

SKHEMA = '''
CREATE TABLE IF NOT EXISTS pidpysnyk (
  id          TEXT PRIMARY KEY,
  poshta      TEXT,
  chat_id     INTEGER,
  taryf       TEXT NOT NULL CHECK (taryf IN ('pidpyska', 'bezkoshtovno')),
  poshta_on   INTEGER NOT NULL DEFAULT 1,
  telegram_on INTEGER NOT NULL DEFAULT 1,
  push_on     INTEGER NOT NULL DEFAULT 1,
  tykhyi      INTEGER NOT NULL DEFAULT 1,
  stvoreno    TEXT NOT NULL,
  nadislano   TEXT
);
CREATE TABLE IF NOT EXISTS adresa (
  pidpysnyk_id TEXT NOT NULL REFERENCES pidpysnyk(id) ON DELETE CASCADE,
  poriadok     INTEGER NOT NULL,
  nazva        TEXT NOT NULL DEFAULT '',
  adresa       TEXT NOT NULL,
  lat          REAL NOT NULL,
  lon          REAL NOT NULL,
  PRIMARY KEY (pidpysnyk_id, poriadok)
);
'''


def sekret() -> bytes:
    s = os.environ.get(ZMINNA_SEKRETU, '')
    if len(s) < 32:
        raise SystemExit(f'Немає ключа відписки: задайте змінну {ZMINNA_SEKRETU} (≥ 32 знаки, лише на сервері).')
    return s.encode('utf-8')


def pidpys(klyuch: bytes, pid: str, kanal: str) -> str:
    return hmac.new(klyuch, f'{pid}|{kanal}'.encode('utf-8'), hashlib.sha256).hexdigest()[:32]


def posylannia_vidpysky(sait: str, klyuch: bytes, pid: str, kanal: str) -> str:
    return f'{sait.rstrip("/")}/vidpyska/?' + urlencode({'p': pid, 'k': kanal, 't': pidpys(klyuch, pid, kanal)})


class Skhovyshche:
    def __init__(self, shlyakh: str | Path = ':memory:'):
        self.con = sqlite3.connect(str(shlyakh))
        self.con.execute('PRAGMA foreign_keys = ON')
        self.con.executescript(SKHEMA)
        self.con.commit()

    # ---------------------------------------------- що дає кабінет (ZAVDANNYA-99)
    def dodaty(self, taryf: str, adresy: list[Adresa], poshta: str | None = None, chat_id: int | None = None,
               stvoreno: str = '', tykhyi: bool = True) -> str:
        pid = secrets.token_urlsafe(12)
        self.con.execute('INSERT INTO pidpysnyk (id, poshta, chat_id, taryf, tykhyi, stvoreno) VALUES (?,?,?,?,?,?)',
                         (pid, poshta, chat_id, taryf, int(tykhyi), stvoreno or '1970-01-01'))
        self.con.executemany('INSERT INTO adresa VALUES (?,?,?,?,?,?)',
                             [(pid, i, a.nazva, a.adresa, a.lat, a.lon) for i, a in enumerate(adresy)])
        self.con.commit()
        return pid

    def pidpysnyky(self) -> list[tuple[Pidpysnyk, dict]]:
        """-> [(підписник, {канал: куди})] — лише ввімкнені канали з контактом."""
        out = []
        for pid, poshta, chat_id, taryf, p_on, t_on, u_on, tykhyi in self.con.execute(
                'SELECT id, poshta, chat_id, taryf, poshta_on, telegram_on, push_on, tykhyi FROM pidpysnyk ORDER BY id'):
            adresy = [Adresa(adresa=a, lat=la, lon=lo, nazva=n) for n, a, la, lo in self.con.execute(
                'SELECT nazva, adresa, lat, lon FROM adresa WHERE pidpysnyk_id = ? ORDER BY poriadok', (pid,))]
            kanaly = {}
            if p_on and poshta:
                kanaly['poshta'] = poshta
            if t_on and chat_id:
                kanaly['telegram'] = chat_id
            if u_on and taryf == 'pidpyska':
                kanaly['push'] = pid          # підписку браузера (endpoint, ключі) тримає сервер продажу
            out.append((Pidpysnyk(pid, taryf, adresy, bool(tykhyi)), kanaly))
        return out

    def nadislano(self, pid: str, data: str) -> None:
        self.con.execute('UPDATE pidpysnyk SET nadislano = ? WHERE id = ?', (data, pid))
        self.con.commit()

    def vymknuty(self, pid: str, kanal: str) -> bool:
        """Вимкнути канал; вимкнено всі — видалити підписника тут. -> чи був такий."""
        if kanal not in KANALY:
            return False
        n = self.con.execute(f'UPDATE pidpysnyk SET {kanal}_on = 0 WHERE id = ?', (pid,)).rowcount
        self.con.execute('DELETE FROM pidpysnyk WHERE id = ? AND poshta_on = 0 AND telegram_on = 0 AND push_on = 0', (pid,))
        self.con.commit()
        return bool(n)

    def vydalyty(self, pid: str) -> None:
        """Видалення на запит людини чи при закритті облікового запису."""
        self.con.execute('DELETE FROM pidpysnyk WHERE id = ?', (pid,))
        self.con.commit()


def vidpyska(skh: Skhovyshche, klyuch: bytes, params: dict) -> tuple[int, str]:
    """Обробник посилання відписки (POST з кнопки поштової програми — RFC 8058 — чи зі сторінки).
    -> (код HTTP, текст сторінки). Неправильний підпис і невідомий підписник — однакова відповідь."""
    pid, kanal, t = (params.get('p') or ''), (params.get('k') or ''), (params.get('t') or '')
    if kanal not in KANALY or not hmac.compare_digest(pidpys(klyuch, pid, kanal), t):
        return 400, 'Посилання не спрацювало. Вимкнути листи можна в кабінеті.'
    skh.vymknuty(pid, kanal)
    return 200, {'poshta': 'Готово: листів «Нове біля дому» більше не буде.',
                 'telegram': 'Готово: повідомлень у Telegram більше не буде.',
                 'push': 'Готово: сповіщень більше не буде.'}[kanal] + ' Увімкнути знову — у кабінеті.'
