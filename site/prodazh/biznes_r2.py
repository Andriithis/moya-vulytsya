# -*- coding: utf-8 -*-
"""Копія бази для компанії → приватне сховище Cloudflare R2 (ZAVDANNYA-157; `site/worker/prodazh/biznes.js`).

Вхід — тека `kopiia-<версія>-<клієнт>/`, яку збирає `dani-edrsr/src/kopiia_biznesu.py` (baza.db, csv.zip, OPYS.md,
SHA256SUMS). Скрипт перевіряє контрольні суми й кладе файли під `biznes/<клієнт>/<версія>/…`, а **останнім** — маніфест
`biznes/<клієнт>/potochna.json` (версія, файли, байти): поки маніфест не переписано, клієнт за посиланням бачить попередню
копію цілою.

  python site/prodazh/biznes_r2.py <тека копії> --sukho                    # лише перевірити й порахувати
  python site/prodazh/biznes_r2.py <тека копії> --do-teky <тека>          # «сховище» на диску (перевірка без Cloudflare)
  CLOUDFLARE_API_TOKEN=… python site/prodazh/biznes_r2.py <тека копії> --zavantazhyty

Завантаження — `npx wrangler r2 object put … --remote`; вхід у Cloudflare — токеном партнера в змінній CLOUDFLARE_API_TOKEN,
не у файлах. Копія з описами подій — лише в R2: у теку сайту й у git цей скрипт нічого не пише. Лише стандартна бібліотека.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from khostynh import R2_BIZNES  # noqa: E402

FAJLY = ('baza.db', 'csv.zip', 'OPYS.md', 'SHA256SUMS')       # той самий перелік — FAJLY у prodazh/biznes.js
TYPY = {'baza.db': 'application/vnd.sqlite3', 'csv.zip': 'application/zip', 'OPYS.md': 'text/markdown; charset=utf-8',
        'SHA256SUMS': 'text/plain; charset=utf-8'}
TEKA = re.compile(r'kopiia-(\d{4}-\d{2}-\d{2})-(k\d{1,6})')


def pidhotuvaty(teka: Path) -> dict:
    """-> {klient, versiia, fajly: [(ключ R2, шлях, тип)], manifest}. Зупинка, якщо тека не та чи суми не збігаються."""
    m = TEKA.fullmatch(teka.name)
    if not m:
        raise SystemExit(f'{teka.name}: тека має зватися kopiia-<РРРР-ММ-ДД>-k<номер> (dani-edrsr/src/kopiia_biznesu.py)')
    versiia, klient = m.groups()
    brak = [f for f in FAJLY if not (teka / f).is_file()]
    if brak:
        raise SystemExit(f'{teka}: бракує {brak}')
    sumy = {}
    for r in (teka / 'SHA256SUMS').read_text(encoding='ascii').splitlines():
        h, _, f = r.partition('  ')
        sumy[f.strip()] = h.strip()
    for f in FAJLY[:-1]:
        h = hashlib.sha256((teka / f).read_bytes()).hexdigest()
        if sumy.get(f) != h:
            raise SystemExit(f'{f}: контрольна сума не збігається з SHA256SUMS — копію пошкоджено, зберіть ще раз')
    fajly = [(f'biznes/{klient}/{versiia}/{f}', teka / f, TYPY[f]) for f in FAJLY]
    manifest = {'versiia': versiia, 'klient': klient,
                'fajly': [{'imia': f, 'bait': (teka / f).stat().st_size, 'sha256': sumy.get(f, '')} for f in FAJLY]}
    return {'klient': klient, 'versiia': versiia, 'fajly': fajly, 'manifest': manifest}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Копія бази для компанії → сховище R2 (ZAVDANNYA-157)')
    ap.add_argument('teka', type=Path, help='kopiia-<версія>-<клієнт>/ з dani-edrsr/src/kopiia_biznesu.py')
    ap.add_argument('--sukho', action='store_true', help='лише перевірити й порахувати')
    ap.add_argument('--do-teky', type=Path, help='записати ключі файлами в теку (перевірка без Cloudflare)')
    ap.add_argument('--zavantazhyty', action='store_true', help='завантажити в R2 через wrangler')
    ap.add_argument('--koshyk', default=R2_BIZNES)
    a = ap.parse_args(argv)
    p = pidhotuvaty(a.teka.resolve())
    man = json.dumps(p['manifest'], ensure_ascii=False)
    kl_man = f'biznes/{p["klient"]}/potochna.json'
    print(f'{p["klient"]}, версія {p["versiia"]}: ' + ', '.join(f'{x["imia"]} {x["bait"] / 1e6:.1f} МБ' for x in p['manifest']['fajly']))
    if a.do_teky:
        for k, f, _t in p['fajly']:
            (a.do_teky / k).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, a.do_teky / k)
        (a.do_teky / kl_man).write_text(man, encoding='utf-8')
        print(f'Записано в {a.do_teky}')
    if a.zavantazhyty:
        npx = shutil.which('npx')
        if not npx or not os.environ.get('CLOUDFLARE_API_TOKEN'):
            raise SystemExit('Потрібні npx (Node.js) і змінна CLOUDFLARE_API_TOKEN (токен партнера)')
        man_f = a.teka / '.potochna.json'
        man_f.write_text(man, encoding='utf-8')
        try:
            for k, f, t in [*p['fajly'], (kl_man, man_f, 'application/json; charset=utf-8')]:      # маніфест — останнім
                r = subprocess.run([npx, 'wrangler', 'r2', 'object', 'put', f'{a.koshyk}/{k}', '--file', str(f), '--remote',
                                    '--content-type', t], capture_output=True, text=True)
                if r.returncode:
                    raise SystemExit(f'{k}: не завантажено ({(r.stderr or r.stdout)[-300:]}). Маніфест не переписано — '
                                     'клієнт бачить попередню копію. Запустіть ще раз.')
        finally:
            man_f.unlink(missing_ok=True)
        print(f'Готово. Посилання клієнту: python site/prodazh/biznes_klienty.py posylannia {p["klient"]} --dniv 7')
    return 0


if __name__ == '__main__':
    sys.exit(main())
