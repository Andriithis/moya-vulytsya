"""Черга, журнал і стан мереж — один файл SQLite на сервері (ZAVDANNYA-107, п. 1, 3, 4).

Стани одиниці:
  chekaie        — у черзі, час ще не настав або чекає повторної спроби;
  vidkhyleno     — не пройшла перевірку правил; у мережу не йде, видно на сторінці-перегляді з причинами;
  opublikovano   — вийшла; є посилання на допис;
  pomylka        — не вийшла після всіх спроб;
  propushcheno   — мережа вимкнена або допис запізнився більше ніж на добу;
  prybrano       — Андрій прибрав, сервіс видалив допис;
  prybraty_vruchnu — Андрій прибрав, а мережа не дала видалити (інтерфейс не вміє або минуло 48 год у Telegram):
                   партнер видаляє руками, сторінка показує це окремо.
Таблиця `zaboroneno` — що прибирали: подія, місце, текст; перевірка правил більше такого не пропускає.
Токенів тут немає (AGENTS, розд. 13).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKHEMA = """
CREATE TABLE IF NOT EXISTS odynytsi (
  id TEXT PRIMARY KEY, tyzhden TEXT, merezha TEXT, kanal TEXT, typ TEXT, hrupa TEXT, chas TEXT,
  stan TEXT, sproby INTEGER DEFAULT 0, nastupna TEXT, zovnishnii_id TEXT, url_dopysu TEXT,
  opublikovano TEXT, zauvazhennia TEXT, dani TEXT);
CREATE INDEX IF NOT EXISTS i_chas ON odynytsi(stan, chas);
CREATE TABLE IF NOT EXISTS zhurnal (
  n INTEGER PRIMARY KEY AUTOINCREMENT, chas TEXT, odynytsia TEXT, merezha TEXT, kanal TEXT, podiia TEXT,
  povidomlennia TEXT);
