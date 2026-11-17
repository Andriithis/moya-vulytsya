"""Хостинг сайту: два варіанти збирання (ZAVDANNYA-88, п. 1; порада — `docs/HOSTYNG.md`).

* `pages` — як досі: кожна сторінка окремим файлом, межа 20 000 файлів (безкоштовний Cloudflare Pages).
* `workers` — Cloudflare Workers зі статичними файлами: сторінки будинків і їхні картинки складено в «пачки»
  `/_budynky/s00000.bin` (сторінки) і `/_budynky/k00000.bin` (картинки) по ≈ 16 будинків; маленький скрипт
  (`site/worker/index.js`) віддає з пачки потрібний будинок за адресою `/budynok/<вулиця>/<номер>/`. Решта сайту —
  звичайні файли, їх Cloudflare віддає сам, без скрипта. Так файлів у сотні разів менше, і повний Київ, а потім Україна
  вміщаються в безкоштовну межу 20 000 файлів (платний план — 100 000).

Формат пачки: 4 байти — довжина L покажчика (big-endian), L байтів — покажчик JSON {slug: [зсув, довжина]}, далі —
байти сторінок (UTF-8) чи картинок (PNG) підряд. Номер пачки — FNV-1a (32 біти) від slug будинку за модулем кількості
пачок; той самий розрахунок — у `worker/index.js`.
"""
from __future__ import annotations

import json
import math
import shutil
import struct
from pathlib import Path

VARIANTY = ('pages', 'workers')
MEZHA_FAILIV = {'pages': 20000, 'workers': 20000}     # безкоштовні плани; платні — 100 000 (--mezha-failiv)
BUDYNKIV_U_PACHTSI = 16
TEKA_PACHOK = '_budynky'
WORKER = Path(__file__).resolve().parent / 'worker'


def fnv1a(tekst: str) -> int:
    h = 0x811C9DC5
    for b in tekst.encode('utf-8'):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def nazva_pachky(nomer: int, kartynka: bool) -> str:
    return f'{"k" if kartynka else "s"}{nomer:05d}.bin'


class Pachky:
    """Складає сторінки й картинки будинків у пачки й пише їх у `<вихід>/_budynky/`."""

    def __init__(self, budynkiv: int, u_pachtsi: int | None = None):
        self.n = max(1, math.ceil(budynkiv / (u_pachtsi or BUDYNKIV_U_PACHTSI)))
        self.storinky = [dict() for _ in range(self.n)]
        self.kartynky = [dict() for _ in range(self.n)]

    def dodaty(self, slug: str, html_: str, png: bytes | None) -> None:
        i = fnv1a(slug) % self.n
        self.storinky[i][slug] = html_.encode('utf-8')
        if png is not None:
            self.kartynky[i][slug] = png

    @staticmethod
    def zapakuvaty(zapysy: dict) -> bytes:
        pokazhchyk, chastyny, zsuv = {}, [], 0
        for slug in sorted(zapysy):
            d = zapysy[slug]
            pokazhchyk[slug] = [zsuv, len(d)]
            chastyny.append(d)
            zsuv += len(d)
        p = json.dumps(pokazhchyk, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return struct.pack('>I', len(p)) + p + b''.join(chastyny)

    def zapysaty(self, vykhid: Path) -> None:
        teka = vykhid / TEKA_PACHOK
        teka.mkdir(parents=True, exist_ok=True)
        for i in range(self.n):
            (teka / nazva_pachky(i, False)).write_bytes(self.zapakuvaty(self.storinky[i]))
            (teka / nazva_pachky(i, True)).write_bytes(self.zapakuvaty(self.kartynky[i]))


def rozpakuvaty(dani: bytes, slug: str) -> bytes | None:
    """Те саме, що робить worker/index.js: дістати один запис з пачки (для тестів і перевірки)."""
    L = struct.unpack('>I', dani[:4])[0]
    z = json.loads(dani[4:4 + L].decode('utf-8')).get(slug)
    return None if z is None else dani[4 + L + z[0]:4 + L + z[0] + z[1]]


def teka_workera(vykhid: Path) -> Path:
    return vykhid.parent / f'{vykhid.name}-worker'


def pidhotuvaty_worker(vykhid: Path, pachok: int, nazva: str = 'moya-vulytsya') -> Path:
    """Тека поруч із сайтом: скрипт і налаштування Cloudflare Workers (`npx wrangler deploy` з цієї теки).
    Ключів тут немає: вхід у Cloudflare — токеном партнера в налаштуваннях запуску, не у файлах."""
    t = teka_workera(vykhid)
    if t.exists():
        shutil.rmtree(t)
    t.mkdir(parents=True)
    shutil.copyfile(WORKER / 'index.js', t / 'index.js')
    konfig = {
        'name': nazva,
        'main': 'index.js',
        'compatibility_date': '2026-11-01',
        'assets': {
            'directory': f'../{vykhid.name}',
            'binding': 'ASSETS',
            'not_found_handling': '404-page',
            'html_handling': 'auto-trailing-slash',
            'run_worker_first': ['/budynok/*'],
        },
        'vars': {'PACHOK': str(pachok)},
    }
    (t / 'wrangler.jsonc').write_text('// Зібрано site/zibraty_sait.py --khostynh workers (ZAVDANNYA-88). Не редагувати руками.\n'
                                      + json.dumps(konfig, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return t
