# -*- coding: utf-8 -*-
"""Карта підписника → приватне сховище Cloudflare R2 (ZAVDANNYA-133, п. 1; docs/PLATNA-CHASTYNA.md, розд. 2).

Вхід — тека, яку збирає `dani-edrsr/src/karta_pidpysnyka.py` (index.html, dani/, spravy/<клітинка>.json, adresy/, vendor/,
shryfty/). Скрипт:
  1) додає покажчик точок `indeks/<клітинка>.json` — [[шир, довг, № точки, адреса], …] — щоб сервер відповідав на
     «події адреси» (`/pidpysnyk/api/podii?la=…&lo=…`), прочитавши два малі файли, а не всю карту;
  2) кладе все в R2 під `karta/<версія>/…` і **останнім** — маніфест `karta/potochna.json` (версія, перелік категорій,
     скільки файлів і байтів). Поки маніфест не переписано, сайт віддає стару версію цілою.

  python site/prodazh/karta_r2.py <тека карти> --sukho                      # лише порахувати: файли, МБ, клітинки
  python site/prodazh/karta_r2.py <тека карти> --do-teky <тека>             # «сховище» на диску (перевірка без Cloudflare)
  python site/prodazh/karta_r2.py <тека карти> --zavantazhyty [--koshyk moya-vulytsya-karta] [--potoky 8]

Завантаження — `npx wrangler r2 object put … --remote`; вхід у Cloudflare — токеном партнера в змінній CLOUDFLARE_API_TOKEN
(docs/ZAPUSK-SAITU.md), не у файлах. Описи справ лишаються лише в R2: у теку сайту (`_site`) цей скрипт нічого не пише.
Лише стандартна бібліотека Python.
"""
from __future__ import annotations

import argparse
import concurrent.futures as CF
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

KOSHYK = 'moya-vulytsya-karta'
# Клітинка справ — як dani-edrsr/src/map_adresy.py: KLITYNKA = (0.018, 0.028), SPRAVY_KL = KLITYNKA / 4. Ті самі числа
# в site/worker/prodazh/karta.js (KLITYNKA); тест порівнює.
SPRAVY_KL = (0.018 / 4, 0.028 / 4)
TYPY = {'html': 'text/html; charset=utf-8', 'json': 'application/json; charset=utf-8', 'js': 'text/javascript; charset=utf-8',
        'css': 'text/css; charset=utf-8', 'woff2': 'font/woff2', 'png': 'image/png', 'svg': 'image/svg+xml', 'txt': 'text/plain; charset=utf-8'}


def klitynka(la: float, lo: float) -> str:
    return f'{math.floor(la / SPRAVY_KL[0])}_{math.floor(lo / SPRAVY_KL[1])}'


def odyn_fail(teka: Path, vzirets: str) -> Path:
    f = sorted(teka.glob(vzirets))
    if len(f) != 1:
        raise SystemExit(f'У {teka} має бути рівно один {vzirets}, знайдено: {[x.name for x in f]}')
    return f[0]


def pidhotuvaty(teka: Path) -> dict:
    """Покажчик точок і маніфест. Повертає {versiia, indeks: {клітинка: [...]}, manifest, fajly: [(ключ у R2, шлях)]}."""
    if not (teka / 'index.html').exists() or not (teka / 'spravy').is_dir():
        raise SystemExit(f'{teka}: це не тека карти підписника (немає index.html чи spravy/) — зберіть dani-edrsr/src/karta_pidpysnyka.py')
    meta = json.loads(odyn_fail(teka / 'dani', 'meta.*.json').read_text(encoding='utf-8'))
    pts = json.loads(odyn_fail(teka / 'dani', 'pts.*.json').read_text(encoding='utf-8'))
    versiia = str(meta.get('versiia') or '').strip()
    if not versiia or not all(c.isalnum() or c in '-_.' for c in versiia):
        raise SystemExit(f'Версія карти «{versiia}» — порожня чи з недозволеними знаками')
    vul = pts['v']
    indeks: dict[str, list] = {}
    for i, p in enumerate(pts['p']):
        la, lo, adr = p[0], p[1], p[2]
        if isinstance(adr, list):                 # «вулиця, номер» упаковано як [№ вулиці, номер] (map_dani.pakuvaty_P)
            adr = f'{vul[adr[0]]}, {adr[1]}'
        indeks.setdefault(klitynka(la, lo), []).append([la, lo, i, adr])
    # кожна точка з подіями мусить мати свою клітинку справ — інакше «події адреси» мовчки повертали б порожньо
    bez = [k for k in indeks if not (teka / 'spravy' / f'{k}.json').exists()]
    if bez:
        raise SystemExit(f'Клітинок без файла справ: {len(bez)} (напр. {bez[:3]}) — інша формула клітинки, ніж у збирача?')
    fajly = [(f'karta/{versiia}/{f.relative_to(teka).as_posix()}', f) for f in sorted(teka.rglob('*'))
             if f.is_file() and not f.relative_to(teka).as_posix().startswith('indeks/')]
    manifest = {'versiia': versiia, 'kategorii': meta.get('cats', []), 'tochok': len(pts['p']), 'klitynok_indeksu': len(indeks),
                'fajliv': len(fajly) + len(indeks), 'bait': sum(f.stat().st_size for _, f in fajly)}
    return {'versiia': versiia, 'indeks': indeks, 'manifest': manifest, 'fajly': fajly}