CREATE TABLE IF NOT EXISTS merezhi (merezha TEXT PRIMARY KEY, zupyneno_do TEXT, prychyna TEXT, pomylok_pidriad INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS zaboroneno (typ TEXT, znachennia TEXT, prychyna TEXT, chas TEXT, PRIMARY KEY (typ, znachennia));
CREATE TABLE IF NOT EXISTS vypusky (fail TEXT PRIMARY KEY, chas TEXT);
"""
MAKS_SPROB = 4
ZUPYNKA_PISLIA_POMYLOK = 3          # 3 помилки підряд у мережі — зупинка на добу
NAZAVZHDY = '9999-12-31T00:00+00:00'


def teper() -> datetime:
    return datetime.now(timezone.utc)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec='minutes')


class Cherha:
    def __init__(self, shliakh: Path | str):
        self.db = sqlite3.connect(str(shliakh), timeout=30)   # щогодинний запуск і сторінка-перегляд пишуть по черзі
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SKHEMA)

    def zakryty(self):
        self.db.close()

    # ---------------------------------------------------------------- журнал
    def zapys(self, podiia: str, povidomlennia: str, o: dict | None = None, merezha: str = '', koly: datetime | None = None):
        o = o or {}
        self.db.execute('INSERT INTO zhurnal (chas, odynytsia, merezha, kanal, podiia, povidomlennia) VALUES (?,?,?,?,?,?)',
                        (iso(koly or teper()), o.get('id', ''), o.get('merezha', merezha), o.get('kanal', ''), podiia,
                         povidomlennia))
        self.db.commit()

    def zhurnal(self, vid: str = '', limit: int = 500) -> list[dict]:
        return [dict(r) for r in self.db.execute('SELECT * FROM zhurnal WHERE chas >= ? ORDER BY n DESC LIMIT ?',
                                                 (vid, limit))]

    # ---------------------------------------------------------------- одиниці
    def dodaty(self, o: dict, zauvazhennia: list[str]) -> bool:
        """Нова одиниця; повторне додавання тієї самої (той самий id) нічого не змінює."""
        if self.db.execute('SELECT 1 FROM odynytsi WHERE id=?', (o['id'],)).fetchone():
            return False
        stan = 'vidkhyleno' if zauvazhennia else 'chekaie'
        self.db.execute(
            'INSERT INTO odynytsi (id, tyzhden, merezha, kanal, typ, hrupa, chas, stan, zauvazhennia, dani) '
            'VALUES (?,?,?,?,?,?,?,?,?,?)',
            (o['id'], o['tyzhden'], o['merezha'], o.get('kanal', ''), o['typ'], o.get('hrupa', ''), o['chas'], stan,
             json.dumps(zauvazhennia, ensure_ascii=False), json.dumps(o, ensure_ascii=False)))
        self.db.commit()
        if zauvazhennia:
            self.zapys('vidkhyleno', '; '.join(zauvazhennia), o)
        return True

    @staticmethod
    def _o(r) -> dict:
        o = json.loads(r['dani'])
        for k in ('stan', 'sproby', 'nastupna', 'zovnishnii_id', 'url_dopysu', 'opublikovano'):
            o[k] = r[k]
        o['zauvazhennia'] = json.loads(r['zauvazhennia'] or '[]')
        return o

    def odna(self, id_: str) -> dict | None:
        r = self.db.execute('SELECT * FROM odynytsi WHERE id=?', (id_,)).fetchone()
        return self._o(r) if r else None

    def vsi(self, tyzhden: str | None = None, stan: str | None = None) -> list[dict]:
        q, p = 'SELECT * FROM odynytsi WHERE 1=1', []
        if tyzhden:
            q, p = q + ' AND tyzhden=?', p + [tyzhden]
        if stan:
            q, p = q + ' AND stan=?', p + [stan]
        return [self._o(r) for r in self.db.execute(q + ' ORDER BY chas, merezha, kanal', p)]

    def tyzhni(self) -> list[str]:
        return [r[0] for r in self.db.execute('SELECT DISTINCT tyzhden FROM odynytsi ORDER BY tyzhden DESC')]

    def chas_nastav(self, zaraz: datetime) -> list[dict]:
        z = iso(zaraz)
        return [self._o(r) for r in self.db.execute(
            "SELECT * FROM odynytsi WHERE stan='chekaie' AND chas <= ? AND (nastupna IS NULL OR nastupna <= ?) "
            'ORDER BY chas, merezha, kanal', (z, z))]

    def stan(self, id_: str, stan: str, **polia):
        polia['stan'] = stan
        sets = ', '.join(f'{k}=?' for k in polia)
        self.db.execute(f'UPDATE odynytsi SET {sets} WHERE id=?', (*polia.values(), id_))
        self.db.commit()

    def nedavni_podii(self, zaraz: datetime, dniv: int) -> set:
        vid = iso(zaraz - timedelta(days=dniv))
        r = set()
        for (d,) in self.db.execute("SELECT dani FROM odynytsi WHERE stan IN ('chekaie','opublikovano') AND chas >= ?",
                                    (vid,)):
            r.update(json.loads(d).get('podii') or [])
        return r

    def vsi_podii(self) -> set:
        r = set()
        for (d,) in self.db.execute("SELECT dani FROM odynytsi WHERE stan IN ('chekaie','opublikovano')"):
            r.update(json.loads(d).get('podii') or [])
        return r

    # ---------------------------------------------------------------- мережі
    def merezha_zupynena(self, merezha: str, zaraz: datetime) -> str | None:
        r = self.db.execute('SELECT zupyneno_do, prychyna FROM merezhi WHERE merezha=?', (merezha,)).fetchone()
        if r and r['zupyneno_do'] and r['zupyneno_do'] > iso(zaraz):
            return r['prychyna']
        return None

    def zupynyty(self, merezha: str, do: str, prychyna: str):
        self.db.execute('INSERT INTO merezhi (merezha, zupyneno_do, prychyna, pomylok_pidriad) VALUES (?,?,?,0) '
                        'ON CONFLICT(merezha) DO UPDATE SET zupyneno_do=excluded.zupyneno_do, prychyna=excluded.prychyna, '
                        'pomylok_pidriad=0', (merezha, do, prychyna))
        self.db.commit()
        self.zapys('zupynka', f'до {"ручного відновлення" if do == NAZAVZHDY else do}: {prychyna}', merezha=merezha)

    def vidnovyty(self, merezha: str):
        self.db.execute('DELETE FROM merezhi WHERE merezha=?', (merezha,))
        self.db.commit()
        self.zapys('vidnovleno', 'мережу відновлено вручну', merezha=merezha)

    def pomylka_merezhi(self, merezha: str) -> int:
        self.db.execute('INSERT INTO merezhi (merezha, pomylok_pidriad) VALUES (?,1) ON CONFLICT(merezha) DO UPDATE '
                        'SET pomylok_pidriad=pomylok_pidriad+1', (merezha,))
        self.db.commit()
        return self.db.execute('SELECT pomylok_pidriad FROM merezhi WHERE merezha=?', (merezha,)).fetchone()[0]

    def uspikh_merezhi(self, merezha: str):
        self.db.execute('UPDATE merezhi SET pomylok_pidriad=0 WHERE merezha=?', (merezha,))
        self.db.commit()

    def stan_merezh(self) -> list[dict]:
        return [dict(r) for r in self.db.execute('SELECT * FROM merezhi ORDER BY merezha')]

    # ---------------------------------------------------------------- прибране
    def zaboronyty(self, typ: str, znachennia: str, prychyna: str):
        self.db.execute('INSERT OR REPLACE INTO zaboroneno VALUES (?,?,?,?)', (typ, znachennia, prychyna, iso(teper())))
        self.db.commit()

    def zaboroneno(self) -> dict:
        r = {'podiia': {}, 'mistse': {}, 'tekst': {}, 'pozytsiia': {}}
        for x in self.db.execute('SELECT typ, znachennia, prychyna FROM zaboroneno'):
            r.setdefault(x['typ'], {})[x['znachennia']] = x['prychyna']
        return r

    # ---------------------------------------------------------------- випуски
    def vypusk_obroblenyi(self, fail: str) -> bool:
        return bool(self.db.execute('SELECT 1 FROM vypusky WHERE fail=?', (fail,)).fetchone())

    def vypusk_obrobleno(self, fail: str):
        self.db.execute('INSERT OR IGNORE INTO vypusky VALUES (?,?)', (fail, iso(teper())))
        self.db.commit()
