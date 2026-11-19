# -*- coding: utf-8 -*-
"""Таблиці «Судової практики» для підписки юриста → приватне сховище R2 (ZAVDANNYA-135; `site/worker/prodazh/sudova.js`).

Те саме зведення, що й для безкоштовних сторінок (`dani-edrsr/src/sudova_praktyka.py sait` → sudova-praktyka.json), але
повністю: по судах, частинах і роках. На сайт воно не йде — лише в сховище довідок (прив'язка DOVIDKY), звідки його
віддає сервер продажу людині з дійсною підпискою юриста.

  python site/prodazh/praktyka_r2.py sudova-praktyka.json --do-teky /tmp/r2      # перевірка без Cloudflare
  CLOUDFLARE_API_TOKEN=… python site/prodazh/praktyka_r2.py sudova-praktyka.json --zavantazhyty

Ключі: praktyka/<версія>/<kupap|kk>-<номер>.json (по файлу на статтю, щоб скрипт Workers не розбирав усе зведення
на кожен запит); останнім — praktyka/potochna.json ({"versiia": …}): нова версія вмикається одним записом.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from khostynh import R2_DOVIDOK  # noqa: E402

SLUG = {'КУпАП': 'kupap', 'КК': 'kk'}


def fajly(dani: dict) -> dict[str, str]:
    """{ключ R2: вміст}. Маніфест — окремо (пишеться останнім)."""
    v = dani.get('versiia') or 'bez-versii'
    stroky = set(dani.get('stroky') or ())
    out = {}
    for s in dani['statti']:
        kl = f'ст.{s["nomer"]} {s["kodeks"]}'
        out[f'praktyka/{v}/{SLUG[s["kodeks"]]}-{s["nomer"]}.json'] = json.dumps({
            'kodeks': s['kodeks'], 'nomer': s['nomer'], 'stattia': kl, 'nazva': s['nazva'], 'kat': s['kat'],
            'pokarano': s['pokarano'], 'strok': kl in stroky, 'ryadky': s['ryadky']}, ensure_ascii=False, separators=(',', ':'))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='«Судова практика» → сховище R2 (ZAVDANNYA-135)')
    ap.add_argument('dzherelo', type=Path, help='sudova-praktyka.json з dani-edrsr')
    ap.add_argument('--do-teky', type=Path, help='записати ключі файлами в теку (перевірка без Cloudflare)')
    ap.add_argument('--zavantazhyty', action='store_true', help='завантажити в R2 через wrangler')
    ap.add_argument('--koshyk', default=R2_DOVIDOK)
    a = ap.parse_args(argv)
    dani = json.loads(a.dzherelo.read_text(encoding='utf-8'))
    ff = fajly(dani)
    manifest = json.dumps({'versiia': dani.get('versiia') or 'bez-versii'}, ensure_ascii=False)
    print(f'{len(ff)} статей, {sum(len(x) for x in ff.values()):,} байт, версія {dani.get("versiia")}')
    if a.do_teky:
        for k, t in {**ff, 'praktyka/potochna.json': manifest}.items():
            (a.do_teky / k).parent.mkdir(parents=True, exist_ok=True)
            (a.do_teky / k).write_text(t, encoding='utf-8')
        print(f'Записано в {a.do_teky}')
    if a.zavantazhyty:
        npx = shutil.which('npx')
        if not npx or not os.environ.get('CLOUDFLARE_API_TOKEN'):
            raise SystemExit('Потрібні npx (Node.js) і змінна CLOUDFLARE_API_TOKEN (токен партнера)')
        with tempfile.TemporaryDirectory() as t:
            for k, tekst in [*ff.items(), ('praktyka/potochna.json', manifest)]:     # маніфест — останнім
                f = Path(t) / 'f.json'
                f.write_text(tekst, encoding='utf-8')
                p = subprocess.run([npx, 'wrangler', 'r2', 'object', 'put', f'{a.koshyk}/{k}', '--file', str(f), '--remote',
                                    '--content-type', 'application/json; charset=utf-8'], capture_output=True, text=True)
                if p.returncode:
                    raise SystemExit(f'{k}: не завантажено ({(p.stderr or p.stdout)[-300:]}). Маніфест не переписано — '
                                     'юристи бачать попередню версію. Запустіть ще раз.')
        print('Готово.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
