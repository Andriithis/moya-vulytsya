# -*- coding: utf-8 -*-
"""ZAVDANNYA-69, крок 1: скарги 1551 -> кеш для табло звіту адреси.

Прив'язка до будинків — ТОЙ САМИЙ код конвеєра (`dani-edrsr/src/budynky_1551.py`, ZAVDANNYA-66, MV-80): ключ адреси
`adr_kliuch`, довідник адрес OSM, ті самі правила номера. Тут нічого не переписано — лише складено в один файл
(будинок, група, місяць) -> скарг, щоб збирач звіту не перечитував 1,3 млн звернень щоразу.

  set DANI_EDRSR=<тека з src/ і config/ гілки main dani-edrsr та data/ з 1551, borders.json, osm_kyiv_city.json>
  python zvit_adresy/skargy69.py <вихід.json>

Вихід — приватний (адреси будинків), лише в tmp/, не в git.
"""
import os, sys, json, collections

DE = os.environ.get('DANI_EDRSR')
if not DE or not os.path.isdir(os.path.join(DE, 'src')):
    sys.exit('вкажіть DANI_EDRSR — теку з кодом dani-edrsr (src/, config/) і data/')
sys.path.insert(0, os.path.join(DE, 'src'))
os.chdir(DE)
import budynky_1551 as BU  # noqa: E402

DO = '2026-10'   # листопад 2026 зібрано не повністю (1551-DLIA-ZVITU, «Як міряно»)


def main():
    out = sys.argv[1]
    Zr = BU.zamir(DO)
    B = Zr['budynky']
    kliuchi = sorted(B)
    idx = {k: i for i, k in enumerate(kliuchi)}
    hrupy = sorted(Zr['H'].nazvy())
    hi = {h: i for i, h in enumerate(hrupy)}
    misiatsi = sorted(Zr['misiatsi'])
    mi = {m: i for i, m in enumerate(misiatsi)}
    bgm = [[idx[bk], hi[h], mi[ym], n] for (bk, h, ym), n in Zr['bgm'].items()]
    zmist = collections.defaultdict(collections.Counter)
    for (bk, kind, content), n in Zr['zmist_bud'].items():
        zmist[bk][content] += n
    json.dump({
        'do': DO, 'hrupy': hrupy, 'misiatsi': misiatsi,
        'budynky': [[k, round(B[k]['lat'], 6), round(B[k]['lon'], 6), B[k]['raion'], B[k]['pidpys']] for k in kliuchi],
        'bgm': bgm,
        # найчастіший зміст — лише для 8 перших рядків будинку (для підпису «що саме»), не весь набір
        'zmist': {k: zmist[k].most_common(8) for k in kliuchi},
        'zvernen': {m: dict(c) for m, c in Zr['misiatsi'].items()},
    }, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(kliuchi)} будинків, {len(bgm)} рядків (будинок, група, місяць) -> {out}')


if __name__ == '__main__':
    main()