def zapysaty_indeks(teka: Path, plan: dict) -> list[tuple[str, Path]]:
    d = teka / 'indeks'
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    out = []
    for k, v in sorted(plan['indeks'].items()):
        f = d / f'{k}.json'
        f.write_text(json.dumps(v, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        out.append((f'karta/{plan["versiia"]}/indeks/{k}.json', f))
    return out


def pidsumok(teka: Path, plan: dict) -> dict:
    sprav = list((teka / 'spravy').glob('*.json'))
    b = sum(f.stat().st_size for f in sprav)
    gz = sum(len(gzip.compress(f.read_bytes(), 6)) for f in sprav)
    return {'versiia': plan['versiia'], 'tochok': plan['manifest']['tochok'], 'fajliv': plan['manifest']['fajliv'],
            'usogo_MB': round(plan['manifest']['bait'] / 1e6, 1), 'spravy_fajliv': len(sprav), 'spravy_MB': round(b / 1e6, 1),
            'spravy_gzip_MB': round(gz / 1e6, 1), 'naibilsha_klitynka_KB': round(max((f.stat().st_size for f in sprav), default=0) / 1e3)}


def do_teky(plan: dict, indeks: list, tsil: Path) -> None:
    """«Сховище» на диску: ті самі ключі, що в R2 (для перевірки скрипта Workers без Cloudflare)."""
    for kliuch, f in plan['fajly'] + indeks:
        t = tsil / kliuch
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, t)
    (tsil / 'karta' / 'potochna.json').write_text(json.dumps(plan['manifest'], ensure_ascii=False), encoding='utf-8')


def zavantazhyty(plan: dict, indeks: list, koshyk: str, potoky: int, teka: Path) -> None:
    npx = shutil.which('npx')
    if not npx:
        raise SystemExit('Немає npx (Node.js) — потрібен для wrangler')
    if not os.environ.get('CLOUDFLARE_API_TOKEN'):
        raise SystemExit('Немає змінної CLOUDFLARE_API_TOKEN (токен партнера, docs/ZAPUSK-SAITU.md)')

    def put(kv):
        kliuch, f = kv
        typ = TYPY.get(f.suffix.lstrip('.'), 'application/octet-stream')
        p = subprocess.run([npx, 'wrangler', 'r2', 'object', 'put', f'{koshyk}/{kliuch}', '--file', str(f), '--remote',
                            '--content-type', typ], capture_output=True, text=True)
        return kliuch, p.returncode, (p.stderr or p.stdout)[-300:]

    vsi = plan['fajly'] + indeks
    pomylky = []
    with CF.ThreadPoolExecutor(potoky) as ex:
        for n, (kliuch, kod, tekst) in enumerate(ex.map(put, vsi), 1):
            if kod:
                pomylky.append((kliuch, tekst))
            if n % 100 == 0:
                print(f'  {n}/{len(vsi)}', flush=True)
    if pomylky:
        raise SystemExit(f'Не завантажено {len(pomylky)} файлів (перший: {pomylky[0]}). Маніфест НЕ переписано — '
                         'сайт і далі віддає попередню версію. Запустіть ще раз.')
    m = teka / 'indeks' / '_potochna.json'
    m.write_text(json.dumps(plan['manifest'], ensure_ascii=False), encoding='utf-8')
    k, kod, tekst = put(('karta/potochna.json', m))
    if kod:
        raise SystemExit(f'Файли є, а маніфест не записано: {tekst}')
    print(f'Готово: {len(vsi)} файлів, чинна версія — {plan["versiia"]}. Старі версії karta/<версія>/ можна прибрати в панелі R2.')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Карта підписника → сховище R2 (ZAVDANNYA-133)')
    ap.add_argument('teka', type=Path, help='тека карти з dani-edrsr/src/karta_pidpysnyka.py')
    ap.add_argument('--sukho', action='store_true', help='лише порахувати')
    ap.add_argument('--do-teky', type=Path, help='записати ключі R2 файлами в цю теку (перевірка без Cloudflare)')
    ap.add_argument('--zavantazhyty', action='store_true', help='завантажити в R2 через wrangler')
    ap.add_argument('--koshyk', default=KOSHYK)
    ap.add_argument('--potoky', type=int, default=8)
    a = ap.parse_args(argv)
    plan = pidhotuvaty(a.teka)
    print(json.dumps(pidsumok(a.teka, plan), ensure_ascii=False))
    if a.sukho:
        return 0
    indeks = zapysaty_indeks(a.teka, plan)
    if a.do_teky:
        do_teky(plan, indeks, a.do_teky)
        print(f'Записано в {a.do_teky}')
    if a.zavantazhyty:
        zavantazhyty(plan, indeks, a.koshyk, a.potoky, a.teka)
    return 0


if __name__ == '__main__':
    sys.exit(main())
